from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

import cshogi
import numpy as np
import pymysql

from csa_preprocess import MOVE_LABELS, encode_move, encode_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export policy/value-network samples from MySQL.")
    parser.add_argument("--output", required=True, type=Path, help="Output .npz path")
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER"))
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", "DB11211213"))
    parser.add_argument("--no-orient", action="store_true", help="Do not rotate states to side-to-move")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.user:
        raise SystemExit("Missing --user or MYSQL_USER.")
    if args.password is None:
        raise SystemExit("Missing --password or MYSQL_PASSWORD.")

    orient_to_turn = not args.no_orient
    states: list[np.ndarray] = []
    moves: list[int] = []
    values: list[float] = []
    value_masks: list[float] = []
    game_ids: list[int] = []
    metas: list[str] = []
    result_counts: Counter[str] = Counter()
    value_mask_counts: Counter[str] = Counter()

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.game_id,
                    p.move_number,
                    p.sfen,
                    m.usi_move,
                    p.side_to_move,
                    final_position.side_to_move AS final_side_to_move,
                    g.result
                FROM positions p
                JOIN moves m
                  ON m.game_id = p.game_id
                 AND m.move_number = p.move_number + 1
                JOIN game_records g
                  ON g.game_id = p.game_id
                JOIN (
                    SELECT game_id, MAX(move_number) AS max_move_number
                    FROM positions
                    GROUP BY game_id
                ) final_moves
                  ON final_moves.game_id = p.game_id
                JOIN positions final_position
                  ON final_position.game_id = p.game_id
                 AND final_position.move_number = final_moves.max_move_number
                ORDER BY p.game_id, p.move_number
                """
            )
            rows = cursor.fetchall()

    invalid_rows = 0
    for row in rows:
        try:
            board = cshogi.Board(str(row["sfen"]))
            move = board.move_from_usi(str(row["usi_move"]))
            if not board.is_legal(move):
                raise ValueError("illegal move")
            states.append(encode_state(board, orient_to_turn=orient_to_turn))
            moves.append(encode_move(move, board.turn, orient_to_turn=orient_to_turn))
            result = clean_result(row["result"])
            value, value_mask, winner = value_for_row(
                str(row["side_to_move"]),
                str(row["final_side_to_move"]),
                result,
            )
            values.append(value)
            value_masks.append(value_mask)
            game_ids.append(int(row["game_id"]))
            result_counts[result or "UNKNOWN"] += 1
            value_mask_counts["labeled" if value_mask else "unlabeled"] += 1
            metas.append(
                json.dumps(
                    {
                        "game_id": int(row["game_id"]),
                        "ply": int(row["move_number"]) + 1,
                        "sfen": str(row["sfen"]),
                        "move_usi": str(row["usi_move"]),
                        "result": result,
                        "winner": winner,
                        "value": value,
                        "value_mask": value_mask,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            invalid_rows += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    states_array = np.stack(states, axis=0) if states else np.zeros((0, 43, 9, 9), dtype=np.uint8)
    np.savez_compressed(
        args.output,
        states=states_array,
        moves=np.asarray(moves, dtype=np.int64),
        values=np.asarray(values, dtype=np.float32),
        value_masks=np.asarray(value_masks, dtype=np.float32),
        game_ids=np.asarray(game_ids, dtype=np.int32),
        meta=np.asarray(metas),
        move_label_count=np.asarray(MOVE_LABELS, dtype=np.int32),
        orient_to_turn=np.asarray(orient_to_turn),
        result_counts=np.asarray(json.dumps(result_counts, ensure_ascii=False)),
        value_mask_counts=np.asarray(json.dumps(value_mask_counts, ensure_ascii=False)),
    )
    print(
        json.dumps(
            {
                "samples": len(moves),
                "games": len(set(game_ids)),
                "value_labeled_samples": int(sum(value_masks)),
                "value_unlabeled_samples": int(len(value_masks) - sum(value_masks)),
                "result_counts": dict(result_counts),
                "invalid_rows": invalid_rows,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def clean_result(value: object) -> str:
    result = "" if value is None else str(value).strip().upper()
    return "" if result in {"", "NONE", "NULL"} else result


def value_for_row(side_to_move: str, final_side_to_move: str, result: str) -> tuple[float, float, str | None]:
    winner: str | None
    if result == "BLACK_WIN":
        winner = "black"
    elif result == "WHITE_WIN":
        winner = "white"
    elif result == "TORYO":
        winner = "white" if final_side_to_move == "black" else "black"
    elif result in {"DRAW", "SENNICHITE"}:
        return 0.0, 1.0, None
    else:
        return 0.0, 0.0, None

    return (1.0 if side_to_move == winner else -1.0), 1.0, winner


if __name__ == "__main__":
    raise SystemExit(main())
