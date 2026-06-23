"""訓練 HalfKP NNUE 局面評估器。

建議標籤由教師引擎搜尋分數與最終勝負混合而成。若資料尚無教師分數，
序盤的純勝負標籤會往 0.5 平滑，並降低 loss 權重，減少高變異的最終
勝負結果干擾序盤學習。
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cshogi
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, Subset

from nnue_model import HALFKP_FEATURES, MODEL_TYPE_HALFKP, NNUEConfig, ShogiNNUE, halfkp_feature_indices


@dataclass(frozen=True)
class TrainStats:
    epoch: int
    train_loss: float
    valid_loss: float


@dataclass(frozen=True)
class DatasetStats:
    total_rows: int
    kept_rows: int
    teacher_rows: int
    result_only_rows: int
    skipped_by_min_ply: int
    skipped_by_max_ply: int
    skipped_missing_ply: int
    skipped_bad_rows: int


@dataclass(frozen=True)
class PositionSample:
    black_features: list[int]
    white_features: list[int]
    side_to_move: int
    target_probability: float
    loss_weight: float
    group: str


def parse_meta(raw_meta: object) -> dict[str, Any]:
    if isinstance(raw_meta, bytes):
        return json.loads(raw_meta.decode("utf-8"))
    return json.loads(str(raw_meta))


def meta_ply(meta: dict[str, Any]) -> int | None:
    for key in ("ply", "move_number", "move_index"):
        if key in meta:
            try:
                return int(meta[key])
            except (TypeError, ValueError):
                return None
    return None


def game_group(meta: dict[str, Any], row_index: int) -> str:
    for key in ("game_id", "source", "file", "csa_path"):
        value = meta.get(key)
        if value not in (None, ""):
            return str(value)
    return f"row:{row_index}"


def sigmoid_number(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def phase_progress(ply: int, start_ply: int, full_ply: int) -> float:
    if full_ply <= start_ply:
        return 1.0
    return min(1.0, max(0.0, (ply - start_ply) / (full_ply - start_ply)))


def make_target(
    result_value: float | None,
    teacher_score: float | None,
    ply: int,
    teacher_score_scale: float,
    teacher_weight_early: float,
    teacher_weight_late: float,
    result_confidence_early: float,
    result_confidence_late: float,
    confidence_full_ply: int,
) -> tuple[float, float, bool]:
    progress = phase_progress(ply, 1, confidence_full_ply)
    result_probability = None
    if result_value is not None and math.isfinite(float(result_value)):
        result_probability = min(1.0, max(0.0, (float(result_value) + 1.0) / 2.0))

    if teacher_score is not None and math.isfinite(teacher_score):
        teacher_probability = sigmoid_number(float(teacher_score) / teacher_score_scale)
        if result_probability is None:
            return teacher_probability, 1.0, True
        teacher_weight = teacher_weight_early + progress * (teacher_weight_late - teacher_weight_early)
        teacher_weight = min(1.0, max(0.0, teacher_weight))
        target = teacher_weight * teacher_probability + (1.0 - teacher_weight) * result_probability
        return target, 1.0, True

    if result_probability is None:
        raise ValueError("這筆資料同時缺少教師分數與勝負標籤")

    confidence = result_confidence_early + progress * (result_confidence_late - result_confidence_early)
    confidence = min(1.0, max(0.0, confidence))
    target = 0.5 + confidence * (result_probability - 0.5)
        # 純勝負序盤局面仍有資訊，但不應壓過教師局面或勝負較明朗的終盤局面。
    loss_weight = 0.25 + 0.75 * progress
    return target, loss_weight, False


def find_teacher_scores(data: np.lib.npyio.NpzFile, requested_key: str) -> tuple[np.ndarray | None, str | None]:
    keys = (requested_key,) if requested_key != "auto" else ("teacher_scores", "search_scores", "eval_scores", "scores")
    for key in keys:
        if key in data.files:
            return data[key].astype(np.float32), key
    return None, None


class NNUEPositionDataset(Dataset[PositionSample]):
    def __init__(
        self,
        npz_path: Path,
        limit: int | None,
        min_ply: int,
        max_ply: int | None,
        teacher_score_key: str,
        teacher_score_scale: float,
        teacher_weight_early: float,
        teacher_weight_late: float,
        result_confidence_early: float,
        result_confidence_late: float,
        confidence_full_ply: int,
    ) -> None:
        data = np.load(npz_path, allow_pickle=True)
        if "meta" not in data.files:
            raise ValueError(f"資料集缺少 meta；目前欄位：{list(data.files)}")
        metas = data["meta"]
        teacher_scores, self.teacher_score_key = find_teacher_scores(data, teacher_score_key)
        values = data["values"].astype(np.float32) if "values" in data.files else None
        value_masks = data["value_masks"].astype(np.float32) if "value_masks" in data.files else None
        if values is None and teacher_scores is None:
            raise ValueError(
                "資料集至少需要 values 或 teacher_scores；"
                f"目前欄位：{list(data.files)}"
            )
        if values is not None and len(metas) != len(values):
            raise ValueError(f"meta/value 長度不同：meta={len(metas)}, values={len(values)}")
        if value_masks is not None and len(metas) != len(value_masks):
            raise ValueError(f"meta/value_masks 長度不同：meta={len(metas)}, value_masks={len(value_masks)}")
        if teacher_scores is not None and len(teacher_scores) != len(metas):
            raise ValueError(f"meta/teacher_scores 長度不同：meta={len(metas)}, teacher_scores={len(teacher_scores)}")

        self.samples: list[PositionSample] = []
        skipped_min = skipped_max = skipped_missing = skipped_bad = teacher_rows = 0
        for row_index in range(len(metas)):
            if limit is not None and len(self.samples) >= limit:
                break
            try:
                meta = parse_meta(metas[row_index])
                ply = meta_ply(meta)
                if ply is None:
                    skipped_missing += 1
                    continue
                if ply < min_ply:
                    skipped_min += 1
                    continue
                if max_ply is not None and ply > max_ply:
                    skipped_max += 1
                    continue
                board = cshogi.Board(meta["sfen"])
                teacher_score = None if teacher_scores is None else float(teacher_scores[row_index])
                has_result = values is not None and (value_masks is None or float(value_masks[row_index]) > 0.5)
                result_value = float(values[row_index]) if has_result else None
                target, weight, has_teacher = make_target(
                    result_value=result_value,
                    teacher_score=teacher_score,
                    ply=ply,
                    teacher_score_scale=teacher_score_scale,
                    teacher_weight_early=teacher_weight_early,
                    teacher_weight_late=teacher_weight_late,
                    result_confidence_early=result_confidence_early,
                    result_confidence_late=result_confidence_late,
                    confidence_full_ply=confidence_full_ply,
                )
                teacher_rows += int(has_teacher)
                self.samples.append(
                    PositionSample(
                        black_features=halfkp_feature_indices(board, cshogi.BLACK),
                        white_features=halfkp_feature_indices(board, cshogi.WHITE),
                        side_to_move=int(board.turn),
                        target_probability=target,
                        loss_weight=weight,
                        group=game_group(meta, row_index),
                    )
                )
            except Exception:
                skipped_bad += 1

        self.stats = DatasetStats(
            total_rows=len(metas),
            kept_rows=len(self.samples),
            teacher_rows=teacher_rows,
            result_only_rows=len(self.samples) - teacher_rows,
            skipped_by_min_ply=skipped_min,
            skipped_by_max_ply=skipped_max,
            skipped_missing_ply=skipped_missing,
            skipped_bad_rows=skipped_bad,
        )

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> PositionSample:
        return self.samples[index]


def flatten_feature_lists(feature_lists: list[list[int]]) -> tuple[torch.Tensor, torch.Tensor]:
    flat: list[int] = []
    offsets: list[int] = []
    cursor = 0
    for features in feature_lists:
        offsets.append(cursor)
        flat.extend(features)
        cursor += len(features)
    return torch.tensor(flat, dtype=torch.long), torch.tensor(offsets, dtype=torch.long)


def collate_sparse(batch: list[PositionSample]) -> tuple[torch.Tensor, ...]:
    black_indices, black_offsets = flatten_feature_lists([sample.black_features for sample in batch])
    white_indices, white_offsets = flatten_feature_lists([sample.white_features for sample in batch])
    return (
        black_indices,
        black_offsets,
        white_indices,
        white_offsets,
        torch.tensor([sample.side_to_move for sample in batch], dtype=torch.long),
        torch.tensor([sample.target_probability for sample in batch], dtype=torch.float32),
        torch.tensor([sample.loss_weight for sample in batch], dtype=torch.float32),
    )


def split_by_game(dataset: NNUEPositionDataset, valid_ratio: float, seed: int) -> tuple[Subset, Subset]:
    groups: dict[str, list[int]] = {}
    for index, sample in enumerate(dataset.samples):
        groups.setdefault(sample.group, []).append(index)
    group_names = list(groups)
    random.Random(seed).shuffle(group_names)
    target_valid = max(1, int(len(dataset) * valid_ratio))
    valid_indices: list[int] = []
    train_indices: list[int] = []
    for group_name in group_names:
        destination = valid_indices if len(valid_indices) < target_valid else train_indices
        destination.extend(groups[group_name])
    if not train_indices:
        train_indices.append(valid_indices.pop())
    return Subset(dataset, train_indices), Subset(dataset, valid_indices)


def run_epoch(
    model: ShogiNNUE,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    grad_clip: float = 2.0,
) -> float:
    training = optimizer is not None
    model.train(training)
    weighted_loss_sum = 0.0
    weight_sum = 0.0
    for batch in loader:
        black_indices, black_offsets, white_indices, white_offsets, side_to_move, targets, weights = (
            tensor.to(device) for tensor in batch
        )
        if training:
            optimizer.zero_grad(set_to_none=True)
        logits = model(black_indices, black_offsets, white_indices, white_offsets, side_to_move)
        losses = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        loss = (losses * weights).sum() / weights.sum().clamp_min(1e-8)
        if training:
            loss.backward()
            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
        weighted_loss_sum += float((losses.detach() * weights).sum().cpu())
        weight_sum += float(weights.sum().detach().cpu())
    return weighted_loss_sum / max(weight_sum, 1e-8)


def parse_hidden_sizes(raw: str) -> tuple[int, ...]:
    values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("hidden sizes must be positive comma-separated integers")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="訓練將棋雙視角 HalfKP NNUE。")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--valid-ratio", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-ply", type=int, default=30, help="預設前 30 手交由開局庫處理")
    parser.add_argument("--max-ply", type=int, default=None)
    parser.add_argument("--accumulator-size", type=int, default=128)
    parser.add_argument("--hidden-sizes", type=parse_hidden_sizes, default=(256, 128, 64, 32))
    parser.add_argument("--score-scale", type=int, default=600, help="每 1 單位 logit 對應的搜尋分數")
    parser.add_argument("--max-search-score", type=int, default=30_000)
    parser.add_argument("--teacher-score-key", default="auto")
    parser.add_argument("--teacher-score-scale", type=float, default=600.0)
    parser.add_argument("--teacher-weight-early", type=float, default=0.90)
    parser.add_argument("--teacher-weight-late", type=float, default=0.45)
    parser.add_argument("--result-confidence-early", type=float, default=0.15)
    parser.add_argument("--result-confidence-late", type=float, default=0.90)
    parser.add_argument("--confidence-full-ply", type=int, default=160)
    parser.add_argument("--grad-clip", type=float, default=2.0)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=11211213)
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    config = NNUEConfig(
        model_type=MODEL_TYPE_HALFKP,
        accumulator_size=args.accumulator_size,
        hidden_sizes=args.hidden_sizes,
        score_scale=args.score_scale,
        max_search_score=args.max_search_score,
    )
    dataset = NNUEPositionDataset(
        npz_path=args.input,
        limit=args.limit,
        min_ply=max(1, args.min_ply),
        max_ply=args.max_ply,
        teacher_score_key=args.teacher_score_key,
        teacher_score_scale=args.teacher_score_scale,
        teacher_weight_early=args.teacher_weight_early,
        teacher_weight_late=args.teacher_weight_late,
        result_confidence_early=args.result_confidence_early,
        result_confidence_late=args.result_confidence_late,
        confidence_full_ply=args.confidence_full_ply,
    )
    print("dataset_stats=" + json.dumps(asdict(dataset.stats), ensure_ascii=False))
    print(f"teacher_score_key={dataset.teacher_score_key}")
    if len(dataset) < 2:
        raise SystemExit("dataset is too small after filtering")
    train_set, valid_set = split_by_game(dataset, args.valid_ratio, args.seed)

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model = ShogiNNUE(
        feature_count=HALFKP_FEATURES,
        accumulator_size=config.accumulator_size,
        hidden_sizes=config.hidden_sizes,
    ).to(device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    print(f"device={device} train={len(train_set)} valid={len(valid_set)} parameters={parameter_count:,}")
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=2)
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, collate_fn=collate_sparse)
    valid_loader = DataLoader(valid_set, batch_size=args.batch_size, shuffle=False, collate_fn=collate_sparse)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    best_valid = float("inf")
    stats: list[TrainStats] = []
    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(model, train_loader, device, optimizer, args.grad_clip)
        with torch.inference_mode():
            valid_loss = run_epoch(model, valid_loader, device, None, args.grad_clip)
        scheduler.step(valid_loss)
        stats.append(TrainStats(epoch, train_loss, valid_loss))
        print(f"epoch={epoch:03d} train_loss={train_loss:.6f} valid_loss={valid_loss:.6f} lr={optimizer.param_groups[0]['lr']:.2e}")
        checkpoint = {
            "model_state": model.state_dict(),
            "config": {**asdict(config), "feature_count": HALFKP_FEATURES},
            "label_config": {
                "teacher_score_key": dataset.teacher_score_key,
                "teacher_score_scale": args.teacher_score_scale,
                "teacher_weight_early": args.teacher_weight_early,
                "teacher_weight_late": args.teacher_weight_late,
                "result_confidence_early": args.result_confidence_early,
                "result_confidence_late": args.result_confidence_late,
                "confidence_full_ply": args.confidence_full_ply,
            },
            "dataset_stats": asdict(dataset.stats),
            "stats": [asdict(item) for item in stats],
        }
        torch.save(checkpoint, args.output)
        if valid_loss < best_valid:
            best_valid = valid_loss
            torch.save(checkpoint, args.output.with_suffix(".best.pt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
