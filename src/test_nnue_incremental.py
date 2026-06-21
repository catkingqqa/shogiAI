"""驗證增量 NNUE 累加器與完整重算完全一致。"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import cshogi
import torch

from nnue_model import NNUEEvaluator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="隨機走棋並驗證 NNUE 增量累加器。")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--max-plies", type=int, default=300)
    parser.add_argument("--seed", type=int, default=11211213)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def assert_same(evaluator: NNUEEvaluator, board: cshogi.Board, state, context: str) -> None:
    black = evaluator._build_accumulator(board, cshogi.BLACK)
    white = evaluator._build_accumulator(board, cshogi.WHITE)
    if not torch.allclose(state.black, black, rtol=1e-5, atol=1e-4):
        difference = float((state.black - black).abs().max().cpu())
        raise AssertionError(f"{context}：先手累加器不一致，最大誤差={difference}")
    if not torch.allclose(state.white, white, rtol=1e-5, atol=1e-4):
        difference = float((state.white - white).abs().max().cpu())
        raise AssertionError(f"{context}：後手累加器不一致，最大誤差={difference}")

    incremental = evaluator.raw_output_for_state(state)
    complete = evaluator.raw_output_for_board(board)
    if abs(incremental - complete) > 1e-4:
        raise AssertionError(f"{context}：輸出不一致，incremental={incremental} complete={complete}")


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    evaluator = NNUEEvaluator(args.model, device=args.device, cache_size=0)
    counters = {"moves": 0, "captures": 0, "promotions": 0, "drops": 0, "king_moves": 0}

    for game_index in range(args.games):
        board = cshogi.Board()
        state = evaluator.create_state(board)
        assert_same(evaluator, board, state, f"game={game_index} root")
        played = 0

        for ply in range(args.max_plies):
            legal_moves = list(board.legal_moves)
            if not legal_moves:
                break
            move = rng.choice(legal_moves)
            if cshogi.move_is_drop(move):
                counters["drops"] += 1
            else:
                if int(board.piece_type(cshogi.move_from(move))) == cshogi.KING:
                    counters["king_moves"] += 1
                if int(board.piece_type(cshogi.move_to(move))) != cshogi.NONE:
                    counters["captures"] += 1
                if cshogi.move_is_promotion(move):
                    counters["promotions"] += 1

            state.push(board, move)
            played += 1
            counters["moves"] += 1
            assert_same(evaluator, board, state, f"game={game_index} ply={ply + 1} push")

        for remaining in range(played, 0, -1):
            state.pop(board)
            assert_same(evaluator, board, state, f"game={game_index} ply={remaining - 1} pop")

    print("增量 NNUE 驗證通過：" + " ".join(f"{key}={value}" for key, value in counters.items()))
    if not all(counters[key] > 0 for key in ("captures", "promotions", "drops", "king_moves")):
        print("警告：隨機測試未覆蓋所有特殊走法，請增加 --games 或 --max-plies。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
