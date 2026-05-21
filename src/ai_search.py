"""功能：實作將棋 AI 搜尋核心，結合局面評估、alpha-beta 剪枝與走法排序。"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from time import monotonic

import cshogi


MATE_SCORE = 1_000_000
INF_SCORE = 10_000_000
EXACT = 0
LOWER_BOUND = 1
UPPER_BOUND = 2

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
HAND_PRESSURE_VALUES = [3, 5, 7, 11, 13, 18, 22]
TEMPO_BONUS = 16

GOLD_LIKE_TYPES = {
    cshogi.GOLD,
    cshogi.PROM_PAWN,
    cshogi.PROM_LANCE,
    cshogi.PROM_KNIGHT,
    cshogi.PROM_SILVER,
}
SHELTER_TYPES = GOLD_LIKE_TYPES | {cshogi.SILVER}
PROMOTABLE_TYPES = {
    cshogi.PAWN,
    cshogi.LANCE,
    cshogi.KNIGHT,
    cshogi.SILVER,
    cshogi.BISHOP,
    cshogi.ROOK,
}
MAJOR_TYPES = {cshogi.BISHOP, cshogi.ROOK, cshogi.PROM_BISHOP, cshogi.PROM_ROOK}
MOBILITY_WEIGHTS = {
    cshogi.PAWN: 1,
    cshogi.LANCE: 1,
    cshogi.KNIGHT: 1,
    cshogi.SILVER: 1,
    cshogi.GOLD: 1,
    cshogi.BISHOP: 3,
    cshogi.ROOK: 3,
    cshogi.PROM_BISHOP: 2,
    cshogi.PROM_ROOK: 2,
}


class SearchTimeout(Exception):
    """功能：定義 SearchTimeout 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    pass


@dataclass(frozen=True)
class SearchResult:
    """功能：定義 SearchResult 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    move: int | None
    score: int
    depth: int
    nodes: int
    pv: list[int]
    timed_out: bool


@dataclass(frozen=True)
class TTEntry:
    """功能：定義 TTEntry 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    depth: int
    score: int
    flag: int
    best_move: int | None


@dataclass
class SearchContext:
    """功能：定義 SearchContext 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    deadline: float | None
    move_orderer: Callable[[cshogi.Board, Iterable[int]], Iterable[int]] | None
    evaluator: Callable[[cshogi.Board], int] | None
    root_move_evaluator: Callable[[cshogi.Board], int] | None = None
    move_orderer_max_ply: int = 2
    nodes: list[int] = field(default_factory=lambda: [0])
    tt: dict[tuple[int, int], TTEntry] = field(default_factory=dict)
    killers: dict[int, list[int]] = field(default_factory=dict)
    history: dict[int, int] = field(default_factory=dict)


def repetition_key(board: cshogi.Board) -> str:
    """功能：處理 repetition_key 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return " ".join(board.sfen().split()[:3])


def evaluate_material(board: cshogi.Board) -> int:
    """功能：處理 evaluate_material 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
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


def piece_color(piece: int) -> int | None:
    """功能：處理 piece_color 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if piece == cshogi.NONE:
        return None
    return cshogi.WHITE if piece >= 17 else cshogi.BLACK


def oriented_coords(square: int, color: int) -> tuple[int, int]:
    """功能：處理 oriented_coords 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    file_index, rank_index = divmod(square, 9)
    if color == cshogi.WHITE:
        return 8 - file_index, 8 - rank_index
    return file_index, rank_index


def piece_square_bonus(square: int, piece_type: int, color: int) -> int:
    """功能：處理 piece_square_bonus 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    file_index, rank_index = oriented_coords(square, color)
    progress = 8 - rank_index
    center = 4 - abs(file_index - 4)

    if piece_type == cshogi.PAWN:
        return progress * 5
    if piece_type == cshogi.LANCE:
        return progress * 2
    if piece_type == cshogi.KNIGHT:
        return progress * 3 + center
    if piece_type == cshogi.SILVER:
        return progress * 2 + center * 2
    if piece_type == cshogi.GOLD:
        return progress + center
    if piece_type in {cshogi.BISHOP, cshogi.ROOK}:
        return center * 2
    if piece_type in GOLD_LIKE_TYPES:
        return progress * 2 + center * 2
    if piece_type == cshogi.PROM_BISHOP:
        return progress * 2 + center * 3
    if piece_type == cshogi.PROM_ROOK:
        return progress * 2 + center * 3
    if piece_type == cshogi.KING:
        edge_distance = min(file_index, 8 - file_index)
        return -edge_distance * 4 - progress * 2
    return 0


