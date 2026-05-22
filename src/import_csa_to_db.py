"""功能：將 CSA 棋譜匯入 MySQL，負責建立棋手、棋局、走法與局面資料。"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import cshogi
from cshogi import CSA

try:
    import pymysql
except ImportError as exc:  # pragma: no cover - shown as a clear CLI error.
    raise SystemExit(
        "Missing dependency: PyMySQL. Install it with `python -m pip install PyMySQL`."
    ) from exc


CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) NOT NULL,
        email VARCHAR(255) UNIQUE,
        password_hash VARCHAR(255),
        role VARCHAR(50) DEFAULT 'user',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS players (
        player_id INT AUTO_INCREMENT PRIMARY KEY,
        player_name VARCHAR(100) NOT NULL,
        rank_name VARCHAR(50),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS game_records (
        game_id INT AUTO_INCREMENT PRIMARY KEY,
        uploader_id INT,
        black_player_id INT,
        white_player_id INT,
        event_name VARCHAR(255),
        site VARCHAR(255),
        opening VARCHAR(100),
        result VARCHAR(50),
        source_format VARCHAR(20),
        original_file_name VARCHAR(255),
        played_at DATE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (uploader_id) REFERENCES users(user_id),
        FOREIGN KEY (black_player_id) REFERENCES players(player_id),
        FOREIGN KEY (white_player_id) REFERENCES players(player_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS moves (
        move_id INT AUTO_INCREMENT PRIMARY KEY,
        game_id INT NOT NULL,
        move_number INT NOT NULL,
        side_to_move ENUM('black', 'white') NOT NULL,
        original_move VARCHAR(100),
        usi_move VARCHAR(20),
        move_time VARCHAR(50),
        comment TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (game_id) REFERENCES game_records(game_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        position_id INT AUTO_INCREMENT PRIMARY KEY,
        game_id INT NOT NULL,
        move_number INT NOT NULL,
        side_to_move ENUM('black', 'white') NOT NULL,
        sfen TEXT NOT NULL,
        sfen_hash CHAR(64),
        is_check BOOLEAN DEFAULT FALSE,
        legal_moves_count INT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (game_id) REFERENCES game_records(game_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


@dataclass
class ImportSummary:
    """功能：定義 ImportSummary 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    parsed_games: int = 0
    imported_games: int = 0
    skipped_games: int = 0
    updated_file_names: int = 0
    imported_moves: int = 0
    imported_positions: int = 0
    errors: list[dict[str, Any]] | None = None

    def add_error(self, source: Path, game_index: int, error: Exception) -> None:
        """功能：處理 add_error 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if self.errors is None:
            self.errors = []
        self.errors.append(
            {
                "source": str(source),
                "game_index": game_index,
                "error": str(error),
            }
        )


PlayerCache = dict[tuple[str, str | None], int]
ExistingGameIndex = dict[str, Any]


def iter_csa_files(path: Path, recursive: bool) -> Iterable[Path]:
    """功能：處理 iter_csa_files 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if path.is_file():
        yield path
        return

    pattern = "**/*" if recursive else "*"
    for file in sorted(path.glob(pattern)):
        if file.is_file() and file.suffix.lower() == ".csa":
            yield file


def parse_csa_games(path: Path, encoding: str | None) -> list[CSA.Parser]:
    """功能：Parse CSA files while tolerating UTF-8 BOM headers."""
    encodings = [encoding] if encoding else []
    for candidate in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        if candidate not in encodings:
            encodings.append(candidate)

    last_error: Exception | None = None
    for candidate in encodings:
        try:
            return CSA.Parser.parse_file(str(path), encoding=candidate)
        except Exception as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


def parse_played_at(value: str | None) -> str | None:
    """功能：處理 parse_played_at 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if not value:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_player_name(value: str | None, fallback: str) -> tuple[str, str | None]:
    """功能：處理 parse_player_name 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    name = (value or fallback).strip() or fallback
    parts = name.rsplit(maxsplit=1)
    if len(parts) == 2 and looks_like_rank(parts[1]):
        return parts[0], parts[1]
    return name, None


def looks_like_rank(value: str) -> bool:
    """功能：處理 looks_like_rank 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    rank_suffixes = (
        "級",
        "段",
        "名人",
        "竜王",
        "龍王",
        "王位",
        "王座",
        "棋王",
        "王将",
        "王將",
        "棋聖",
        "女流",
    )
    return any(value.endswith(suffix) for suffix in rank_suffixes)


def game_result(parser: CSA.Parser) -> str | None:
    """功能：處理 game_result 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if parser.endgame:
        return str(parser.endgame).lstrip("%")
    if parser.win == cshogi.BLACK_WIN:
        return "BLACK_WIN"
    if parser.win == cshogi.WHITE_WIN:
        return "WHITE_WIN"
    if parser.win == cshogi.DRAW:
        return "DRAW"
    return None


