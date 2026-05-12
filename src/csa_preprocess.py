from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cshogi
from cshogi import CSA
import numpy as np


# 模型訓練資料的固定尺寸設定：
# 將 9x9 棋盤、手駒、輪到哪方走棋都轉成固定大小的 numpy array。
PIECE_TYPE_COUNT = 14
HAND_PIECE_COUNT = 7
BOARD_SIZE = 9
SQUARE_N = 81
STATE_PLANES = 43
NORMAL_MOVE_LABELS = SQUARE_N * SQUARE_N * 2
MOVE_LABELS = NORMAL_MOVE_LABELS + HAND_PIECE_COUNT * SQUARE_N


@dataclass
class SampleMeta:
    # 每一筆訓練樣本的來源資訊，方便之後回查是從哪份棋譜、哪一步產生。
    source: str
    game_index: int
    ply: int
    sfen: str
    move_usi: str


@dataclass
class InvalidGame:
    # 記錄無法解析或中途出錯的棋局，讓批次轉檔時不會因單一檔案中斷。
    source: str
    game_index: int
    reason: str
    ply: int | None = None
    move_usi: str | None = None
    sfen: str | None = None


def iter_csa_files(path: Path, recursive: bool) -> Iterable[Path]:
    # 依照使用者給的路徑找出 CSA/KIF 檔；可以處理單檔或整個資料夾。
    if path.is_file():
        yield path
        return
    pattern = "**/*" if recursive else "*"
    for file in sorted(path.glob(pattern)):
        if file.is_file() and file.suffix.lower() in {".csa", ".kif"}:
            yield file


def piece_color(piece: int) -> int | None:
    # cshogi 用數字代表棋子，這裡把棋子換成黑方/白方/空格。
    if piece == cshogi.NONE:
        return None
    return cshogi.WHITE if piece >= 17 else cshogi.BLACK


def orient_square(square: int, turn: int, orient_to_turn: bool) -> int:
    # 若要以「輪到走棋的一方」視角訓練，白方走棋時會把棋盤旋轉 180 度。
    if orient_to_turn and turn == cshogi.WHITE:
        return 80 - square
    return square


def encode_state(board: cshogi.Board, orient_to_turn: bool = True) -> np.ndarray:
    # 把目前局面轉成神經網路容易吃的 43 層特徵平面。
    state = np.zeros((STATE_PLANES, BOARD_SIZE, BOARD_SIZE), dtype=np.uint8)
    turn = board.turn

    for square, piece in enumerate(board.pieces):
        color = piece_color(piece)
        if color is None:
            continue
        ptype = board.piece_type(square)
        if not 1 <= ptype <= PIECE_TYPE_COUNT:
            continue
        view_square = orient_square(square, turn, orient_to_turn)
        row, col = divmod(view_square, BOARD_SIZE)

        if orient_to_turn:
            owner_offset = 0 if color == turn else PIECE_TYPE_COUNT
        else:
            owner_offset = 0 if color == cshogi.BLACK else PIECE_TYPE_COUNT
        state[owner_offset + ptype - 1, row, col] = 1

    black_hands, white_hands = board.pieces_in_hand
    if orient_to_turn:
        own_hands = black_hands if turn == cshogi.BLACK else white_hands
        opp_hands = white_hands if turn == cshogi.BLACK else black_hands
    else:
        own_hands = black_hands
        opp_hands = white_hands

    for i, count in enumerate(own_hands):
        state[28 + i, :, :] = count
    for i, count in enumerate(opp_hands):
        state[35 + i, :, :] = count

    state[42, :, :] = 1 if (orient_to_turn or turn == cshogi.BLACK) else 0
    return state


def encode_move(move: int, turn: int, orient_to_turn: bool = True) -> int:
    # 把 cshogi 的走法編號轉成自己的 policy label，包含普通移動、升變、打入。
    view_move = cshogi.move_rotate(move) if orient_to_turn and turn == cshogi.WHITE else move
    to_square = cshogi.move_to(view_move)

    if cshogi.move_is_drop(view_move):
        drop_piece = cshogi.move_drop_hand_piece(view_move)
        if not 0 <= drop_piece < HAND_PIECE_COUNT:
            raise ValueError(f"unsupported drop piece index: {drop_piece}")
        return NORMAL_MOVE_LABELS + drop_piece * SQUARE_N + to_square

    from_square = cshogi.move_from(view_move)
    promotion = 1 if cshogi.move_is_promotion(view_move) else 0
    return (from_square * SQUARE_N + to_square) * 2 + promotion