def manhattan_distance(first: int, second: int) -> int:
    """功能：處理 manhattan_distance 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    first_file, first_rank = divmod(first, 9)
    second_file, second_rank = divmod(second, 9)
    return abs(first_file - second_file) + abs(first_rank - second_rank)


def promotion_zone_bonus(square: int, piece_type: int, color: int) -> int:
    """功能：處理 promotion_zone_bonus 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    _, rank_index = oriented_coords(square, color)
    progress = 8 - rank_index
    if piece_type in PROMOTABLE_TYPES and progress >= 6:
        return 18 + (progress - 6) * 8
    if piece_type in {cshogi.PROM_PAWN, cshogi.PROM_LANCE, cshogi.PROM_KNIGHT, cshogi.PROM_SILVER}:
        return 16 + center_file_bonus(square, color)
    if piece_type in {cshogi.PROM_BISHOP, cshogi.PROM_ROOK}:
        return 28 + center_file_bonus(square, color) * 2
    return 0


def center_file_bonus(square: int, color: int) -> int:
    """功能：處理 center_file_bonus 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    file_index, _ = oriented_coords(square, color)
    return 4 - abs(file_index - 4)


def side_pseudo_moves(board: cshogi.Board, color: int) -> list[int]:
    """功能：處理 side_pseudo_moves 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if board.turn == color:
        return list(board.pseudo_legal_moves)
    copy = board.copy()
    copy.turn = color
    return list(copy.pseudo_legal_moves)


def attack_counts(board: cshogi.Board, color: int) -> list[int]:
    """功能：處理 attack_counts 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    attacks = [0] * 81
    for move in side_pseudo_moves(board, color):
        if cshogi.move_is_drop(move):
            continue
        attacks[cshogi.move_to(move)] += 1
    return attacks


def mobility_score(board: cshogi.Board, color: int) -> int:
    """功能：處理 mobility_score 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    score = 0
    for move in side_pseudo_moves(board, color):
        if cshogi.move_is_drop(move):
            continue
        piece_type = int(board.piece_type(cshogi.move_from(move)))
        score += MOBILITY_WEIGHTS.get(piece_type, 0)
    return score


def king_ring(square: int) -> list[int]:
    """功能：處理 king_ring 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    file_index, rank_index = divmod(square, 9)
    ring = []
    for file_delta in (-1, 0, 1):
        for rank_delta in (-1, 0, 1):
            if file_delta == 0 and rank_delta == 0:
                continue
            next_file = file_index + file_delta
            next_rank = rank_index + rank_delta
            if 0 <= next_file < 9 and 0 <= next_rank < 9:
                ring.append(next_file * 9 + next_rank)
    return ring


def king_safety_score(
    board: cshogi.Board,
    color: int,
    own_attacks: list[int],
    enemy_attacks: list[int],
) -> int:
    """功能：處理 king_safety_score 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    square = board.king_square(color)
    file_index, rank_index = oriented_coords(square, color)
    score = 0
    shelter_count = 0
    for target in king_ring(square):
        piece = int(board.pieces[target])
        if piece_color(piece) == color and int(board.piece_type(target)) in SHELTER_TYPES:
            score += 18
            shelter_count += 1
        if own_attacks[target] > 0:
            score += 2
        if enemy_attacks[target] > 0:
            score -= 10 * min(enemy_attacks[target], 2)
    if enemy_attacks[square] > 0:
        score -= 30
    if min(file_index, 8 - file_index) <= 2 and rank_index >= 6:
        score += shelter_count * 6
    for target, piece in enumerate(board.pieces):
        if piece_color(int(piece)) != color:
            continue
        piece_type = int(board.piece_type(target))
        if piece_type not in SHELTER_TYPES:
            continue
        distance = manhattan_distance(square, target)
        if distance == 2:
            score += 10
        elif distance == 3:
            score += 4
    score -= king_line_pressure(board, color)
    return score


