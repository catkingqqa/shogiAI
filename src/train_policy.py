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
from policy_model import SmallPolicyValueNet


class PolicyValueDataset(Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]]):
    def __init__(
        self,
        states: np.ndarray,
        moves: np.ndarray,
        values: np.ndarray,
        value_masks: np.ndarray,
        indices: np.ndarray,
    ) -> None:
        self.states = states
        self.moves = moves
        self.values = values
        self.value_masks = value_masks
        self.indices = indices

    def __len__(self) -> int:
        return int(self.indices.size)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        sample_index = int(self.indices[index])
        state = torch.from_numpy(self.states[sample_index].astype(np.float32, copy=False))
        move = torch.tensor(int(self.moves[sample_index]), dtype=torch.long)
        value = torch.tensor(float(self.values[sample_index]), dtype=torch.float32)
        value_mask = torch.tensor(float(self.value_masks[sample_index]), dtype=torch.float32)
        return state, move, value, value_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a small policy/value network.")
    parser.add_argument("--input", required=True, type=Path, help="Policy dataset .npz")
    parser.add_argument("--output", required=True, type=Path, help="Model checkpoint path")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--min-learning-rate", type=float, default=1e-5)
    parser.add_argument("--value-loss-weight", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=20260518)
    return parser.parse_args()


def split_by_game(game_ids: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    if len(loader.dataset) == 0:
        return {
            "policy_loss": 0.0,
            "top1": 0.0,
            "top3": 0.0,
            "top5": 0.0,
            "value_loss": 0.0,
            "value_mae": 0.0,
        }
    policy_criterion = nn.CrossEntropyLoss()
    value_criterion = nn.MSELoss()
    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_top1 = 0
    total_top3 = 0
    total_top5 = 0
    total_value_mae = 0.0
    total = 0
    total_value_count = 0
    model.eval()
    with torch.inference_mode():
        for states, moves, values, value_masks in loader:
            states = states.to(device)
            moves = moves.to(device)
            values = values.to(device)
            value_masks = value_masks.to(device)
            logits, predicted_values = model(states)
            policy_loss = policy_criterion(logits, moves)
            total_policy_loss += float(policy_loss) * states.size(0)
            topk = torch.topk(logits, k=5, dim=1).indices
            targets = moves.unsqueeze(1)
            total_top1 += int((topk[:, :1] == targets).any(dim=1).sum())
            total_top3 += int((topk[:, :3] == targets).any(dim=1).sum())
            total_top5 += int((topk == targets).any(dim=1).sum())
            total += int(states.size(0))

            valid = value_masks > 0
            if valid.any():
                value_loss = value_criterion(predicted_values[valid], values[valid])
                valid_count = int(valid.sum())
                total_value_loss += float(value_loss) * valid_count
                total_value_mae += float(torch.abs(predicted_values[valid] - values[valid]).sum())
                total_value_count += valid_count
    return {
        "policy_loss": total_policy_loss / total,
        "top1": total_top1 / total,
        "top3": total_top3 / total,
        "top5": total_top5 / total,
        "value_loss": total_value_loss / max(total_value_count, 1),
        "value_mae": total_value_mae / max(total_value_count, 1),
    }


def main() -> int:
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    data = np.load(args.input, allow_pickle=False)
    states = data["states"]
    moves = data["moves"]
    values = data["values"]
    value_masks = data["value_masks"] if "value_masks" in data.files else np.ones_like(values, dtype=np.float32)
    game_ids = data["game_ids"]
    orient_to_turn = bool(data["orient_to_turn"])
    train_indices, val_indices, test_indices = split_by_game(game_ids, args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader = DataLoader(
        PolicyValueDataset(states, moves, values, value_masks, train_indices),
        batch_size=args.batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        PolicyValueDataset(states, moves, values, value_masks, val_indices),
        batch_size=args.batch_size,
        shuffle=False,
    )
    test_loader = DataLoader(
        PolicyValueDataset(states, moves, values, value_masks, test_indices),
        batch_size=args.batch_size,
        shuffle=False,
    )

    model = SmallPolicyValueNet(MOVE_LABELS).to(device)
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
    value_criterion = nn.MSELoss()
    best_val_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, float | int]] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total = 0
        for batch_states, batch_moves, batch_values, batch_value_masks in train_loader:
            batch_states = batch_states.to(device)
            batch_moves = batch_moves.to(device)
            batch_values = batch_values.to(device)
            batch_value_masks = batch_value_masks.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits, predicted_values = model(batch_states)
            policy_loss = policy_criterion(logits, batch_moves)
            valid_values = batch_value_masks > 0
            if valid_values.any():
                value_loss = value_criterion(predicted_values[valid_values], batch_values[valid_values])
            else:
                value_loss = predicted_values.sum() * 0
            loss = policy_loss + args.value_loss_weight * value_loss
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
                "val_value_loss": val_metrics["value_loss"],
                "val_value_mae": val_metrics["value_mae"],
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
                    "val_value_loss": round(val_metrics["value_loss"], 6),
                    "val_value_mae": round(val_metrics["value_mae"], 6),
                    "value_loss_weight": args.value_loss_weight,
                },
                ensure_ascii=False,
            )
        )
        combined_val_loss = val_metrics["policy_loss"] + args.value_loss_weight * val_metrics["value_loss"]
        if combined_val_loss < best_val_loss:
            best_val_loss = combined_val_loss
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
                "value_labeled_samples": int(value_masks.sum()),
                "value_unlabeled_samples": int(value_masks.size - value_masks.sum()),
            },
            "value_loss_weight": args.value_loss_weight,
            "optimizer": "AdamW",
            "learning_rate": args.learning_rate,
            "min_learning_rate": args.min_learning_rate,
            "weight_decay": args.weight_decay,
            "test_metrics": {
                "policy_loss": test_metrics["policy_loss"],
                "accuracy": test_metrics["top1"],
                "top3_accuracy": test_metrics["top3"],
                "top5_accuracy": test_metrics["top5"],
                "value_loss": test_metrics["value_loss"],
                "value_mae": test_metrics["value_mae"],
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
                "test_value_loss": round(test_metrics["value_loss"], 6),
                "test_value_mae": round(test_metrics["value_mae"], 6),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
