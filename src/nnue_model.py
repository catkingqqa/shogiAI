from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cshogi
import torch
from torch import nn

from csa_preprocess import HAND_PIECE_COUNT, PIECE_TYPE_COUNT, SQUARE_N, orient_square, piece_color


PIECE_OWNER_TYPES = PIECE_TYPE_COUNT * 2
KING_RELATIVE_BANKS = 2
KING_RELATIVE_FEATURES = KING_RELATIVE_BANKS * SQUARE_N * PIECE_OWNER_TYPES * SQUARE_N
HAND_FEATURES = HAND_PIECE_COUNT * 2
NNUE_FEATURES = KING_RELATIVE_FEATURES + HAND_FEATURES


def nnue_feature_indices(board: cshogi.Board, orient_to_turn: bool = True) -> list[int]:
    turn = board.turn
    own_king = orient_square(board.king_square(turn), turn, orient_to_turn)
    enemy = cshogi.WHITE if turn == cshogi.BLACK else cshogi.BLACK
    opp_king = orient_square(board.king_square(enemy), turn, orient_to_turn)
    features: list[int] = []

    bank_size = SQUARE_N * PIECE_OWNER_TYPES * SQUARE_N
    for square, piece in enumerate(board.pieces):
        color = piece_color(int(piece))
        if color is None:
            continue
        piece_type = int(board.piece_type(square))
        if not 1 <= piece_type <= PIECE_TYPE_COUNT:
            continue
        view_square = orient_square(square, turn, orient_to_turn)
        owner_offset = 0 if color == turn else PIECE_TYPE_COUNT
        piece_code = owner_offset + piece_type - 1
        features.append((own_king * PIECE_OWNER_TYPES + piece_code) * SQUARE_N + view_square)
        features.append(bank_size + (opp_king * PIECE_OWNER_TYPES + piece_code) * SQUARE_N + view_square)

    black_hands, white_hands = board.pieces_in_hand
    own_hands = black_hands if turn == cshogi.BLACK else white_hands
    opp_hands = white_hands if turn == cshogi.BLACK else black_hands
    hand_offset = KING_RELATIVE_FEATURES
    for hand_index, count in enumerate(own_hands):
        features.extend([hand_offset + hand_index] * int(count))
    for hand_index, count in enumerate(opp_hands):
        features.extend([hand_offset + HAND_PIECE_COUNT + hand_index] * int(count))
    return features


class SparseNNUEValueNet(nn.Module):
    def __init__(self, feature_count: int = NNUE_FEATURES, hidden_size: int = 64) -> None:
        super().__init__()
        self.feature_count = feature_count
        self.hidden_size = hidden_size
        self.feature_transform = nn.EmbeddingBag(feature_count, hidden_size, mode="sum")
        self.output = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ClippedReLU() if hasattr(nn, "ClippedReLU") else nn.ReLU(),
            nn.Linear(64, 1),
            nn.Tanh(),
        )

    def forward(self, feature_indices: torch.Tensor, offsets: torch.Tensor) -> torch.Tensor:
        hidden = self.feature_transform(feature_indices, offsets)
        hidden = torch.clamp(hidden, min=0.0, max=1.0)
        return self.output(hidden).squeeze(1)


@dataclass(frozen=True)
class NNUEValuePredictor:
    model_path: Path
    device: torch.device
    model: SparseNNUEValueNet
    orient_to_turn: bool

    @classmethod
    def load(cls, model_path: Path, device: str | None = None) -> "NNUEValuePredictor":
        target_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        checkpoint = torch.load(Path(model_path), map_location=target_device, weights_only=True)
        model = SparseNNUEValueNet(
            int(checkpoint.get("feature_count", NNUE_FEATURES)),
            int(checkpoint.get("hidden_size", 64)),
        )
        model.load_state_dict(checkpoint["model_state"])
        model.to(target_device)
        model.eval()
        return cls(
            model_path=Path(model_path),
            device=target_device,
            model=model,
            orient_to_turn=bool(checkpoint.get("orient_to_turn", True)),
        )

    def value_for_board(self, board: cshogi.Board) -> float:
        features = nnue_feature_indices(board, orient_to_turn=self.orient_to_turn)
        indices = torch.tensor(features, dtype=torch.long, device=self.device)
        offsets = torch.tensor([0], dtype=torch.long, device=self.device)
        with torch.inference_mode():
            return float(self.model(indices, offsets)[0].detach().cpu())
