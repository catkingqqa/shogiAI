"""將棋 HalfKP NNUE 局面評估模型。

模型分別維護先手王與後手王視角的累加器，兩邊共享權重，再依目前手番
調整串接順序，最後輸出不受範圍限制的 logit。正值表示目前手番較有利。
搜尋分數由 logit 換算；勝率則使用 sigmoid(logit) 換算。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cshogi
import torch
from torch import nn

BOARD_SQUARES = 81
PIECE_TYPE_COUNT = 14
HAND_PIECE_COUNT = 7
HAND_BUCKETS = 19
SIDE_COUNT = 2
MODEL_TYPE_HALFKP = "halfkp"
MODEL_TYPE_LEGACY = "legacy_sparse"

# HalfKP 的「棋子」部分不包含兩枚王；王的位置會另外編入每個王－棋子特徵。
NON_KING_PIECE_TYPES = tuple(piece_type for piece_type in range(1, PIECE_TYPE_COUNT + 1) if piece_type != cshogi.KING)
PIECE_TYPE_TO_SLOT = {piece_type: slot for slot, piece_type in enumerate(NON_KING_PIECE_TYPES)}
PIECE_TYPE_TO_HAND_PIECE = {
    int(cshogi.hand_piece_to_piece_type(hand_piece)): hand_piece for hand_piece in range(HAND_PIECE_COUNT)
}
BOARD_PIECE_FEATURES = SIDE_COUNT * len(NON_KING_PIECE_TYPES) * BOARD_SQUARES
HAND_PIECE_FEATURE_OFFSET = BOARD_PIECE_FEATURES
HAND_PIECE_FEATURES = SIDE_COUNT * HAND_PIECE_COUNT * HAND_BUCKETS
PIECE_FEATURES = BOARD_PIECE_FEATURES + HAND_PIECE_FEATURES
HALFKP_FEATURES = BOARD_SQUARES * PIECE_FEATURES

# 保留原模型使用的常數，讓既有 checkpoint 仍可載入。
LEGACY_BOARD_FEATURES = SIDE_COUNT * PIECE_TYPE_COUNT * BOARD_SQUARES
LEGACY_HAND_FEATURE_OFFSET = LEGACY_BOARD_FEATURES
LEGACY_HAND_FEATURES = SIDE_COUNT * HAND_PIECE_COUNT * HAND_BUCKETS
LEGACY_TURN_FEATURE_OFFSET = LEGACY_HAND_FEATURE_OFFSET + LEGACY_HAND_FEATURES
LEGACY_TOTAL_FEATURES = LEGACY_TURN_FEATURE_OFFSET + 1


def piece_color(piece: int) -> int | None:
    if piece == cshogi.NONE:
        return None
    return cshogi.WHITE if piece >= 17 else cshogi.BLACK


def orient_square(square: int, perspective: int) -> int:
    return 80 - square if perspective == cshogi.WHITE else square


def piece_board_feature_index(side: int, piece_type: int, square: int) -> int:
    slot = PIECE_TYPE_TO_SLOT[piece_type]
    return (side * len(NON_KING_PIECE_TYPES) + slot) * BOARD_SQUARES + square


def piece_hand_feature_index(side: int, hand_piece: int, count_bucket: int) -> int:
    return HAND_PIECE_FEATURE_OFFSET + ((side * HAND_PIECE_COUNT + hand_piece) * HAND_BUCKETS + count_bucket)


def halfkp_board_index(
    perspective: int,
    king_square: int,
    piece_owner: int,
    piece_type: int,
    piece_square: int,
) -> int:
    """建立單一盤面棋子的 HalfKP 特徵編號。"""
    view_king = orient_square(king_square, perspective)
    view_piece = orient_square(piece_square, perspective)
    side = 0 if piece_owner == perspective else 1
    return view_king * PIECE_FEATURES + piece_board_feature_index(side, piece_type, view_piece)


def halfkp_hand_index(
    perspective: int,
    king_square: int,
    hand_owner: int,
    hand_piece: int,
    count: int,
) -> int:
    """建立單一持駒數量狀態的 HalfKP 特徵編號。"""
    view_king = orient_square(king_square, perspective)
    side = 0 if hand_owner == perspective else 1
    bucket = min(max(int(count), 0), HAND_BUCKETS - 1)
    return view_king * PIECE_FEATURES + piece_hand_feature_index(side, hand_piece, bucket)


def halfkp_feature_indices(board: cshogi.Board, perspective: int) -> list[int]:
    """取得指定玩家視角下，目前啟用的 HalfKP 特徵編號。
    """
    king_square = int(board.king_square(perspective))
    if not 0 <= king_square < BOARD_SQUARES:
        raise ValueError(f"missing king for perspective={perspective}")
    king_square = orient_square(king_square, perspective)
    king_offset = king_square * PIECE_FEATURES
    indices: list[int] = []

    for square, piece in enumerate(board.pieces):
        color = piece_color(int(piece))
        if color is None:
            continue
        piece_type = int(board.piece_type(square))
        if piece_type == cshogi.KING or piece_type not in PIECE_TYPE_TO_SLOT:
            continue
        side = 0 if color == perspective else 1
        view_square = orient_square(square, perspective)
        indices.append(king_offset + piece_board_feature_index(side, piece_type, view_square))

    black_hands, white_hands = board.pieces_in_hand
    own_hands = black_hands if perspective == cshogi.BLACK else white_hands
    opponent_hands = white_hands if perspective == cshogi.BLACK else black_hands
    for side, hands in enumerate((own_hands, opponent_hands)):
        for hand_piece, count in enumerate(hands):
            bucket = min(int(count), HAND_BUCKETS - 1)
            indices.append(king_offset + piece_hand_feature_index(side, hand_piece, bucket))
    return indices


def active_feature_indices(board: cshogi.Board, orient_to_turn: bool = True) -> list[int]:
    """原模型的特徵編碼器，只保留給既有 checkpoint 使用。"""
    turn = board.turn
    indices: list[int] = []
    for square, piece in enumerate(board.pieces):
        color = piece_color(int(piece))
        if color is None:
            continue
        piece_type = int(board.piece_type(square))
        if not 1 <= piece_type <= PIECE_TYPE_COUNT:
            continue
        side = (0 if color == turn else 1) if orient_to_turn else (0 if color == cshogi.BLACK else 1)
        view_square = 80 - square if orient_to_turn and turn == cshogi.WHITE else square
        indices.append((side * PIECE_TYPE_COUNT + piece_type - 1) * BOARD_SQUARES + view_square)

    black_hands, white_hands = board.pieces_in_hand
    if orient_to_turn:
        own_hands = black_hands if turn == cshogi.BLACK else white_hands
        opponent_hands = white_hands if turn == cshogi.BLACK else black_hands
    else:
        own_hands, opponent_hands = black_hands, white_hands
    for side, hands in enumerate((own_hands, opponent_hands)):
        for hand_piece, count in enumerate(hands):
            bucket = min(int(count), HAND_BUCKETS - 1)
            indices.append(LEGACY_HAND_FEATURE_OFFSET + ((side * HAND_PIECE_COUNT + hand_piece) * HAND_BUCKETS + bucket))
    if not orient_to_turn and turn == cshogi.WHITE:
        indices.append(LEGACY_TURN_FEATURE_OFFSET)
    return indices


class ClippedReLU(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.clamp(x, 0.0, 1.0)


class ShogiNNUE(nn.Module):
    """具有六個權重層的 HalfKP 網路。
    先後手視角分別執行共享的 HalfKP -> 128，再依目前手番排序並串接，
    後續結構為 256 -> 256 -> 128 -> 64 -> 32 -> 1。
    """

    def __init__(
        self,
        feature_count: int = HALFKP_FEATURES,
        accumulator_size: int = 128,
        hidden_sizes: tuple[int, ...] = (256, 128, 64, 32),
    ) -> None:
        super().__init__()
        if not hidden_sizes:
            raise ValueError("hidden_sizes must not be empty")
        self.feature_count = feature_count
        self.accumulator_size = accumulator_size
        self.hidden_sizes = tuple(hidden_sizes)
        self.feature_transformer = nn.EmbeddingBag(feature_count, accumulator_size, mode="sum", sparse=False)
        self.feature_bias = nn.Parameter(torch.zeros(accumulator_size))
        self.feature_activation = ClippedReLU()

        layers: list[nn.Module] = []
        in_features = accumulator_size * 2
        for out_features in self.hidden_sizes:
            layers.extend((nn.Linear(in_features, out_features), ClippedReLU()))
            in_features = out_features
        layers.append(nn.Linear(in_features, 1))
        self.layers = nn.Sequential(*layers)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        nn.init.normal_(self.feature_transformer.weight, mean=0.0, std=0.01)
        nn.init.zeros_(self.feature_bias)
        for module in self.layers:
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)

    def forward(
        self,
        black_indices: torch.Tensor,
        black_offsets: torch.Tensor,
        white_indices: torch.Tensor,
        white_offsets: torch.Tensor,
        side_to_move: torch.Tensor,
    ) -> torch.Tensor:
        black = self.feature_activation(self.feature_transformer(black_indices, black_offsets) + self.feature_bias)
        white = self.feature_activation(self.feature_transformer(white_indices, white_offsets) + self.feature_bias)
        return self.forward_from_accumulators(black, white, side_to_move, already_activated=True)

    def forward_from_accumulators(
        self,
        black: torch.Tensor,
        white: torch.Tensor,
        side_to_move: torch.Tensor,
        already_activated: bool = False,
    ) -> torch.Tensor:
        """由雙視角累加器執行後段網路，供增量推論使用。"""
        if not already_activated:
            black = self.feature_activation(black)
            white = self.feature_activation(white)
        is_white = side_to_move.to(dtype=torch.bool).unsqueeze(1)
        current = torch.where(is_white, white, black)
        opponent = torch.where(is_white, black, white)
        return self.layers(torch.cat((current, opponent), dim=1)).squeeze(1)


@dataclass
class _AccumulatorSnapshot:
    black: torch.Tensor
    white: torch.Tensor
    turn: int
    board_hash: int


class IncrementalNNUEState:
    """與搜尋棋盤同步的雙視角 NNUE 增量累加器。
    """

    def __init__(self, evaluator: "NNUEEvaluator", board: cshogi.Board) -> None:
        if evaluator.model_type != MODEL_TYPE_HALFKP or not isinstance(evaluator.model, ShogiNNUE):
            raise ValueError("增量累加器只支援 HalfKP 模型")
        self.evaluator = evaluator
        self.black = evaluator._build_accumulator(board, cshogi.BLACK)
        self.white = evaluator._build_accumulator(board, cshogi.WHITE)
        self.turn = int(board.turn)
        self.board_hash = int(board.zobrist_hash())
        self._stack: list[_AccumulatorSnapshot] = []

    def _check_board(self, board: cshogi.Board) -> None:
        if int(board.turn) != self.turn or int(board.zobrist_hash()) != self.board_hash:
            raise RuntimeError("棋盤與 NNUE 增量狀態不同步；請只透過 state.push/pop 走棋")

    def _apply_indices(self, perspective: int, removed: list[int], added: list[int]) -> None:
        accumulator = self.black if perspective == cshogi.BLACK else self.white
        weights = self.evaluator.model.feature_transformer.weight
        if removed:
            indices = torch.tensor(removed, dtype=torch.long, device=self.evaluator.device)
            accumulator.sub_(weights.index_select(0, indices).sum(dim=0))
        if added:
            indices = torch.tensor(added, dtype=torch.long, device=self.evaluator.device)
            accumulator.add_(weights.index_select(0, indices).sum(dim=0))

    @torch.inference_mode()
    def push(self, board: cshogi.Board, move: int) -> None:
        """走一步棋，僅更新受影響的 HalfKP 特徵。"""
        self._check_board(board)
        self._stack.append(
            _AccumulatorSnapshot(self.black.clone(), self.white.clone(), self.turn, self.board_hash)
        )

        mover = int(board.turn)
        to_square = int(cshogi.move_to(move))
        is_drop = bool(cshogi.move_is_drop(move))
        if is_drop:
            hand_piece = int(cshogi.move_drop_hand_piece(move))
            moved_piece_type = int(cshogi.hand_piece_to_piece_type(hand_piece))
            old_hand_count = int(board.pieces_in_hand[mover][hand_piece])
            from_square = None
            captured_piece_type = None
        else:
            from_square = int(cshogi.move_from(move))
            moved_piece_type = int(board.piece_type(from_square))
            captured = int(board.piece_type(to_square))
            captured_piece_type = captured if captured != cshogi.NONE else None
            hand_piece = None
            old_hand_count = None

        board.push(move)
        try:
            if moved_piece_type == cshogi.KING:
                # 王的位置是該視角所有 HalfKP 特徵的一部分，必須重建該側。
                if mover == cshogi.BLACK:
                    self.black = self.evaluator._build_accumulator(board, cshogi.BLACK)
                else:
                    self.white = self.evaluator._build_accumulator(board, cshogi.WHITE)

                # 另一個王視角不包含移動中的王，但吃子與持駒仍需增量更新。
                if captured_piece_type is not None:
                    perspective = int(cshogi.opponent(mover))
                    king_square = int(board.king_square(perspective))
                    demoted_type = captured_piece_type - 8 if captured_piece_type > cshogi.KING else captured_piece_type
                    captured_hand_piece = PIECE_TYPE_TO_HAND_PIECE[demoted_type]
                    new_count = int(board.pieces_in_hand[mover][captured_hand_piece])
                    removed = [
                        halfkp_board_index(
                            perspective,
                            king_square,
                            cshogi.opponent(mover),
                            captured_piece_type,
                            to_square,
                        ),
                        halfkp_hand_index(
                            perspective, king_square, mover, captured_hand_piece, new_count - 1
                        ),
                    ]
                    added = [
                        halfkp_hand_index(perspective, king_square, mover, captured_hand_piece, new_count)
                    ]
                    self._apply_indices(perspective, removed, added)
            else:
                promoted_piece_type = moved_piece_type + 8 if cshogi.move_is_promotion(move) else moved_piece_type
                for perspective in (cshogi.BLACK, cshogi.WHITE):
                    king_square = int(board.king_square(perspective))
                    removed: list[int] = []
                    added: list[int] = []

                    if is_drop:
                        assert hand_piece is not None and old_hand_count is not None
                        removed.append(halfkp_hand_index(perspective, king_square, mover, hand_piece, old_hand_count))
                        added.append(halfkp_hand_index(perspective, king_square, mover, hand_piece, old_hand_count - 1))
                    else:
                        assert from_square is not None
                        removed.append(halfkp_board_index(perspective, king_square, mover, moved_piece_type, from_square))

                    added.append(halfkp_board_index(perspective, king_square, mover, promoted_piece_type, to_square))

                    if captured_piece_type is not None:
                        removed.append(
                            halfkp_board_index(
                                perspective,
                                king_square,
                                cshogi.opponent(mover),
                                captured_piece_type,
                                to_square,
                            )
                        )
                        demoted_type = captured_piece_type - 8 if captured_piece_type > cshogi.KING else captured_piece_type
                        captured_hand_piece = PIECE_TYPE_TO_HAND_PIECE[demoted_type]
                        new_count = int(board.pieces_in_hand[mover][captured_hand_piece])
                        removed.append(
                            halfkp_hand_index(
                                perspective, king_square, mover, captured_hand_piece, new_count - 1
                            )
                        )
                        added.append(
                            halfkp_hand_index(perspective, king_square, mover, captured_hand_piece, new_count)
                        )
                    self._apply_indices(perspective, removed, added)

            self.turn = int(board.turn)
            self.board_hash = int(board.zobrist_hash())
        except Exception:
            board.pop()
            snapshot = self._stack.pop()
            self.black, self.white = snapshot.black, snapshot.white
            self.turn, self.board_hash = snapshot.turn, snapshot.board_hash
            raise

    def pop(self, board: cshogi.Board) -> int:
        """回復一步棋及其增量累加器。"""
        self._check_board(board)
        if not self._stack:
            raise IndexError("NNUE 增量狀態已位於根節點")
        move = int(board.pop())
        snapshot = self._stack.pop()
        self.black, self.white = snapshot.black, snapshot.white
        self.turn, self.board_hash = snapshot.turn, snapshot.board_hash
        self._check_board(board)
        return move


class LegacyShogiNNUE(nn.Module):
    def __init__(self, feature_count: int, accumulator_size: int, hidden_size: int) -> None:
        super().__init__()
        self.accumulator = nn.EmbeddingBag(feature_count, accumulator_size, mode="sum", sparse=False)
        self.layers = nn.Sequential(
            nn.Linear(accumulator_size, hidden_size),
            ClippedReLU(),
            nn.Linear(hidden_size, hidden_size // 2),
            ClippedReLU(),
            nn.Linear(hidden_size // 2, 1),
            nn.Tanh(),
        )

    def forward(self, indices: torch.Tensor, offsets: torch.Tensor) -> torch.Tensor:
        return self.layers(self.accumulator(indices, offsets)).squeeze(1)


@dataclass(frozen=True)
class NNUEConfig:
    model_type: str = MODEL_TYPE_HALFKP
    accumulator_size: int = 128
    hidden_sizes: tuple[int, ...] = (256, 128, 64, 32)
    score_scale: int = 600
    max_search_score: int = 30_000


class NNUEEvaluator:
    """載入 checkpoint，並提供目前手番視角的搜尋評估分數。"""

    def __init__(self, model_path: Path | str, device: str | None = None, cache_size: int = 100_000) -> None:
        self.model_path = Path(model_path)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=True)
        config = checkpoint.get("config", {})
        self.model_type = str(config.get("model_type", MODEL_TYPE_LEGACY))
        self.score_scale = int(config.get("score_scale", 1200 if self.model_type == MODEL_TYPE_LEGACY else 600))
        self.max_search_score = int(config.get("max_search_score", 30_000))

        if self.model_type == MODEL_TYPE_HALFKP:
            self.model: nn.Module = ShogiNNUE(
                feature_count=int(config.get("feature_count", HALFKP_FEATURES)),
                accumulator_size=int(config.get("accumulator_size", 128)),
                hidden_sizes=tuple(int(value) for value in config.get("hidden_sizes", (256, 128, 64, 32))),
            )
        else:
            self.orient_to_turn = bool(config.get("orient_to_turn", True))
            self.model = LegacyShogiNNUE(
                feature_count=int(config.get("feature_count", LEGACY_TOTAL_FEATURES)),
                accumulator_size=int(config.get("accumulator_size", 256)),
                hidden_size=int(config.get("hidden_size", 128)),
            )
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.to(self.device)
        self.model.eval()
        self.cache_size = max(0, cache_size)
        self._cache: dict[int, int] = {}

    @torch.inference_mode()
    def _build_accumulator(self, board: cshogi.Board, perspective: int) -> torch.Tensor:
        """由完整局面建立一個未套用 ClippedReLU 的累加器。"""
        if not isinstance(self.model, ShogiNNUE):
            raise ValueError("累加器只支援 HalfKP 模型")
        features = halfkp_feature_indices(board, perspective)
        indices = torch.tensor(features, dtype=torch.long, device=self.device)
        return self.model.feature_transformer.weight.index_select(0, indices).sum(dim=0) + self.model.feature_bias

    def create_state(self, board: cshogi.Board) -> IncrementalNNUEState:
        """在搜尋根節點建立一次完整累加器，之後以 push/pop 增量維護。"""
        return IncrementalNNUEState(self, board)

    @torch.inference_mode()
    def raw_output_for_state(self, state: IncrementalNNUEState) -> float:
        """直接從增量累加器取得目前手番視角的 logit。"""
        if state.evaluator is not self or not isinstance(self.model, ShogiNNUE):
            raise ValueError("增量狀態不屬於這個 NNUE 評估器")
        output = self.model.forward_from_accumulators(
            state.black.unsqueeze(0),
            state.white.unsqueeze(0),
            torch.tensor([state.turn], dtype=torch.long, device=self.device),
        )
        return float(output[0].cpu())

    def evaluate_state(self, state: IncrementalNNUEState) -> int:
        """取得增量狀態的搜尋分數，不重新掃描棋盤。"""
        if self.cache_size > 0 and state.board_hash in self._cache:
            return self._cache[state.board_hash]
        raw = self.raw_output_for_state(state)
        score = int(round(raw * self.score_scale))
        score = max(-self.max_search_score, min(self.max_search_score, score))
        if self.cache_size > 0:
            if len(self._cache) >= self.cache_size:
                self._cache.clear()
            self._cache[state.board_hash] = score
        return score

    def raw_output_for_board(self, board: cshogi.Board) -> float:
        if self.model_type == MODEL_TYPE_LEGACY:
            features = active_feature_indices(board, orient_to_turn=self.orient_to_turn)
            indices = torch.tensor(features, dtype=torch.long, device=self.device)
            offsets = torch.tensor([0], dtype=torch.long, device=self.device)
            with torch.inference_mode():
                return float(self.model(indices, offsets)[0].detach().cpu())

        black_features = halfkp_feature_indices(board, cshogi.BLACK)
        white_features = halfkp_feature_indices(board, cshogi.WHITE)
        with torch.inference_mode():
            output = self.model(
                torch.tensor(black_features, dtype=torch.long, device=self.device),
                torch.tensor([0], dtype=torch.long, device=self.device),
                torch.tensor(white_features, dtype=torch.long, device=self.device),
                torch.tensor([0], dtype=torch.long, device=self.device),
                torch.tensor([board.turn], dtype=torch.long, device=self.device),
            )
        return float(output[0].detach().cpu())

    def win_probability_for_board(self, board: cshogi.Board) -> float:
        raw = self.raw_output_for_board(board)
        if self.model_type == MODEL_TYPE_LEGACY:
            return (raw + 1.0) / 2.0
        return float(torch.sigmoid(torch.tensor(raw)))

    def value_for_board(self, board: cshogi.Board) -> float:
        return 2.0 * self.win_probability_for_board(board) - 1.0

    def evaluate(self, board: cshogi.Board) -> int:
        key = int(board.zobrist_hash())
        if self.cache_size > 0 and key in self._cache:
            return self._cache[key]
        raw = self.raw_output_for_board(board)
        if self.model_type == MODEL_TYPE_LEGACY:
            score = int(round(raw * self.score_scale))
        else:
            score = int(round(raw * self.score_scale))
            score = max(-self.max_search_score, min(self.max_search_score, score))
        if self.cache_size > 0:
            if len(self._cache) >= self.cache_size:
                self._cache.clear()
            self._cache[key] = score
        return score


def board_from_meta_json(raw_meta: str | bytes) -> cshogi.Board:
    meta = json.loads(raw_meta.decode("utf-8") if isinstance(raw_meta, bytes) else str(raw_meta))
    return cshogi.Board(meta["sfen"])