def ray_squares(square: int, file_delta: int, rank_delta: int) -> list[int]:
    """功能：處理 ray_squares 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    file_index, rank_index = divmod(square, 9)
    ray = []
    file_index += file_delta
    rank_index += rank_delta
    while 0 <= file_index < 9 and 0 <= rank_index < 9:
        ray.append(file_index * 9 + rank_index)
        file_index += file_delta
        rank_index += rank_delta
    return ray


def king_line_pressure(board: cshogi.Board, color: int) -> int:
    """功能：處理 king_line_pressure 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    king = board.king_square(color)
    enemy = cshogi.WHITE if color == cshogi.BLACK else cshogi.BLACK
    pressure = 0
    rook_dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    bishop_dirs = ((1, 1), (1, -1), (-1, 1), (-1, -1))
    for directions, attackers in (
        (rook_dirs, {cshogi.ROOK, cshogi.PROM_ROOK}),
        (bishop_dirs, {cshogi.BISHOP, cshogi.PROM_BISHOP}),
    ):
        for file_delta, rank_delta in directions:
            blockers = 0
            for target in ray_squares(king, file_delta, rank_delta):
                piece = int(board.pieces[target])
                if piece == cshogi.NONE:
                    continue
                if piece_color(piece) == color:
                    blockers += 1
                    if blockers >= 2:
                        break
                    continue
                if piece_color(piece) == enemy and int(board.piece_type(target)) in attackers:
                    pressure += 42 if blockers == 0 else 18
                break
    return pressure


def hanging_piece_score(
    board: cshogi.Board,
    color: int,
    own_attacks: list[int],
    enemy_attacks: list[int],
) -> int:
    """功能：處理 hanging_piece_score 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    penalty = 0
    for square, piece in enumerate(board.pieces):
        if piece_color(int(piece)) != color:
            continue
        piece_type = int(board.piece_type(square))
        if piece_type == cshogi.KING:
            continue
        value = PIECE_VALUES.get(piece_type, 0)
        if enemy_attacks[square] > 0 and own_attacks[square] == 0:
            penalty += value // 8
        elif enemy_attacks[square] > own_attacks[square]:
            penalty += value // 18
        elif enemy_attacks[square] == 0 and own_attacks[square] > 0 and piece_type in MAJOR_TYPES:
            penalty -= value // 40
    return -penalty


def hand_pressure_score(board: cshogi.Board, color: int) -> int:
    """功能：處理 hand_pressure_score 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    enemy_king = board.king_square(cshogi.WHITE if color == cshogi.BLACK else cshogi.BLACK)
    ring = king_ring(enemy_king)
    open_ring_squares = sum(1 for square in ring if board.pieces[square] == cshogi.NONE)
    weak_ring_squares = sum(
        1
        for square in ring
        if board.pieces[square] == cshogi.NONE
        or piece_color(int(board.pieces[square])) != color
    )
    hands = board.pieces_in_hand[color]
    pressure = open_ring_squares * sum(int(count) * HAND_PRESSURE_VALUES[index] for index, count in enumerate(hands))
    pressure += weak_ring_squares * (int(hands[3]) * 8 + int(hands[4]) * 10 + int(hands[5]) * 12 + int(hands[6]) * 14)
    return pressure


