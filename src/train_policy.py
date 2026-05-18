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


class PolicyValueDataset(Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]):
    def __init__(self, states: np.ndarray, moves: np.ndarray, values: np.ndarray, indices: np.ndarray) -> None:
        self.states = states
        self.moves = moves
        self.values = values
        self.indices = indices

    def __len__(self) -> int:
        return int(self.indices.size)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        sample_index = int(self.indices[index])
        state = torch.from_numpy(self.states[sample_index].astype(np.float32, copy=False))
        move = torch.tensor(int(self.moves[sample_index]), dtype=torch.long)
        value = torch.tensor(float(self.values[sample_index]), dtype=torch.float32)
        return state, move, value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a small policy/value network.")
    parser.add_argument("--input", required=True, type=Path, help="Policy dataset .npz")
    parser.add_argument("--output", required=True, type=Path, help="Model checkpoint path")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
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


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float, float, float]:
    if len(loader.dataset) == 0:
        return 0.0, 0.0, 0.0, 0.0
    policy_criterion = nn.CrossEntropyLoss()
    value_criterion = nn.MSELoss()
    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_correct = 0
    total_value_mae = 0.0
    total = 0
    model.eval()
    with torch.inference_mode():
        for states, moves, values in loader:
            states = states.to(device)
            moves = moves.to(device)
            values = values.to(device)
            logits, predicted_values = model(states)
            policy_loss = policy_criterion(logits, moves)
            value_loss = value_criterion(predicted_values, values)
            total_policy_loss += float(policy_loss) * states.size(0)
            total_value_loss += float(value_loss) * states.size(0)
            total_correct += int((logits.argmax(dim=1) == moves).sum())
            total_value_mae += float(torch.abs(predicted_values - values).sum())
            total += int(states.size(0))
    return total_policy_loss / total, total_correct / total, total_value_loss / total, total_value_mae / total


def main() -> int:
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    data = np.load(args.input, allow_pickle=False)
    states = data["states"]
    moves = data["moves"]
    values = data["values"]
    game_ids = data["game_ids"]
    orient_to_turn = bool(data["orient_to_turn"])
    train_indices, val_indices, test_indices = split_by_game(game_ids, args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader = DataLoader(
        PolicyValueDataset(states, moves, values, train_indices),
        batch_size=args.batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        PolicyValueDataset(states, moves, values, val_indices),
        batch_size=args.batch_size,
        shuffle=False,
    )
    test_loader = DataLoader(
        PolicyValueDataset(states, moves, values, test_indices),
        batch_size=args.batch_size,
        shuffle=False,
    )

    model = SmallPolicyValueNet(MOVE_LABELS).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    policy_criterion = nn.CrossEntropyLoss()
    value_criterion = nn.MSELoss()
    best_val_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, float | int]] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total = 0
        for batch_states, batch_moves, batch_values in train_loader:
            batch_states = batch_states.to(device)
            batch_moves = batch_moves.to(device)
            batch_values = batch_values.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits, predicted_values = model(batch_states)
            policy_loss = policy_criterion(logits, batch_moves)
            value_loss = value_criterion(predicted_values, batch_values)
            loss = policy_loss + value_loss
            loss.backward()
            optimizer.step()
            total_loss += float(loss) * batch_states.size(0)
            total += int(batch_states.size(0))

        train_loss = total_loss / max(total, 1)
        val_policy_loss, val_acc, val_value_loss, val_value_mae = evaluate(model, val_loader, device)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_policy_loss": val_policy_loss,
                "val_accuracy": val_acc,
                "val_value_loss": val_value_loss,
                "val_value_mae": val_value_mae,
            }
        )
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "train_loss": round(train_loss, 6),
                    "val_policy_loss": round(val_policy_loss, 6),
                    "val_accuracy": round(val_acc, 6),
                    "val_value_loss": round(val_value_loss, 6),
                    "val_value_mae": round(val_value_mae, 6),
                },
                ensure_ascii=False,
            )
        )
        combined_val_loss = val_policy_loss + val_value_loss
        if combined_val_loss < best_val_loss:
            best_val_loss = combined_val_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    test_policy_loss, test_acc, test_value_loss, test_value_mae = evaluate(model, test_loader, device)

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
            "test_metrics": {
                "policy_loss": test_policy_loss,
                "accuracy": test_acc,
                "value_loss": test_value_loss,
                "value_mae": test_value_mae,
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
                "test_policy_loss": round(test_policy_loss, 6),
                "test_accuracy": round(test_acc, 6),
                "test_value_loss": round(test_value_loss, 6),
                "test_value_mae": round(test_value_mae, 6),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
