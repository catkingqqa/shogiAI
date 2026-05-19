from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cshogi
import numpy as np
import torch
from torch import nn

from csa_preprocess import MOVE_LABELS, encode_move, encode_state


class SmallPolicyValueNet(nn.Module):
    def __init__(self, move_label_count: int = MOVE_LABELS) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(43, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
        )
        self.policy_head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 9 * 9, 512),
            nn.ReLU(inplace=True),
            nn.Linear(512, move_label_count),
        )
        self.value_head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 9 * 9, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 1),
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.features(x)
        return self.policy_head(features), self.value_head(features).squeeze(1)


@dataclass(frozen=True)
class PolicyCandidate:
    move: int
    label: int
    score: float
    probability: float


class PolicyValuePredictor:
    def __init__(self, model_path: Path, device: str | None = None, cache_size: int = 20_000) -> None:
        self.model_path = Path(model_path)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=True)
        self.model = SmallPolicyValueNet(int(checkpoint.get("move_label_count", MOVE_LABELS)))
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.to(self.device)
        self.model.eval()
        self.orient_to_turn = bool(checkpoint.get("orient_to_turn", True))
        self.cache_size = max(0, cache_size)
        self._prediction_cache: dict[int, tuple[torch.Tensor, float]] = {}

    def predict_for_board(self, board: cshogi.Board) -> tuple[torch.Tensor, float]:
        cache_key = int(board.zobrist_hash())
        if self.cache_size > 0 and cache_key in self._prediction_cache:
            return self._prediction_cache[cache_key]

        state = encode_state(board, orient_to_turn=self.orient_to_turn).astype(np.float32, copy=False)
        tensor = torch.from_numpy(state).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            logits, value = self.model(tensor)
            prediction = (logits[0].detach().cpu(), float(value[0].detach().cpu()))

        if self.cache_size > 0:
            if len(self._prediction_cache) >= self.cache_size:
                self._prediction_cache.clear()
            self._prediction_cache[cache_key] = prediction
        return prediction

    def value_for_board(self, board: cshogi.Board) -> float:
        _, value = self.predict_for_board(board)
        return value

    def rank_legal_moves(
        self,
        board: cshogi.Board,
        legal_moves: Iterable[int] | None = None,
    ) -> list[PolicyCandidate]:
        moves = list(board.legal_moves if legal_moves is None else legal_moves)
        if not moves:
            return []

        logits, _ = self.predict_for_board(board)
        labels = [encode_move(move, board.turn, orient_to_turn=self.orient_to_turn) for move in moves]
        legal_logits = torch.tensor([float(logits[label]) for label in labels], dtype=torch.float32)
        probabilities = torch.softmax(legal_logits, dim=0)
        ranked = [
            PolicyCandidate(
                move=move,
                label=label,
                score=float(legal_logits[index]),
                probability=float(probabilities[index]),
            )
            for index, (move, label) in enumerate(zip(moves, labels, strict=True))
        ]
        return sorted(ranked, key=lambda item: item.score, reverse=True)