def piece_efficiency_score(
    board: cshogi.Board,
    color: int,
    own_attacks: list[int],
    enemy_attacks: list[int],
) -> int:
    """功能：處理 piece_efficiency_score 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    enemy_king = board.king_square(cshogi.WHITE if color == cshogi.BLACK else cshogi.BLACK)
    score = 0
    for square, piece in enumerate(board.pieces):
        if piece_color(int(piece)) != color:
            continue
        piece_type = int(board.piece_type(square))
        if piece_type in MAJOR_TYPES:
            distance = manhattan_distance(square, enemy_king)
            score += max(0, 9 - distance) * 3
        if piece_type in {cshogi.SILVER, cshogi.GOLD} and manhattan_distance(square, enemy_king) <= 3:
            score += 12
        if own_attacks[square] >= 2 and enemy_attacks[square] == 0 and piece_type != cshogi.KING:
            score += 4
    return score


def evaluate_position(board: cshogi.Board) -> int:
    """功能：處理 evaluate_position 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    black_attacks = attack_counts(board, cshogi.BLACK)
    white_attacks = attack_counts(board, cshogi.WHITE)

    score = 0
    for square, piece in enumerate(board.pieces):
        color = piece_color(int(piece))
        if color is None:
            continue
        piece_type = int(board.piece_type(square))
        value = PIECE_VALUES.get(piece_type, 0)
        positional = piece_square_bonus(square, piece_type, color)
        promotion = promotion_zone_bonus(square, piece_type, color)
        signed = value + positional + promotion
        score += signed if color == cshogi.BLACK else -signed

    black_hands, white_hands = board.pieces_in_hand
    for index, value in enumerate(HAND_VALUES):
        score += int(black_hands[index]) * value
        score -= int(white_hands[index]) * value

    score += mobility_score(board, cshogi.BLACK)
    score -= mobility_score(board, cshogi.WHITE)
    score += king_safety_score(board, cshogi.BLACK, black_attacks, white_attacks)
    score -= king_safety_score(board, cshogi.WHITE, white_attacks, black_attacks)
    score += hanging_piece_score(board, cshogi.BLACK, black_attacks, white_attacks)
    score -= hanging_piece_score(board, cshogi.WHITE, white_attacks, black_attacks)
    score += piece_efficiency_score(board, cshogi.BLACK, black_attacks, white_attacks)
    score -= piece_efficiency_score(board, cshogi.WHITE, white_attacks, black_attacks)
    score += hand_pressure_score(board, cshogi.BLACK)
    score -= hand_pressure_score(board, cshogi.WHITE)
    score += TEMPO_BONUS if board.turn == cshogi.BLACK else -TEMPO_BONUS

    return score if board.turn == cshogi.BLACK else -score


def evaluate(board: cshogi.Board, evaluator: Callable[[cshogi.Board], int] | None) -> int:
    """功能：處理 evaluate 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return evaluator(board) if evaluator is not None else evaluate_position(board)


def tactical_score(board: cshogi.Board, move: int) -> int:
    """功能：處理 tactical_score 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    score = 0
    captured_type = int(cshogi.move_cap(move))
    if captured_type:
        attacker_type = int(board.piece_type(cshogi.move_from(move)))
        score += 10_000 + PIECE_VALUES.get(captured_type, 0) * 10 - PIECE_VALUES.get(attacker_type, 0)
    if cshogi.move_is_promotion(move):
        score += 2_000
    return score


def is_quiet_move(move: int) -> bool:
    """功能：處理 is_quiet_move 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return int(cshogi.move_cap(move)) == 0 and not cshogi.move_is_promotion(move)


def ordered_moves(
    board: cshogi.Board,
    legal_moves: list[int],
    context: SearchContext,
    ply: int,
    tt_move: int | None,
) -> list[int]:
    """功能：處理 ordered_moves 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if context.move_orderer is not None and ply < context.move_orderer_max_ply:
        preferred = list(context.move_orderer(board, legal_moves))
        policy_rank = {move: index for index, move in enumerate(preferred)}
    else:
        policy_rank = {move: index for index, move in enumerate(legal_moves)}

    killers = context.killers.get(ply, [])
    return sorted(
        legal_moves,
        key=lambda move: (
            move == tt_move,
            tactical_score(board, move),
            move in killers,
            context.history.get(move, 0),
            -policy_rank.get(move, len(legal_moves)),
        ),
        reverse=True,
    )


def terminal_score(board: cshogi.Board, ply: int) -> int | None:
    """功能：處理 terminal_score 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    legal_moves = list(board.legal_moves)
    if legal_moves:
        return None
    if board.is_check():
        return -MATE_SCORE + ply
    return 0


def tt_key(board: cshogi.Board, position_counts: dict[str, int]) -> tuple[int, int]:
    """功能：處理 tt_key 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return board.zobrist_hash(), min(position_counts.get(repetition_key(board), 0), 3)