def value_for_turn(result: int, turn: int) -> float:
    # 從當前走棋方角度標記勝負：贏為 1、輸為 -1、和棋為 0。
    if result == cshogi.DRAW:
        return 0.0
    if result == cshogi.BLACK_WIN:
        return 1.0 if turn == cshogi.BLACK else -1.0
    if result == cshogi.WHITE_WIN:
        return 1.0 if turn == cshogi.WHITE else -1.0
    raise ValueError(f"unknown game result: {result}")


def replay_game(
    parser: CSA.Parser,
    source: Path,
    game_index: int,
    orient_to_turn: bool,
) -> tuple[list[np.ndarray], list[int], list[float], list[SampleMeta]]:
    # 逐手重播一盤棋，產生每一步的盤面、下一手答案、勝負標籤和 metadata。
    if parser.win not in cshogi.GAME_RESULTS:
        raise ValueError(f"game has no known result: {parser.win}")

    board = cshogi.Board(parser.sfen)
    states: list[np.ndarray] = []
    moves: list[int] = []
    values: list[float] = []
    metas: list[SampleMeta] = []

    for ply, move in enumerate(parser.moves, start=1):
        move_usi = cshogi.move_to_usi(move)
        if not board.is_legal(move):
            raise ValueError(f"illegal move at ply {ply}: {move_usi}")

        states.append(encode_state(board, orient_to_turn=orient_to_turn))
        moves.append(encode_move(move, board.turn, orient_to_turn=orient_to_turn))
        values.append(value_for_turn(parser.win, board.turn))
        metas.append(
            SampleMeta(
                source=str(source),
                game_index=game_index,
                ply=ply,
                sfen=board.sfen(),
                move_usi=move_usi,
            )
        )
        board.push(move)

    return states, moves, values, metas


def parse_args() -> argparse.Namespace:
    # 命令列參數設定：輸入棋譜、輸出 npz、是否遞迴掃描和錯誤報告。
    ap = argparse.ArgumentParser(description="Convert legal CSA games into training samples.")
    ap.add_argument("--input", required=True, type=Path, help="CSA file or directory")
    ap.add_argument("--output", required=True, type=Path, help="Output .npz file")
    ap.add_argument("--recursive", action="store_true", help="Scan directories recursively")
    ap.add_argument("--encoding", default=None, help="CSA text encoding, e.g. cp932 or utf-8")
    ap.add_argument("--keep-invalid-report", type=Path, default=None, help="Write invalid games as JSONL")
    ap.add_argument("--max-games", type=int, default=None, help="Stop after this many parsed games")
    ap.add_argument("--no-orient", action="store_true", help="Do not rotate to side-to-move perspective")
    return ap.parse_args()


def main() -> int:
    # 主流程：掃描棋譜、轉成訓練資料、輸出壓縮 npz，並記錄壞棋譜。
    args = parse_args()
    orient_to_turn = not args.no_orient

    all_states: list[np.ndarray] = []
    all_moves: list[int] = []
    all_values: list[float] = []
    all_meta: list[SampleMeta] = []
    invalid: list[InvalidGame] = []
    legal_games = 0
    parsed_games = 0

    for file in iter_csa_files(args.input, args.recursive):
        try:
            games = CSA.Parser.parse_file(str(file), encoding=args.encoding)
        except Exception as exc:
            invalid.append(InvalidGame(str(file), 0, f"parse failed: {exc}"))
            continue

        for game_index, parser in enumerate(games):
            parsed_games += 1
            try:
                states, moves, values, metas = replay_game(parser, file, game_index, orient_to_turn)
            except Exception as exc:
                invalid.append(InvalidGame(str(file), game_index, str(exc)))
                continue

            legal_games += 1
            all_states.extend(states)
            all_moves.extend(moves)
            all_values.extend(values)
            all_meta.extend(metas)

            if args.max_games is not None and parsed_games >= args.max_games:
                break
        if args.max_games is not None and parsed_games >= args.max_games:
            break

    args.output.parent.mkdir(parents=True, exist_ok=True)
    states_array = (
        np.stack(all_states, axis=0)
        if all_states
        else np.zeros((0, STATE_PLANES, BOARD_SIZE, BOARD_SIZE), dtype=np.uint8)
    )
    np.savez_compressed(
        args.output,
        states=states_array,
        moves=np.asarray(all_moves, dtype=np.int32),
        values=np.asarray(all_values, dtype=np.float32),
        meta=np.asarray([json.dumps(asdict(m), ensure_ascii=False) for m in all_meta]),
        move_label_count=np.asarray(MOVE_LABELS, dtype=np.int32),
    )

    if args.keep_invalid_report is not None:
        args.keep_invalid_report.parent.mkdir(parents=True, exist_ok=True)
        with args.keep_invalid_report.open("w", encoding="utf-8") as f:
            for item in invalid:
                f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "parsed_games": parsed_games,
                "legal_games": legal_games,
                "invalid_games": len(invalid),
                "samples": len(all_moves),
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
