from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from time import monotonic

import cshogi


MATE_SCORE = 1_000_000
INF_SCORE = 10_000_000

PIECE_VALUES = {
    cshogi.PAWN: 100,
    cshogi.LANCE: 300,
    cshogi.KNIGHT: 320,
    cshogi.SILVER: 450,
    cshogi.GOLD: 500,
    cshogi.BISHOP: 700,
    cshogi.ROOK: 800,
    cshogi.KING: 0,
    cshogi.PROM_PAWN: 520,
    cshogi.PROM_LANCE: 520,
    cshogi.PROM_KNIGHT: 520,
    cshogi.PROM_SILVER: 520,
    cshogi.PROM_BISHOP: 900,
    cshogi.PROM_ROOK: 1_000,
}

HAND_VALUES = [100, 300, 320, 450, 500, 700, 800]


class SearchTimeout(Exception):
    pass


@dataclass(frozen=True)
class SearchResult:
    move: int | None
    score: int
    depth: int
    nodes: int
    pv: list[int]
    timed_out: bool


def repetition_key(board: cshogi.Board) -> str:
    return " ".join(board.sfen().split()[:3])


def evaluate_material(board: cshogi.Board) -> int:
    score = 0
    for square, piece in enumerate(board.pieces):
        if piece == cshogi.NONE:
            continue
        value = PIECE_VALUES.get(int(board.piece_type(square)), 0)
        score += -value if piece >= 17 else value

    black_hands, white_hands = board.pieces_in_hand
    for index, value in enumerate(HAND_VALUES):
        score += int(black_hands[index]) * value
        score -= int(white_hands[index]) * value

    return score if board.turn == cshogi.BLACK else -score


def terminal_score(board: cshogi.Board, ply: int) -> int | None:
    legal_moves = list(board.legal_moves)
    if legal_moves:
        return None
    if board.is_check():
        return -MATE_SCORE + ply
    return 0


def negamax(
    board: cshogi.Board,
    depth: int,
    alpha: int,
    beta: int,
    position_counts: dict[str, int],
    deadline: float | None,
    ply: int,
    nodes: list[int],
    move_orderer: Callable[[cshogi.Board, Iterable[int]], Iterable[int]] | None,
    evaluator: Callable[[cshogi.Board], int] | None,
) -> tuple[int, list[int]]:
    if deadline is not None and monotonic() >= deadline:
        raise SearchTimeout

    nodes[0] += 1
    if position_counts.get(repetition_key(board), 0) >= 4:
        return 0, []

    terminal = terminal_score(board, ply)
    if terminal is not None:
        return terminal, []
    if depth <= 0:
        return evaluator(board) if evaluator is not None else evaluate_material(board), []

    best_score = -INF_SCORE
    best_line: list[int] = []

    legal_moves = list(board.legal_moves)
    ordered_moves = list(move_orderer(board, legal_moves)) if move_orderer is not None else legal_moves
    for move in ordered_moves:
        child = board.copy()
        child.push(move)
        child_counts = dict(position_counts)
        key = repetition_key(child)
        child_counts[key] = child_counts.get(key, 0) + 1

        score, line = negamax(
            child,
            depth - 1,
            -beta,
            -alpha,
            child_counts,
            deadline,
            ply + 1,
            nodes,
            move_orderer,
            evaluator,
        )
        score = -score
        if score > best_score:
            best_score = score
            best_line = [move, *line]
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break

    return best_score, best_line


def search_best_move(
    board: cshogi.Board,
    position_counts: dict[str, int],
    max_depth: int,
    time_limit_ms: int | None,
    move_orderer: Callable[[cshogi.Board, Iterable[int]], Iterable[int]] | None = None,
    evaluator: Callable[[cshogi.Board], int] | None = None,
) -> SearchResult:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return SearchResult(
            move=None,
            score=terminal_score(board, 0) or 0,
            depth=0,
            nodes=0,
            pv=[],
            timed_out=False,
        )

    deadline = None if time_limit_ms is None else monotonic() + time_limit_ms / 1000
    best_move = legal_moves[0]
    best_score = evaluate_material(board)
    best_line = [best_move]
    completed_depth = 0
    total_nodes = 0
    timed_out = False

    for depth in range(1, max_depth + 1):
        depth_nodes = [0]
        try:
            score, line = negamax(
                board,
                depth,
                -INF_SCORE,
                INF_SCORE,
                position_counts,
                deadline,
                0,
                depth_nodes,
                move_orderer,
                evaluator,
            )
        except SearchTimeout:
            timed_out = True
            break

        total_nodes += depth_nodes[0]
        completed_depth = depth
        if line:
            best_move = line[0]
            best_line = line
            best_score = score

    return SearchResult(
        move=best_move,
        score=best_score,
        depth=completed_depth,
        nodes=total_nodes,
        pv=best_line,
        timed_out=timed_out,
    )
