from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cshogi
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from nnue_model import NNUE_FEATURES, SparseNNUEValueNet, nnue_feature_indices


class NNUEDataset(Dataset[tuple[list[int], float]]):
    def __init__(self, sfens: np.ndarray, values: np.ndarray, indices: np.ndarray) -> None:
        self.sfens = sfens
        self.values = values
        self.indices = indices

    def __len__(self) -> int:
        return int(self.indices.size)

    def __getitem__(self, index: int) -> tuple[list[int], float]:
        sample_index = int(self.indices[index])
        board = cshogi.Board(str(self.sfens[sample_index]))
        return nnue_feature_indices(board), float(self.values[sample_index])


def collate_nnue(batch: list[tuple[list[int], float]]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    flat_features: list[int] = []
    offsets: list[int] = []
    values: list[float] = []
    cursor = 0
    for features, value in batch:
        offsets.append(cursor)
        flat_features.extend(features)
        cursor += len(features)
        values.append(value)
    return (
        torch.tensor(flat_features, dtype=torch.long),
        torch.tensor(offsets, dtype=torch.long),
        torch.tensor(values, dtype=torch.float32),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train an NNUE-like sparse value evaluator.")
    parser.add_argument("--input", required=True, type=Path, help="Dataset .npz created by export_policy_dataset.py")
    parser.add_argument("--output", required=True, type=Path, help="NNUE checkpoint path")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260521)
    parser.add_argument("--max-samples", type=int, default=None, help="Optional smoke-test limit")
    return parser.parse_args()


def split_by_game(game_ids: np.ndarray, indices: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    unique_games = sorted({int(game_ids[index]) for index in indices})
    rng = random.Random(seed)
    rng.shuffle(unique_games)
    train_end = max(1, int(len(unique_games) * 0.8))
    val_end = max(train_end + 1, int(len(unique_games) * 0.9))
    train_games = set(unique_games[:train_end])
    val_games = set(unique_games[train_end:val_end])
    test_games = set(unique_games[val_end:])
    train_indices = indices[np.isin(game_ids[indices], list(train_games))]
    val_indices = indices[np.isin(game_ids[indices], list(val_games))]
    test_indices = indices[np.isin(game_ids[indices], list(test_games))]
    return train_indices, val_indices, test_indices


def sfens_from_meta(meta: np.ndarray) -> np.ndarray:
    sfens = []
    for item in meta:
        sfens.append(json.loads(str(item))["sfen"])
    return np.asarray(sfens)


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    if len(loader.dataset) == 0:
        return {"loss": 0.0, "mae": 0.0}
    criterion = nn.MSELoss(reduction="sum")
    total_loss = 0.0
    total_mae = 0.0
    total = 0
    model.eval()
    with torch.inference_mode():
        for feature_indices, offsets, values in loader:
            feature_indices = feature_indices.to(device)
            offsets = offsets.to(device)
            values = values.to(device)
            predictions = model(feature_indices, offsets)
            total_loss += float(criterion(predictions, values))
            total_mae += float(torch.abs(predictions - values).sum())
            total += int(values.numel())
    return {"loss": total_loss / total, "mae": total_mae / total}


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    data = np.load(args.input, allow_pickle=False)
    values = data["values"].astype(np.float32, copy=False)
    masks = data["value_masks"] if "value_masks" in data.files else np.ones_like(values, dtype=np.float32)
    game_ids = data["game_ids"] if "game_ids" in data.files else np.arange(values.size, dtype=np.int32)
    sfens = sfens_from_meta(data["meta"])
    valid_indices = np.where(masks > 0)[0]
    if args.max_samples is not None:
        valid_indices = valid_indices[: args.max_samples]

    train_indices, val_indices, test_indices = split_by_game(game_ids, valid_indices, args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader = DataLoader(
        NNUEDataset(sfens, values, train_indices),
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate_nnue,
    )
    val_loader = DataLoader(
        NNUEDataset(sfens, values, val_indices),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collate_nnue,
    )
    test_loader = DataLoader(
        NNUEDataset(sfens, values, test_indices),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collate_nnue,
    )

    model = SparseNNUEValueNet(NNUE_FEATURES, args.hidden_size).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.MSELoss()
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, float | int]] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total = 0
        for feature_indices, offsets, values_batch in train_loader:
            feature_indices = feature_indices.to(device)
            offsets = offsets.to(device)
            values_batch = values_batch.to(device)
            optimizer.zero_grad(set_to_none=True)
            predictions = model(feature_indices, offsets)
            loss = criterion(predictions, values_batch)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * int(values_batch.numel())
            total += int(values_batch.numel())

        train_loss = total_loss / max(total, 1)
        val_metrics = evaluate(model, val_loader, device)
        current_lr = float(optimizer.param_groups[0]["lr"])
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "learning_rate": current_lr,
            "val_loss": val_metrics["loss"],
            "val_mae": val_metrics["mae"],
        }
        history.append(row)
        print(json.dumps({key: round(value, 6) if isinstance(value, float) else value for key, value in row.items()}))
        if val_metrics["loss"] < best_loss:
            best_loss = val_metrics["loss"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        scheduler.step()

    if best_state is not None:
        model.load_state_dict(best_state)
    test_metrics = evaluate(model, test_loader, device)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "feature_count": NNUE_FEATURES,
            "hidden_size": args.hidden_size,
            "orient_to_turn": True,
            "history": history,
            "test_metrics": test_metrics,
            "splits": {
                "train_samples": int(train_indices.size),
                "validation_samples": int(val_indices.size),
                "test_samples": int(test_indices.size),
            },
        },
        args.output,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "train_samples": int(train_indices.size),
                "validation_samples": int(val_indices.size),
                "test_samples": int(test_indices.size),
                "test_loss": round(test_metrics["loss"], 6),
                "test_mae": round(test_metrics["mae"], 6),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
