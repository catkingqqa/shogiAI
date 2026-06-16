from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable

import cshogi

from ai_search import evaluate_position, repetition_key, search_best_move
from policy_model import PolicyPredictor


@dataclass(frozen=True)
class MatchEngine:
    name: str
    predictor: PolicyPredictor | None
    depth: int = 3
    time_limit_ms: int = 1000
    policy_order_ply: int = 2

    def order_moves(self, board: cshogi.Board, legal_moves: Iterable[int]) -> list[int]:
        if self.predictor is None:
            return list(legal_moves)
        return [candidate.move for candidate in self.predictor.rank_legal_moves(board, legal_moves)]


@dataclass
class GameResult:
    game: int
    black: str
    white: str
    result: str
    winner: str | None
    winner_side: str | None
    plies: int
    reason: str
    moves: list[str]
    new_score: float
    old_score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run head-to-head games between two policy models.")
    parser.add_argument("--old-model", type=Path, default=Path("out/policy_model.prev.pt"))
    parser.add_argument("--new-model", type=Path, default=Path("out/policy_model.pt"))
    parser.add_argument("--old-name", default="old")
    parser.add_argument("--new-name", default="new")
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--time-limit-ms", type=int, default=1000)
    parser.add_argument("--policy-order-ply", type=int, default=2)
    parser.add_argument("--max-plies", type=int, default=256)
    parser.add_argument(
        "--adjudicate-score",
        type=int,
        default=1000,
        help="At max plies, award win if one side leads by this evaluation score; 0 disables adjudication.",
    )
    parser.add_argument("--output-jsonl", type=Path, default=None)
    parser.add_argument("--no-policy", action="store_true", help="Compare pure traditional search without models.")
    return parser.parse_args()


def load_engine(
    name: str,
    model_path: Path | None,
    disabled: bool,
    depth: int = 3,
    time_limit_ms: int = 1000,
    policy_order_ply: int = 2,
) -> MatchEngine:
    if disabled or model_path is None:
        return MatchEngine(
            name=name,
            predictor=None,
            depth=depth,
            time_limit_ms=time_limit_ms,
            policy_order_ply=policy_order_ply,
        )
    if not model_path.is_file():
        raise FileNotFoundError(f"model not found: {model_path}")
    return MatchEngine(
        name=name,
        predictor=PolicyPredictor(model_path),
        depth=depth,
        time_limit_ms=time_limit_ms,
        policy_order_ply=policy_order_ply,
    )


def terminal_result(board: cshogi.Board) -> tuple[str, str | None, str | None, str] | None:
    legal_moves = list(board.legal_moves)
    if legal_moves:
        return None
    if board.is_check():
        winner_side = "white" if board.turn == cshogi.BLACK else "black"
        return "win", winner_side, winner_side, "checkmate"
    return "draw", None, None, "no legal moves"


def play_game(
    game_index: int,
    black_engine: MatchEngine,
    white_engine: MatchEngine,
    new_name: str,
    old_name: str,
    max_plies: int,
    adjudicate_score: int,
) -> GameResult:
    board = cshogi.Board()
    position_counts = {repetition_key(board): 1}
    moves: list[str] = []
    scores = {new_name: 0.0, old_name: 0.0}

    reason = "max plies"
    result = "draw"
    winner_name: str | None = None
    winner_side: str | None = None

    for _ in range(max_plies):
        terminal = terminal_result(board)
        if terminal is not None:
            result, winner_side, _, reason = terminal
            break
        if position_counts.get(repetition_key(board), 0) >= 4:
            result = "draw"
            reason = "sennichite"
            break

        engine = black_engine if board.turn == cshogi.BLACK else white_engine
        search = search_best_move(
            board,
            position_counts,
            engine.depth,
            engine.time_limit_ms,
            move_orderer=engine.order_moves if engine.predictor is not None else None,
            move_orderer_max_ply=engine.policy_order_ply,
        )
        if search.move is None:
            result = "draw"
            reason = "no selected move"
            break

        scores[engine.name] += search.score
        move_usi = cshogi.move_to_usi(search.move)
        moves.append(move_usi)
        board.push(search.move)
        key = repetition_key(board)
        position_counts[key] = position_counts.get(key, 0) + 1
    else:
        result, winner_side, reason = adjudicate_max_plies(board, adjudicate_score)

    if winner_side is not None:
        winner_name = black_engine.name if winner_side == "black" else white_engine.name

    return GameResult(
        game=game_index,
        black=black_engine.name,
        white=white_engine.name,
        result=result,
        winner=winner_name,
        winner_side=winner_side,
        plies=len(moves),
        reason=reason,
        moves=moves,
        new_score=scores[new_name],
        old_score=scores[old_name],
    )


def summarize(results: list[GameResult], new_name: str, old_name: str) -> dict[str, object]:
    new_wins = sum(1 for result in results if result.winner == new_name)
    old_wins = sum(1 for result in results if result.winner == old_name)
    draws = sum(1 for result in results if result.result == "draw")
    return {
        "games": len(results),
        "new": new_name,
        "old": old_name,
        "new_wins": new_wins,
        "old_wins": old_wins,
        "draws": draws,
        "new_score_rate": (new_wins + 0.5 * draws) / max(len(results), 1),
        "average_plies": sum(result.plies for result in results) / max(len(results), 1),
        "results": [asdict(result) for result in results],
    }


def adjudicate_max_plies(board: cshogi.Board, threshold: int) -> tuple[str, str | None, str]:
    if threshold <= 0:
        return "draw", None, "max plies"
    side_to_move_score = evaluate_position(board)
    black_score = side_to_move_score if board.turn == cshogi.BLACK else -side_to_move_score
    if black_score >= threshold:
        return "win", "black", f"max plies adjudication black +{black_score}"
    if black_score <= -threshold:
        return "win", "white", f"max plies adjudication white +{-black_score}"
    return "draw", None, f"max plies eval {black_score}"


def main() -> int:
    args = parse_args()
    old_engine = load_engine(
        args.old_name,
        args.old_model,
        args.no_policy,
        depth=args.depth,
        time_limit_ms=args.time_limit_ms,
        policy_order_ply=max(0, args.policy_order_ply),
    )
    new_engine = load_engine(
        args.new_name,
        args.new_model,
        args.no_policy,
        depth=args.depth,
        time_limit_ms=args.time_limit_ms,
        policy_order_ply=max(0, args.policy_order_ply),
    )

    results: list[GameResult] = []
    started = perf_counter()
    for game_index in range(1, args.games + 1):
        if game_index % 2 == 1:
            black_engine, white_engine = new_engine, old_engine
        else:
            black_engine, white_engine = old_engine, new_engine
        result = play_game(
            game_index=game_index,
            black_engine=black_engine,
            white_engine=white_engine,
            new_name=args.new_name,
            old_name=args.old_name,
            max_plies=args.max_plies,
            adjudicate_score=max(0, args.adjudicate_score),
        )
        results.append(result)
        print(
            json.dumps(
                {
                    "game": result.game,
                    "black": result.black,
                    "white": result.white,
                    "winner": result.winner,
                    "result": result.result,
                    "reason": result.reason,
                    "plies": result.plies,
                },
                ensure_ascii=False,
            )
        )

    summary = summarize(results, args.new_name, args.old_name)
    summary["seconds"] = round(perf_counter() - started, 3)
    if args.output_jsonl is not None:
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.output_jsonl.open("w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
            handle.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