def side_name(turn: int) -> str:
    """功能：處理 side_name 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return "black" if turn == cshogi.BLACK else "white"


def sfen_hash(sfen: str) -> str:
    """功能：處理 sfen_hash 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return hashlib.sha256(sfen.encode("utf-8")).hexdigest()


def legal_moves_count(board: cshogi.Board) -> int:
    """功能：處理 legal_moves_count 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return sum(1 for _ in board.legal_moves)


def ensure_schema(cursor: Any) -> None:
    """功能：處理 ensure_schema 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    for sql in CREATE_TABLES_SQL:
        cursor.execute(sql)


def ensure_user(cursor: Any, username: str, email: str | None) -> int:
    """功能：處理 ensure_user 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if email:
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
    else:
        cursor.execute("SELECT user_id FROM users WHERE username = %s ORDER BY user_id LIMIT 1", (username,))
    row = cursor.fetchone()
    if row:
        return int(row["user_id"])

    cursor.execute(
        "INSERT INTO users (username, email, role) VALUES (%s, %s, 'user')",
        (username, email),
    )
    return int(cursor.lastrowid)


def game_content_key(initial_sfen: str, moves_usi: Iterable[str]) -> str:
    """用初始局面與完整手順建立內容指紋，避免改檔名後重複匯入同一盤。"""
    payload = "\n".join([initial_sfen.strip(), *moves_usi])
    return "content:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parser_content_key(parser: CSA.Parser) -> str:
    """從 CSA parser 直接建立棋局內容指紋。"""
    return game_content_key(parser.sfen, (cshogi.move_to_usi(move) for move in parser.moves))


def load_existing_game_index(cursor: Any) -> ExistingGameIndex:
    """讀取既有棋局的檔名與內容索引，供 --skip-existing 判斷重複與更新檔名。"""
    file_keys: set[str] = set()
    file_names_by_game: dict[int, str | None] = {}
    cursor.execute(
        """
        SELECT game_id, original_file_name
        FROM game_records
        WHERE source_format = 'CSA'
          AND original_file_name IS NOT NULL
        """
    )
    for row in cursor.fetchall():
        game_id = int(row["game_id"])
        file_name = str(row["original_file_name"])
        file_names_by_game[game_id] = file_name
        file_keys.add(file_name)

    cursor.execute(
        """
        SELECT g.game_id, p.sfen
        FROM game_records g
        JOIN positions p
          ON p.game_id = g.game_id
         AND p.move_number = 0
        WHERE g.source_format = 'CSA'
        """
    )
    initial_sfens = {int(row["game_id"]): str(row["sfen"]) for row in cursor.fetchall()}

    moves_by_game: dict[int, list[str]] = defaultdict(list)
    if initial_sfens:
        cursor.execute(
            """
            SELECT game_id, usi_move
            FROM moves
            WHERE game_id IN (
                SELECT game_id
                FROM game_records
                WHERE source_format = 'CSA'
            )
            ORDER BY game_id, move_number
            """
        )
        for row in cursor.fetchall():
            moves_by_game[int(row["game_id"])].append(str(row["usi_move"]))

    content_keys: dict[str, dict[str, Any]] = {}
    for game_id, initial_sfen in initial_sfens.items():
        content_keys[game_content_key(initial_sfen, moves_by_game.get(game_id, []))] = {
            "game_id": game_id,
            "file_name": file_names_by_game.get(game_id),
        }

    return {"file_keys": file_keys, "content_keys": content_keys}


def load_player_cache(cursor: Any) -> PlayerCache:
    """功能：處理 load_player_cache 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    cursor.execute("SELECT player_id, player_name, rank_name FROM players")
    return {
        (str(row["player_name"]), row["rank_name"]): int(row["player_id"])
        for row in cursor.fetchall()
    }


def ensure_player(cursor: Any, player_cache: PlayerCache, player_name: str, rank_name: str | None) -> int:
    """功能：處理 ensure_player 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    cache_key = (player_name, rank_name)
    if cache_key in player_cache:
        return player_cache[cache_key]

    cursor.execute(
        """
        SELECT player_id
        FROM players
        WHERE player_name = %s
          AND (rank_name = %s OR (rank_name IS NULL AND %s IS NULL))
        ORDER BY player_id
        LIMIT 1
        """,
        (player_name, rank_name, rank_name),
    )
    row = cursor.fetchone()
    if row:
        player_id = int(row["player_id"])
        player_cache[cache_key] = player_id
        return player_id

    cursor.execute(
        "INSERT INTO players (player_name, rank_name) VALUES (%s, %s)",
        (player_name, rank_name),
    )
    player_id = int(cursor.lastrowid)
    player_cache[cache_key] = player_id
    return player_id


def original_file_key(file_name: str, game_index: int) -> str:
    """功能：處理 original_file_key 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return file_name if game_index == 0 else f"{file_name}#game{game_index}"


