"""功能：訓練 policy network，包含資料集、切分、驗證與 checkpoint 儲存流程。"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from csa_preprocess import MOVE_LABELS
from policy_model import SmallPolicyNet


class PolicyDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    """功能：定義 PolicyDataset 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    def __init__(
        self,
        states: np.ndarray,
        moves: np.ndarray,
        indices: np.ndarray,
    ) -> None:
        """功能：初始化物件狀態與必要資源。"""
        self.states = states
        self.moves = moves
        self.indices = indices

    def __len__(self) -> int:
        """功能：處理 __len__ 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        return int(self.indices.size)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        """功能：處理 __getitem__ 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        sample_index = int(self.indices[index])
        state = torch.from_numpy(self.states[sample_index].astype(np.float32, copy=False))
        move = torch.tensor(int(self.moves[sample_index]), dtype=torch.long)
        return state, move


def parse_args() -> argparse.Namespace:
    """功能：解析命令列參數，讓使用者可以調整輸入、輸出與執行選項。"""
    parser = argparse.ArgumentParser(description="Train a small policy network.")
    parser.add_argument("--input", required=True, type=Path, help="Policy dataset .npz")
    parser.add_argument("--output", required=True, type=Path, help="Model checkpoint path")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--min-learning-rate", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=20260518)
    return parser.parse_args()


def split_by_game(game_ids: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """功能：處理 split_by_game 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    unique_games = sorted({int(game_id) for game_id in game_ids})
    rng = random.Random(seed)
    rng.shuffle(unique_games)

    total_games = len(unique_games)
    train_end = max(1, int(total_games * 0.8))
    val_end = max(train_end + 1, int(total_games * 0.9))
    train_games = set(unique_games[:train_end])
    val_games = set(unique_games[train_end:val_end])
    test_games = set(unique_games[val_end:])

    indices = np.arange(game_ids.size)
    train_indices = indices[np.isin(game_ids, list(train_games))]
    val_indices = indices[np.isin(game_ids, list(val_games))]
    test_indices = indices[np.isin(game_ids, list(test_games))]
    return train_indices, val_indices, test_indices


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    """功能：處理 evaluate 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if len(loader.dataset) == 0:
        return {
            "policy_loss": 0.0,
            "top1": 0.0,
            "top3": 0.0,
            "top5": 0.0,
        }
    policy_criterion = nn.CrossEntropyLoss()
    total_policy_loss = 0.0
    total_top1 = 0
    total_top3 = 0
    total_top5 = 0
    total = 0
    model.eval()
    with torch.inference_mode():
        for states, moves in loader:
            states = states.to(device)
            moves = moves.to(device)
            logits = model(states)
            policy_loss = policy_criterion(logits, moves)
            total_policy_loss += float(policy_loss) * states.size(0)
            topk = torch.topk(logits, k=5, dim=1).indices
            targets = moves.unsqueeze(1)
            total_top1 += int((topk[:, :1] == targets).any(dim=1).sum())
            total_top3 += int((topk[:, :3] == targets).any(dim=1).sum())
            total_top5 += int((topk == targets).any(dim=1).sum())
            total += int(states.size(0))
    return {
        "policy_loss": total_policy_loss / total,
        "top1": total_top1 / total,
        "top3": total_top3 / total,
        "top5": total_top5 / total,
    }


def main() -> int:
    """功能：串接本檔案的主要執行流程。"""
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    data = np.load(args.input, allow_pickle=False)
    states = data["states"]
    moves = data["moves"]
    game_ids = data["game_ids"]
    orient_to_turn = bool(data["orient_to_turn"])
    train_indices, val_indices, test_indices = split_by_game(game_ids, args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader = DataLoader(
        PolicyDataset(states, moves, train_indices),
        batch_size=args.batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        PolicyDataset(states, moves, val_indices),
        batch_size=args.batch_size,
        shuffle=False,
    )
    test_loader = DataLoader(
        PolicyDataset(states, moves, test_indices),
        batch_size=args.batch_size,
        shuffle=False,
    )

    model = SmallPolicyNet(MOVE_LABELS).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
        eta_min=args.min_learning_rate,
    )
    policy_criterion = nn.CrossEntropyLoss()
    best_val_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, float | int]] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total = 0
        for batch_states, batch_moves in train_loader:
            batch_states = batch_states.to(device)
            batch_moves = batch_moves.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch_states)
            loss = policy_criterion(logits, batch_moves)
            loss.backward()
            optimizer.step()
            total_loss += float(loss) * batch_states.size(0)
            total += int(batch_states.size(0))

        train_loss = total_loss / max(total, 1)
        val_metrics = evaluate(model, val_loader, device)
        current_lr = float(optimizer.param_groups[0]["lr"])
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "learning_rate": current_lr,
                "val_policy_loss": val_metrics["policy_loss"],
                "val_accuracy": val_metrics["top1"],
                "val_top3_accuracy": val_metrics["top3"],
                "val_top5_accuracy": val_metrics["top5"],
            }
        )
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "train_loss": round(train_loss, 6),
                    "learning_rate": round(current_lr, 8),
                    "val_policy_loss": round(val_metrics["policy_loss"], 6),
                    "val_accuracy": round(val_metrics["top1"], 6),
                    "val_top3_accuracy": round(val_metrics["top3"], 6),
                    "val_top5_accuracy": round(val_metrics["top5"], 6),
                },
                ensure_ascii=False,
            )
        )
        if val_metrics["policy_loss"] < best_val_loss:
            best_val_loss = val_metrics["policy_loss"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        scheduler.step()

    if best_state is not None:
        model.load_state_dict(best_state)
    test_metrics = evaluate(model, test_loader, device)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "move_label_count": MOVE_LABELS,
            "orient_to_turn": orient_to_turn,
            "history": history,
            "splits": {
                "train_samples": int(train_indices.size),
                "validation_samples": int(val_indices.size),
                "test_samples": int(test_indices.size),
            },
            "optimizer": "AdamW",
            "learning_rate": args.learning_rate,
            "min_learning_rate": args.min_learning_rate,
            "weight_decay": args.weight_decay,
            "test_metrics": {
                "policy_loss": test_metrics["policy_loss"],
                "accuracy": test_metrics["top1"],
                "top3_accuracy": test_metrics["top3"],
                "top5_accuracy": test_metrics["top5"],
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
                "test_policy_loss": round(test_metrics["policy_loss"], 6),
                "test_accuracy": round(test_metrics["top1"], 6),
                "test_top3_accuracy": round(test_metrics["top3"], 6),
                "test_top5_accuracy": round(test_metrics["top5"], 6),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