def record_killer(context: SearchContext, ply: int, move: int) -> None:
    """功能：處理 record_killer 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    killers = context.killers.setdefault(ply, [])
    if move in killers:
        return
    killers.insert(0, move)
    del killers[2:]


def quiescence(
    board: cshogi.Board,
    alpha: int,
    beta: int,
    position_counts: dict[str, int],
    context: SearchContext,
    ply: int,
) -> int:
    """功能：處理 quiescence 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if context.deadline is not None and monotonic() >= context.deadline:
        raise SearchTimeout

    context.nodes[0] += 1
    if position_counts.get(repetition_key(board), 0) >= 4:
        return 0

    terminal = terminal_score(board, ply)
    if terminal is not None:
        return terminal

    stand_pat = evaluate(board, context.evaluator)
    if not board.is_check():
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

    legal_moves = list(board.legal_moves)
    if board.is_check():
        candidates = legal_moves
    else:
        candidates = [move for move in legal_moves if int(cshogi.move_cap(move)) or cshogi.move_is_promotion(move)]
    candidates.sort(key=lambda move: tactical_score(board, move), reverse=True)

    for move in candidates:
        child = board.copy()
        child.push(move)
        child_counts = dict(position_counts)
        child_key = repetition_key(child)
        child_counts[child_key] = child_counts.get(child_key, 0) + 1
        score = -quiescence(child, -beta, -alpha, child_counts, context, ply + 1)
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def negamax(
    board: cshogi.Board,
    depth: int,
    alpha: int,
    beta: int,
    position_counts: dict[str, int],
    ply: int,
    context: SearchContext,
) -> tuple[int, list[int]]:
    """功能：處理 negamax 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if context.deadline is not None and monotonic() >= context.deadline:
        raise SearchTimeout

    context.nodes[0] += 1
    if position_counts.get(repetition_key(board), 0) >= 4:
        return 0, []

    terminal = terminal_score(board, ply)
    if terminal is not None:
        return terminal, []
    if depth <= 0:
        return quiescence(board, alpha, beta, position_counts, context, ply), []

    entry_key = tt_key(board, position_counts)
    entry = context.tt.get(entry_key)
    original_alpha = alpha
    if entry is not None and entry.depth >= depth:
        if entry.flag == EXACT:
            return entry.score, [entry.best_move] if entry.best_move is not None else []
        if entry.flag == LOWER_BOUND:
            alpha = max(alpha, entry.score)
        elif entry.flag == UPPER_BOUND:
            beta = min(beta, entry.score)
        if alpha >= beta:
            return entry.score, [entry.best_move] if entry.best_move is not None else []

    best_score = -INF_SCORE
    best_line: list[int] = []

    legal_moves = list(board.legal_moves)
    for move in ordered_moves(board, legal_moves, context, ply, entry.best_move if entry else None):
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
            ply + 1,
            context,
        )
        score = -score
        if ply == 0 and context.root_move_evaluator is not None:
            score += context.root_move_evaluator(child)
        if score > best_score:
            best_score = score
            best_line = [move, *line]
        if score > alpha:
            alpha = score
        if alpha >= beta:
            if is_quiet_move(move):
                record_killer(context, ply, move)
                context.history[move] = context.history.get(move, 0) + depth * depth
            break

    if best_score <= original_alpha:
        flag = UPPER_BOUND
    elif best_score >= beta:
        flag = LOWER_BOUND
    else:
        flag = EXACT
    context.tt[entry_key] = TTEntry(depth=depth, score=best_score, flag=flag, best_move=best_line[0] if best_line else None)
    return best_score, best_line


def search_best_move(
    board: cshogi.Board,
    position_counts: dict[str, int],
    max_depth: int,
    time_limit_ms: int | None,
    move_orderer: Callable[[cshogi.Board, Iterable[int]], Iterable[int]] | None = None,
    evaluator: Callable[[cshogi.Board], int] | None = None,
    root_move_evaluator: Callable[[cshogi.Board], int] | None = None,
    move_orderer_max_ply: int = 2,
) -> SearchResult:
    """功能：處理 search_best_move 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
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
    best_score = evaluate(board, evaluator)
    best_line = [best_move]
    completed_depth = 0
    total_nodes = 0
    timed_out = False

    context = SearchContext(
        deadline=deadline,
        move_orderer=move_orderer,
        evaluator=evaluator,
        root_move_evaluator=root_move_evaluator,
        move_orderer_max_ply=max(0, move_orderer_max_ply),
    )
    for depth in range(1, max_depth + 1):
        start_nodes = context.nodes[0]
        try:
            score, line = negamax(
                board,
                depth,
                -INF_SCORE,
                INF_SCORE,
                position_counts,
                0,
                context,
            )
        except SearchTimeout:
            timed_out = True
            break

        total_nodes += context.nodes[0] - start_nodes
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