def build_position_row(game_id: int, move_number: int, board: cshogi.Board) -> tuple[Any, ...]:
    """功能：處理 build_position_row 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    sfen = board.sfen()
    return (
        game_id,
        move_number,
        side_name(board.turn),
        sfen,
        sfen_hash(sfen),
        bool(board.is_check()),
        legal_moves_count(board),
    )


def build_move_and_position_rows(
    game_id: int,
    parser: CSA.Parser,
    source: Path,
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    """功能：處理 build_move_and_position_rows 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    board = cshogi.Board(parser.sfen)
    move_rows: list[tuple[Any, ...]] = []
    position_rows: list[tuple[Any, ...]] = [build_position_row(game_id, 0, board)]
    comments = parser.comments or []
    times = parser.times or []

    for move_number, move in enumerate(parser.moves, start=1):
        move_usi = cshogi.move_to_usi(move)
        if not board.is_legal(move):
            raise ValueError(f"illegal move at {source}:{move_number}: {move_usi}")

        move_rows.append(
            (
                game_id,
                move_number,
                side_name(board.turn),
                move_usi,
                move_usi,
                str(times[move_number - 1]) if move_number - 1 < len(times) else None,
                comments[move_number - 1] if move_number - 1 < len(comments) else None,
            )
        )
        board.push(move)
        position_rows.append(build_position_row(game_id, move_number, board))

    return move_rows, position_rows


def insert_game(
    conn: Any,
    parser: CSA.Parser,
    source: Path,
    game_index: int,
    uploader_id: int,
    skip_existing: bool,
    existing_games: ExistingGameIndex,
    player_cache: PlayerCache,
) -> tuple[bool, int, int, bool]:
    """功能：處理 insert_game 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    with conn.cursor() as cursor:
        file_key = original_file_key(source.name, game_index)
        content_key = parser_content_key(parser)
        file_keys: set[str] = existing_games["file_keys"]
        content_keys: dict[str, dict[str, Any]] = existing_games["content_keys"]
        if skip_existing and file_key in file_keys:
            return False, 0, 0, False
        if skip_existing and content_key in content_keys:
            existing = content_keys[content_key]
            old_file_name = existing.get("file_name")
            if old_file_name != file_key:
                cursor.execute(
                    "UPDATE game_records SET original_file_name = %s WHERE game_id = %s",
                    (file_key, int(existing["game_id"])),
                )
                if old_file_name:
                    file_keys.discard(str(old_file_name))
                file_keys.add(file_key)
                existing["file_name"] = file_key
                return False, 0, 0, True
            return False, 0, 0, False

        names = parser.names or []
        black_name, black_rank = parse_player_name(names[0] if names else None, "先手")
        white_name, white_rank = parse_player_name(
            names[1] if len(names) > 1 else None,
            "後手",
        )
        black_player_id = ensure_player(cursor, player_cache, black_name, black_rank)
        white_player_id = ensure_player(cursor, player_cache, white_name, white_rank)
        info = parser.var_info or {}

        cursor.execute(
            """
            INSERT INTO game_records
                (
                    uploader_id, black_player_id, white_player_id,
                    event_name, site, opening, result, source_format,
                    original_file_name, played_at
                )
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, 'CSA', %s, %s)
            """,
            (
                uploader_id,
                black_player_id,
                white_player_id,
                info.get("EVENT"),
                info.get("SITE"),
                info.get("OPENING"),
                game_result(parser),
                file_key,
                parse_played_at(info.get("START_TIME")),
            ),
        )
        game_id = int(cursor.lastrowid)
        move_rows, position_rows = build_move_and_position_rows(game_id, parser, source)

        if move_rows:
            cursor.executemany(
                """
                INSERT INTO moves
                    (game_id, move_number, side_to_move, original_move, usi_move, move_time, comment)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s)
                """,
                move_rows,
            )
        cursor.executemany(
            """
            INSERT INTO positions
                (game_id, move_number, side_to_move, sfen, sfen_hash, is_check, legal_moves_count)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
            """,
            position_rows,
        )
        file_keys.add(file_key)
        content_keys[content_key] = {"game_id": game_id, "file_name": file_key}

    return True, len(move_rows), len(position_rows), False


def parse_args() -> argparse.Namespace:
    """功能：解析命令列參數，讓使用者可以調整輸入、輸出與執行選項。"""
    parser = argparse.ArgumentParser(description="Import CSA game records into MySQL.")
    parser.add_argument("--input", required=True, type=Path, help="CSA file or directory")
    parser.add_argument("--recursive", action="store_true", help="Scan input directory recursively")
    parser.add_argument("--encoding", default="utf-8-sig", help="CSA file encoding, e.g. utf-8-sig, utf-8, or cp932")
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER"))
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", "DB11211213"))
    parser.add_argument("--uploader", default="csa_importer", help="Username stored in users")
    parser.add_argument("--uploader-email", default=None)
    parser.add_argument("--create-tables", action="store_true", help="Create required tables if missing")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Skip games already in DB by original_file_name or by initial SFEN + full move sequence hash. "
            "If content matches but the file name changed, update original_file_name to the new file name."
        ),
    )
    parser.add_argument("--max-games", type=int, default=None, help="Stop after this many parsed games")
    parser.add_argument("--pause-every", type=int, default=0, help="Pause after this many newly imported games")
    parser.add_argument("--pause-seconds", type=float, default=65.0, help="Seconds to pause when --pause-every is reached")
    parser.add_argument("--dry-run", action="store_true", help="Parse CSA files but do not connect or write")
    return parser.parse_args()


def connect(args: argparse.Namespace) -> Any:
    """功能：處理 connect 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if not args.user:
        raise SystemExit("Missing --user or MYSQL_USER.")
    password = args.password
    if password is None:
        password = getpass.getpass(f"MySQL password for {args.user}@{args.host}: ")

    return pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def dry_run(args: argparse.Namespace) -> ImportSummary:
    """功能：處理 dry_run 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    summary = ImportSummary()
    for source in iter_csa_files(args.input, args.recursive):
        games = parse_csa_games(source, args.encoding)
        for game_index, parser in enumerate(games):
            summary.parsed_games += 1
            summary.imported_games += 1
            summary.imported_moves += len(parser.moves)
            summary.imported_positions += len(parser.moves) + 1
            if args.max_games is not None and summary.parsed_games >= args.max_games:
                return summary
    return summary


def safe_rollback(conn: Any) -> None:
    """功能：處理 safe_rollback 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    try:
        conn.rollback()
    except Exception:
        pass


