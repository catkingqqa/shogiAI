"""從 MySQL 串流匯出 NNUE 所需的局面、勝負與分組資訊。"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pymysql


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="從 MySQL 匯出精簡 NNUE 資料集。")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER"))
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", "DB11211213"))
    parser.add_argument("--limit", type=int, default=None, help="只供流程測試；正式匯出不要設定")
    parser.add_argument("--progress-every", type=int, default=100_000)
    return parser.parse_args()


def clean_result(value: object) -> str:
    result = "" if value is None else str(value).strip().upper()
    return "" if result in {"", "NONE", "NULL"} else result


def value_for_row(side_to_move: str, final_side_to_move: str, result: str) -> tuple[float, float, str | None]:
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


def main() -> int:
    args = parse_args()
    if not args.user:
        raise SystemExit("缺少 --user 或 MYSQL_USER")
    if args.password is None:
        raise SystemExit("缺少 --password 或 MYSQL_PASSWORD")

    metas: list[str] = []
    values: list[float] = []
    value_masks: list[float] = []
    game_ids: list[int] = []
    result_counts: Counter[str] = Counter()

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.SSDictCursor,
    )
    limit_clause = "" if args.limit is None else f"\n        LIMIT {int(args.limit)}"
    query = f"""
        SELECT
            p.game_id,
            p.move_number,
            p.sfen,
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
        {limit_clause}
    """

    with connection:
        with connection.cursor() as cursor:
            print("開始查詢 MySQL NNUE 資料...")
            cursor.execute(query)
            for row_index, row in enumerate(cursor, start=1):
                result = clean_result(row["result"])
                value, value_mask, winner = value_for_row(
                    str(row["side_to_move"]), str(row["final_side_to_move"]), result
                )
                game_id = int(row["game_id"])
                values.append(value)
                value_masks.append(value_mask)
                game_ids.append(game_id)
                result_counts[result or "UNKNOWN"] += 1
                metas.append(
                    json.dumps(
                        {
                            "game_id": game_id,
                            "ply": int(row["move_number"]) + 1,
                            "sfen": str(row["sfen"]),
                            "result": result,
                            "winner": winner,
                            "value": value,
                            "value_mask": value_mask,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                if row_index % max(1, args.progress_every) == 0:
                    print(f"exported={row_index:,}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp.npz")
    np.savez_compressed(
        temporary,
        meta=np.asarray(metas, dtype=object),
        values=np.asarray(values, dtype=np.float32),
        value_masks=np.asarray(value_masks, dtype=np.float32),
        game_ids=np.asarray(game_ids, dtype=np.int32),
        result_counts=np.asarray(json.dumps(result_counts, ensure_ascii=False)),
    )
    os.replace(temporary, args.output)
    print(
        json.dumps(
            {
                "samples": len(metas),
                "games": len(set(game_ids)),
                "value_labeled_samples": int(sum(value_masks)),
                "result_counts": dict(result_counts),
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