def import_to_mysql(args: argparse.Namespace) -> ImportSummary:
    """功能：處理 import_to_mysql 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    summary = ImportSummary()
    conn = connect(args)
    try:
        with conn.cursor() as cursor:
            if args.create_tables:
                ensure_schema(cursor)
            uploader_id = ensure_user(cursor, args.uploader, args.uploader_email)
            existing_games = load_existing_game_index(cursor) if args.skip_existing else {
                "file_keys": set(),
                "content_keys": {},
            }
            player_cache = load_player_cache(cursor)
        conn.commit()

        for source in iter_csa_files(args.input, args.recursive):
            try:
                games = parse_csa_games(source, args.encoding)
            except Exception as exc:
                summary.add_error(source, 0, exc)
                continue

            for game_index, parser in enumerate(games):
                summary.parsed_games += 1
                try:
                    imported, moves_inserted, positions_inserted, file_name_updated = insert_game(
                        conn,
                        parser,
                        source,
                        game_index,
                        uploader_id,
                        args.skip_existing,
                        existing_games,
                        player_cache,
                    )
                    conn.commit()
                except Exception as exc:
                    safe_rollback(conn)
                    summary.add_error(source, game_index, exc)
                    continue

                if imported:
                    summary.imported_games += 1
                    summary.imported_moves += moves_inserted
                    summary.imported_positions += positions_inserted
                elif file_name_updated:
                    summary.updated_file_names += 1
                else:
                    summary.skipped_games += 1

                changed_games = summary.imported_games + summary.updated_file_names
                if (imported or file_name_updated) and args.pause_every > 0 and changed_games % args.pause_every == 0:
                    print(
                        f"Changed {changed_games} games; sleeping {args.pause_seconds} seconds "
                        "to avoid MySQL max_questions limit.",
                        flush=True,
                    )
                    time.sleep(args.pause_seconds)

                if args.max_games is not None and summary.parsed_games >= args.max_games:
                    return summary
    finally:
        conn.close()

    return summary


def main() -> int:
    """功能：串接本檔案的主要執行流程。"""
    args = parse_args()
    summary = dry_run(args) if args.dry_run else import_to_mysql(args)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
