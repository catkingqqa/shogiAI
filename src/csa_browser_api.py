"""功能：提供 CSA 棋譜瀏覽、資料庫查詢、自行對弈與 AI 對弈的 HTTP API。"""
from __future__ import annotations

import argparse
import getpass
import json
import mimetypes
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, unquote, urlparse

import cshogi
from ai_search import evaluate_position, search_best_move
from compare_ai_models import (
    MatchEngine,
    adjudicate_max_plies,
    load_engine,
    play_game,
    summarize,
    terminal_result,
)
from policy_model import PolicyValuePredictor

try:
    import pymysql
except ImportError:
    pymysql = None


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"

MOVE_RE = re.compile(r"^[+-][0-9]{4}[A-Z]{2}$")
BOARD_RANKS = range(1, 10)
BOARD_FILES = range(9, 0, -1)

PIECE_NAMES = {
    "FU": "歩",
    "KY": "香",
    "KE": "桂",
    "GI": "銀",
    "KI": "金",
    "KA": "角",
    "HI": "飛",
    "OU": "玉",
    "TO": "と",
    "NY": "杏",
    "NK": "圭",
    "NG": "全",
    "UM": "馬",
    "RY": "竜",
}

TYPE_TO_KIND = {
    cshogi.PAWN: "FU",
    cshogi.LANCE: "KY",
    cshogi.KNIGHT: "KE",
    cshogi.SILVER: "GI",
    cshogi.GOLD: "KI",
    cshogi.BISHOP: "KA",
    cshogi.ROOK: "HI",
    cshogi.KING: "OU",
    cshogi.PROM_PAWN: "TO",
    cshogi.PROM_LANCE: "NY",
    cshogi.PROM_KNIGHT: "NK",
    cshogi.PROM_SILVER: "NG",
    cshogi.PROM_BISHOP: "UM",
    cshogi.PROM_ROOK: "RY",
}

USI_DROP_TO_KIND = {
    "P": "FU",
    "L": "KY",
    "N": "KE",
    "S": "GI",
    "G": "KI",
    "B": "KA",
    "R": "HI",
}

HAND_INDEX_TO_KIND = {
    0: "FU",
    1: "KY",
    2: "KE",
    3: "GI",
    4: "KI",
    5: "KA",
    6: "HI",
}
HAND_ORDER = ["HI", "KA", "KI", "GI", "KE", "KY", "FU"]
UNPROMOTE = {
    "TO": "FU",
    "NY": "KY",
    "NK": "KE",
    "NG": "GI",
    "UM": "KA",
    "RY": "HI",
}


@dataclass
class Piece:
    """功能：定義 Piece 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    color: str
    kind: str


@dataclass
class MoveRecord:
    """功能：定義 MoveRecord 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    ply: int
    color: str
    from_square: str | None
    to_square: str | None
    piece: str | None
    usi_like: str
    captured: str | None = None


@dataclass
class Position:
    """功能：定義 Position 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    ply: int
    turn: str
    board: dict[str, Piece]
    hands: dict[str, dict[str, int]]
    last_move: MoveRecord | None


@dataclass
class Game:
    """功能：定義 Game 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    id: str
    name: str
    metadata: dict[str, str] = field(default_factory=dict)
    positions: list[Position] = field(default_factory=list)
    moves: list[MoveRecord] = field(default_factory=list)


class GameSource(Protocol):
    """功能：定義 GameSource 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    def list_games(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """功能：處理 list_games 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        ...

    def get_position(self, game_id: str, ply: int) -> dict[str, Any]:
        """功能：處理 get_position 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        ...

    def stats(self) -> dict[str, Any]:
        """功能：處理 stats 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        ...


def clone_board(board: dict[str, Piece]) -> dict[str, Piece]:
    """功能：處理 clone_board 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return {square: Piece(piece.color, piece.kind) for square, piece in board.items()}


def clone_hands(hands: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """功能：處理 clone_hands 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return {color: dict(counts) for color, counts in hands.items()}


def square_name(file_digit: str, rank_digit: str) -> str:
    """功能：處理 square_name 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return f"{file_digit}{rank_digit}"


def opponent(color: str) -> str:
    """功能：處理 opponent 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return "-" if color == "+" else "+"


def empty_hands() -> dict[str, dict[str, int]]:
    """功能：處理 empty_hands 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return {"+": {piece: 0 for piece in HAND_ORDER}, "-": {piece: 0 for piece in HAND_ORDER}}


def add_hand(hands: dict[str, dict[str, int]], color: str, piece: str, delta: int) -> None:
    """功能：處理 add_hand 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    base_piece = UNPROMOTE.get(piece, piece)
    hands[color].setdefault(base_piece, 0)
    hands[color][base_piece] += delta
    if hands[color][base_piece] < 0:
        raise ValueError(f"negative hand count for {color}{base_piece}")


def initial_board() -> dict[str, Piece]:
    """功能：處理 initial_board 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    rows = {
        1: ["-KY", "-KE", "-GI", "-KI", "-OU", "-KI", "-GI", "-KE", "-KY"],
        2: [" * ", "-HI", " * ", " * ", " * ", " * ", " * ", "-KA", " * "],
        3: ["-FU", "-FU", "-FU", "-FU", "-FU", "-FU", "-FU", "-FU", "-FU"],
        4: [" * "] * 9,
        5: [" * "] * 9,
        6: [" * "] * 9,
        7: ["+FU", "+FU", "+FU", "+FU", "+FU", "+FU", "+FU", "+FU", "+FU"],
        8: [" * ", "+KA", " * ", " * ", " * ", " * ", " * ", "+HI", " * "],
        9: ["+KY", "+KE", "+GI", "+KI", "+OU", "+KI", "+GI", "+KE", "+KY"],
    }
    board: dict[str, Piece] = {}
    for rank, cells in rows.items():
        apply_board_row(board, rank, "".join(cells))
    return board


def apply_board_row(board: dict[str, Piece], rank: int, content: str) -> None:
    """功能：處理 apply_board_row 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if len(content) < 27:
        raise ValueError(f"rank P{rank} is too short")

    for index in range(9):
        cell = content[index * 3 : index * 3 + 3]
        file_number = 9 - index
        square = f"{file_number}{rank}"
        if cell == " * ":
            board.pop(square, None)
            continue
        color = cell[0]
        piece = cell[1:3]
        if color not in {"+", "-"} or piece not in PIECE_NAMES:
            raise ValueError(f"invalid board cell at {square}: {cell!r}")
        board[square] = Piece(color=color, kind=piece)


def apply_hand_line(hands: dict[str, dict[str, int]], color: str, content: str) -> None:
    """功能：處理 apply_hand_line 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    compact = content.replace(" ", "")
    for index in range(0, len(compact), 4):
        token = compact[index : index + 4]
        if not token:
            continue
        if len(token) != 4 or token[:2] != "00" or token[2:] not in PIECE_NAMES:
            raise ValueError(f"invalid hand token: {token!r}")
        add_hand(hands, color, token[2:], 1)


def parse_metadata(line: str, metadata: dict[str, str]) -> None:
    """功能：處理 parse_metadata 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if line.startswith("N+") or line.startswith("N-"):
        metadata["black" if line[1] == "+" else "white"] = line[2:].strip()
    elif line.startswith("$") and ":" in line:
        key, value = line[1:].split(":", 1)
        metadata[key.strip().lower()] = value.strip()


def compact_move_text(line: str) -> str:
    """功能：處理 compact_move_text 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return line[0] + line[1:5] + line[5:7]


def csa_move_to_usi_like(color: str, from_square: str | None, to_square: str, piece: str) -> str:
    """功能：處理 csa_move_to_usi_like 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if from_square is None:
        return f"{PIECE_NAMES.get(piece, piece)}*{to_square}"
    return f"{from_square}-{to_square}{PIECE_NAMES.get(piece, piece)}"


def apply_move(
    board: dict[str, Piece],
    hands: dict[str, dict[str, int]],
    ply: int,
    line: str,
) -> MoveRecord:
    """功能：處理 apply_move 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    color = line[0]
    from_square = square_name(line[1], line[2])
    to_square = square_name(line[3], line[4])
    piece = line[5:7]
    is_drop = from_square == "00"
    origin = None if is_drop else from_square

    if piece not in PIECE_NAMES:
        raise ValueError(f"unsupported piece in move {ply}: {piece}")

    captured_piece = board.get(to_square)
    if captured_piece is not None:
        if captured_piece.color == color:
            raise ValueError(f"move {ply} captures own piece on {to_square}")
        add_hand(hands, color, captured_piece.kind, 1)

    if is_drop:
        add_hand(hands, color, piece, -1)
    else:
        moving_piece = board.pop(from_square, None)
        if moving_piece is None:
            raise ValueError(f"move {ply} has no piece on {from_square}")
        if moving_piece.color != color:
            raise ValueError(f"move {ply} moves opponent piece on {from_square}")

    board[to_square] = Piece(color=color, kind=piece)
    return MoveRecord(
        ply=ply,
        color=color,
        from_square=origin,
        to_square=to_square,
        piece=piece,
        usi_like=csa_move_to_usi_like(color, origin, to_square, piece),
        captured=captured_piece.kind if captured_piece else None,
    )


def read_csa_text(path: Path) -> str:
    """功能：處理 read_csa_text 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_csa(path: Path, game_id: str) -> Game:
    """功能：處理 parse_csa 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    board: dict[str, Piece] = {}
    hands = empty_hands()
    turn = "+"
    metadata: dict[str, str] = {}
    moves: list[MoveRecord] = []
    positions: list[Position] = []
    has_board_rows = False

    for raw_line in read_csa_text(path).splitlines():
        line = raw_line.rstrip("\r\n")
        if not line or line.startswith("'"):
            continue

        parse_metadata(line, metadata)

        if line == "PI":
            board = initial_board()
            has_board_rows = True
            continue

        if line.startswith("P") and len(line) >= 2:
            marker = line[1]
            if marker in "123456789":
                apply_board_row(board, int(marker), line[2:])
                has_board_rows = True
                continue
            if marker in "+-":
                apply_hand_line(hands, marker, line[2:])
                continue

        if line in {"+", "-"} and not moves:
            turn = line
            positions.append(Position(0, turn, clone_board(board), clone_hands(hands), None))
            continue

        if MOVE_RE.match(line):
            if not has_board_rows:
                board = initial_board()
                has_board_rows = True
                if not positions:
                    positions.append(Position(0, turn, clone_board(board), clone_hands(hands), None))
            move = apply_move(board, hands, len(moves) + 1, compact_move_text(line))
            moves.append(move)
            turn = opponent(move.color)
            positions.append(Position(len(moves), turn, clone_board(board), clone_hands(hands), move))
            continue

        if line.startswith("%"):
            metadata["result"] = line[1:].strip()

    if not positions:
        if not has_board_rows:
            board = initial_board()
        positions.append(Position(0, turn, clone_board(board), clone_hands(hands), None))

    return Game(id=game_id, name=Path(game_id).name, metadata=metadata, positions=positions, moves=moves)


def text_matches(value: str, needle: str) -> bool:
    """功能：處理 text_matches 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return needle.lower() in (value or "").lower()


def filter_file_games(games: list[dict[str, Any]], filters: dict[str, str]) -> list[dict[str, Any]]:
    """功能：處理 filter_file_games 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    event = filters.get("event", "").strip()
    date_from = filters.get("date_from", "").strip()
    date_to = filters.get("date_to", "").strip()
    player = filters.get("player", "").strip()
    opening = filters.get("opening", "").strip()
    filtered = []

    for game in games:
        if event and not text_matches(game.get("event", ""), event):
            continue
        played_at = str(game.get("startTime", ""))[:10]
        if date_from and (not played_at or played_at < date_from):
            continue
        if date_to and (not played_at or played_at > date_to):
            continue
        if player and not (
            text_matches(game.get("black", ""), player) or text_matches(game.get("white", ""), player)
        ):
            continue
        if opening and not text_matches(game.get("opening", ""), opening):
            continue
        filtered.append(game)

    return sorted(filtered, key=lambda item: (item.get("startTime", ""), item.get("id", "")), reverse=True)


class CsaFileSource:
    """功能：定義 CsaFileSource 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    def list_games(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """功能：處理 list_games 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        games = []
        if not DATA_DIR.exists():
            return games
        for path in sorted(DATA_DIR.rglob("*.csa")):
            game_id = path.relative_to(DATA_DIR).as_posix()
            try:
                game = parse_csa(path, game_id)
                games.append(serialize_game_summary(game))
            except Exception as exc:
                games.append({"id": game_id, "name": path.name, "error": str(exc)})
        return filter_file_games(games, filters or {})

    def get_position(self, game_id: str, ply: int) -> dict[str, Any]:
        """功能：處理 get_position 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        decoded = unquote(game_id).replace("\\", "/")
        path = (DATA_DIR / decoded).resolve()
        data_root = DATA_DIR.resolve()
        if data_root != path and data_root not in path.parents:
            raise FileNotFoundError(game_id)
        if path.suffix.lower() != ".csa" or not path.is_file():
            raise FileNotFoundError(game_id)

        game = parse_csa(path, decoded)
        if ply < 0 or ply >= len(game.positions):
            raise ValueError(f"ply must be between 0 and {len(game.positions) - 1}")
        return serialize_position(game, game.positions[ply])

    def stats(self) -> dict[str, Any]:
        """功能：處理 stats 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        games = self.list_games()
        playable_games = [game for game in games if not game.get("error")]
        return {
            "source": "csa",
            "database": "",
            "games": len(playable_games),
            "players": 0,
            "moves": sum(int(game.get("moves") or 0) for game in playable_games),
            "positions": sum(int(game.get("moves") or 0) + 1 for game in playable_games),
            "duplicateGroups": 0,
        }


@dataclass
class MySqlConfig:
    """功能：定義 MySqlConfig 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class BookMove:
    move_usi: str
    count: int
    total: int

    @property
    def rate(self) -> float:
        return self.count / self.total if self.total else 0.0


class OpeningBook:
    def __init__(self, entries: dict[str, list[BookMove]], max_ply: int, min_count: int) -> None:
        self.entries = entries
        self.max_ply = max_ply
        self.min_count = min_count

    @classmethod
    def from_mysql(cls, config: MySqlConfig, max_ply: int, min_count: int) -> "OpeningBook":
        if pymysql is None:
            raise RuntimeError("PyMySQL is required for MySQL opening book.")
        raw: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        connection = pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p.sfen, m.usi_move
                    FROM positions p
                    JOIN moves m
                      ON m.game_id = p.game_id
                     AND m.move_number = p.move_number + 1
                    WHERE p.move_number < %s
                    ORDER BY p.game_id, p.move_number
                    """,
                    (max_ply,),
                )
                for row in cursor.fetchall():
                    raw[str(row["sfen"])][str(row["usi_move"])] += 1

        entries: dict[str, list[BookMove]] = {}
        for sfen, moves in raw.items():
            total = sum(moves.values())
            ranked = [
                BookMove(move_usi=move_usi, count=count, total=total)
                for move_usi, count in moves.items()
                if count >= min_count
            ]
            ranked.sort(key=lambda item: (item.count, item.move_usi), reverse=True)
            if ranked:
                entries[sfen] = ranked
        return cls(entries, max_ply=max_ply, min_count=min_count)

    def find(self, board: cshogi.Board) -> BookMove | None:
        candidates = self.entries.get(board.sfen())
        if not candidates:
            return None
        for candidate in candidates:
            move = board.move_from_usi(candidate.move_usi)
            if board.is_legal(move):
                return candidate
        return None


class MySqlSource:
    """功能：定義 MySqlSource 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    def __init__(self, config: MySqlConfig):
        """功能：初始化物件狀態與必要資源。"""
        if pymysql is None:
            raise RuntimeError("PyMySQL is not installed. Run `python -m pip install -r requirements.txt`.")
        self.config = config

    def connect(self) -> Any:
        """功能：處理 connect 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        return pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )

    @staticmethod
    def clean_text(value: Any) -> str:
        """功能：處理 clean_text 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if value is None:
            return ""
        text = str(value).strip()
        return "" if text.lower() in {"", "null", "none"} else text

    @classmethod
    def display_name(cls, row: dict[str, Any]) -> str:
        """功能：處理 display_name 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        played_at = row.get("played_at")
        date_text = played_at.isoformat() if played_at else ""
        event_text = cls.clean_text(row.get("event_name"))
        black_text = cls.clean_text(row.get("black_player"))
        white_text = cls.clean_text(row.get("white_player"))
        players_text = ""
        if black_text and white_text:
            players_text = f"{black_text} vs {white_text}"
        elif black_text or white_text:
            players_text = black_text or white_text

        parts = [part for part in (date_text, event_text, players_text) if part]
        if parts:
            return " · ".join(parts)
        return cls.clean_text(row.get("original_file_name")) or f"game-{row['game_id']}"

    @staticmethod
    def like_param(value: str) -> str:
        """功能：處理 like_param 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        return f"%{value.strip()}%"

    def list_games(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """功能：處理 list_games 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        filters = filters or {}
        where_sql, params = self.build_filters(filters)
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        g.game_id,
                        g.original_file_name,
                        COALESCE(bp.player_name, '先手') AS black_player,
                        COALESCE(wp.player_name, '後手') AS white_player,
                        COALESCE(g.event_name, '') AS event_name,
                        COALESCE(g.opening, '') AS opening,
                        COALESCE(g.result, '') AS result,
                        g.played_at,
                        COUNT(m.move_id) AS move_count
                    FROM game_records g
                    LEFT JOIN players bp ON g.black_player_id = bp.player_id
                    LEFT JOIN players wp ON g.white_player_id = wp.player_id
                    LEFT JOIN moves m ON g.game_id = m.game_id
                    {where_sql}
                    GROUP BY
                        g.game_id, g.original_file_name, bp.player_name, wp.player_name,
                        g.event_name, g.opening, g.result, g.played_at
                    ORDER BY g.played_at DESC, g.game_id DESC
                    """,
                    params,
                )
                rows = cursor.fetchall()

        games = []
        for row in rows:
            games.append(
                {
                    "id": str(row["game_id"]),
                    "name": self.display_name(row),
                    "moves": int(row["move_count"]),
                    "black": self.clean_text(row["black_player"]) or "先手",
                    "white": self.clean_text(row["white_player"]) or "後手",
                    "event": self.clean_text(row["event_name"]),
                    "opening": self.clean_text(row["opening"]),
                    "result": self.clean_text(row["result"]),
                    "startTime": row["played_at"].isoformat() if row["played_at"] else "",
                }
            )
        return games

    def build_filters(self, filters: dict[str, str]) -> tuple[str, list[Any]]:
        """功能：處理 build_filters 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        clauses: list[str] = []
        params: list[Any] = []

        event = filters.get("event", "").strip()
        if event:
            clauses.append("COALESCE(g.event_name, '') LIKE %s")
            params.append(self.like_param(event))

        date_from = filters.get("date_from", "").strip()
        if date_from:
            clauses.append("g.played_at >= %s")
            params.append(date_from)

        date_to = filters.get("date_to", "").strip()
        if date_to:
            clauses.append("g.played_at <= %s")
            params.append(date_to)

        player = filters.get("player", "").strip()
        if player:
            clauses.append("(COALESCE(bp.player_name, '') LIKE %s OR COALESCE(wp.player_name, '') LIKE %s)")
            params.extend([self.like_param(player), self.like_param(player)])

        opening = filters.get("opening", "").strip()
        if opening:
            clauses.append("COALESCE(g.opening, '') LIKE %s")
            params.append(self.like_param(opening))

        if not clauses:
            return "", []
        return "WHERE " + " AND ".join(clauses), params

    def get_position(self, game_id: str, ply: int) -> dict[str, Any]:
        """功能：處理 get_position 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        try:
            game_pk = int(game_id)
        except ValueError as exc:
            raise FileNotFoundError(game_id) from exc

        with self.connect() as conn:
            with conn.cursor() as cursor:
                game = self.fetch_game(cursor, game_pk)
                if game is None:
                    raise FileNotFoundError(game_id)

                cursor.execute("SELECT COUNT(*) AS move_count FROM moves WHERE game_id = %s", (game_pk,))
                max_ply = int(cursor.fetchone()["move_count"])
                if ply < 0 or ply > max_ply:
                    raise ValueError(f"ply must be between 0 and {max_ply}")

                cursor.execute(
                    """
                    SELECT move_number, side_to_move, sfen, is_check, legal_moves_count
                    FROM positions
                    WHERE game_id = %s AND move_number = %s
                    LIMIT 1
                    """,
                    (game_pk, ply),
                )
                position = cursor.fetchone()
                if position is None:
                    raise FileNotFoundError(f"position {ply} for game {game_id}")

                cursor.execute(
                    """
                    SELECT move_number, side_to_move, original_move, usi_move, comment
                    FROM moves
                    WHERE game_id = %s
                    ORDER BY move_number
                    """,
                    (game_pk,),
                )
                moves = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT sfen
                    FROM positions
                    WHERE game_id = %s AND move_number = 0
                    LIMIT 1
                    """,
                    (game_pk,),
                )
                initial_position = cursor.fetchone()

        board_obj = cshogi.Board(position["sfen"])
        board, hands = board_from_cshogi(board_obj)
        move_records = (
            move_records_from_db_rows(str(initial_position["sfen"]), moves)
            if initial_position is not None
            else [move_from_db_row(move, None) for move in moves]
        )
        last_move = next((move for move in move_records if move.ply == ply), None)

        return {
            "game": game,
            "ply": ply,
            "maxPly": max_ply,
            "turn": "+" if position["side_to_move"] == "black" else "-",
            "turnLabel": "先手" if position["side_to_move"] == "black" else "後手",
            "board": board_grid(board),
            "hands": hands,
            "handOrder": HAND_ORDER,
            "pieceNames": PIECE_NAMES,
            "lastMove": serialize_move(last_move),
            "moves": [serialize_move(move) for move in move_records],
            "isCheck": bool(position["is_check"]),
            "legalMovesCount": position["legal_moves_count"],
        }

    def fetch_game(self, cursor: Any, game_pk: int) -> dict[str, Any] | None:
        """功能：處理 fetch_game 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        cursor.execute(
            """
            SELECT
                g.game_id,
                g.original_file_name,
                COALESCE(bp.player_name, '先手') AS black_player,
                COALESCE(wp.player_name, '後手') AS white_player,
                COALESCE(g.event_name, '') AS event_name,
                COALESCE(g.opening, '') AS opening,
                COALESCE(g.result, '') AS result,
                g.played_at
            FROM game_records g
            LEFT JOIN players bp ON g.black_player_id = bp.player_id
            LEFT JOIN players wp ON g.white_player_id = wp.player_id
            WHERE g.game_id = %s
            LIMIT 1
            """,
            (game_pk,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cursor.execute("SELECT COUNT(*) AS move_count FROM moves WHERE game_id = %s", (game_pk,))
        move_count = int(cursor.fetchone()["move_count"])
        return {
            "id": str(row["game_id"]),
            "name": self.display_name(row),
            "moves": move_count,
            "black": self.clean_text(row["black_player"]) or "先手",
            "white": self.clean_text(row["white_player"]) or "後手",
            "event": self.clean_text(row["event_name"]),
            "opening": self.clean_text(row["opening"]),
            "result": self.clean_text(row["result"]),
            "startTime": row["played_at"].isoformat() if row["played_at"] else "",
        }

    def stats(self) -> dict[str, Any]:
        """功能：處理 stats 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        with self.connect() as conn:
            with conn.cursor() as cursor:
                counts: dict[str, int] = {}
                for key, table in (
                    ("games", "game_records"),
                    ("players", "players"),
                    ("moves", "moves"),
                    ("positions", "positions"),
                ):
                    cursor.execute(f"SELECT COUNT(1) AS count_value FROM {table}")
                    counts[key] = int(cursor.fetchone()["count_value"])

                cursor.execute(
                    """
                    SELECT COUNT(1) AS count_value
                    FROM (
                        SELECT original_file_name
                        FROM game_records
                        WHERE source_format = 'CSA'
                          AND original_file_name IS NOT NULL
                        GROUP BY original_file_name
                        HAVING COUNT(1) > 1
                    ) duplicated
                    """
                )
                duplicate_groups = int(cursor.fetchone()["count_value"])

        return {
            "source": "mysql",
            "database": self.config.database,
            "games": counts["games"],
            "players": counts["players"],
            "moves": counts["moves"],
            "positions": counts["positions"],
            "duplicateGroups": duplicate_groups,
        }


def cshogi_square_to_browser(square_name_text: str) -> str:
    """功能：處理 cshogi_square_to_browser 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    rank = ord(square_name_text[1]) - ord("a") + 1
    return f"{square_name_text[0]}{rank}"


def usi_square_to_browser(square_name_text: str) -> str:
    """功能：處理 usi_square_to_browser 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if len(square_name_text) != 2:
        return square_name_text
    rank = ord(square_name_text[1]) - ord("a") + 1
    return f"{square_name_text[0]}{rank}"


def board_from_cshogi(board_obj: cshogi.Board) -> tuple[dict[str, Piece], dict[str, dict[str, int]]]:
    """功能：處理 board_from_cshogi 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    board: dict[str, Piece] = {}
    for square_index, piece in enumerate(board_obj.pieces):
        if piece == cshogi.NONE:
            continue
        piece_type = int(board_obj.piece_type(square_index))
        kind = TYPE_TO_KIND[piece_type]
        color = "-" if piece >= 17 else "+"
        square = cshogi_square_to_browser(cshogi.SQUARE_NAMES[square_index])
        board[square] = Piece(color=color, kind=kind)

    hands = empty_hands()
    black_hands, white_hands = board_obj.pieces_in_hand
    for index, kind in HAND_INDEX_TO_KIND.items():
        hands["+"][kind] = int(black_hands[index])
        hands["-"][kind] = int(white_hands[index])
    return board, hands


def move_from_db_row(row: dict[str, Any] | None, board_after_move: dict[str, Piece] | None) -> MoveRecord | None:
    """功能：處理 move_from_db_row 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if row is None:
        return None
    usi = row.get("usi_move") or row.get("original_move") or ""
    from_square: str | None = None
    to_square: str | None = None
    piece: str | None = None

    if len(usi) >= 4 and "*" in usi:
        piece = USI_DROP_TO_KIND.get(usi[0])
        to_square = usi_square_to_browser(usi[2:4])
    elif len(usi) >= 4:
        from_square = usi_square_to_browser(usi[0:2])
        to_square = usi_square_to_browser(usi[2:4])
        if board_after_move is not None and to_square in board_after_move:
            piece = board_after_move[to_square].kind

    return MoveRecord(
        ply=int(row["move_number"]),
        color="+" if row["side_to_move"] == "black" else "-",
        from_square=from_square,
        to_square=to_square,
        piece=piece,
        usi_like=usi,
    )


def move_records_from_db_rows(initial_sfen: str, rows: list[dict[str, Any]]) -> list[MoveRecord]:
    """功能：處理 move_records_from_db_rows 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    board = cshogi.Board(initial_sfen)
    records: list[MoveRecord] = []

    for row in rows:
        usi = row.get("usi_move") or row.get("original_move") or ""
        try:
            move = board.move_from_usi(usi)
            if not board.is_legal(move):
                raise ValueError(f"illegal move: {usi}")
            records.append(move_record_from_usi(board, move, int(row["move_number"])))
            board.push(move)
        except Exception:
            fallback = move_from_db_row(row, None)
            if fallback is not None:
                records.append(fallback)

    return records


def browser_square_from_usi(square_text: str) -> str:
    """功能：處理 browser_square_from_usi 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return usi_square_to_browser(square_text)


def move_record_from_usi(board_before_move: cshogi.Board, move: int, ply: int) -> MoveRecord:
    """功能：處理 move_record_from_usi 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    usi = cshogi.move_to_usi(move)
    board_after_move = board_before_move.copy()
    board_after_move.push(move)
    board_after, _ = board_from_cshogi(board_after_move)

    if "*" in usi:
        from_square = None
        to_square = browser_square_from_usi(usi[2:4])
    else:
        from_square = browser_square_from_usi(usi[0:2])
        to_square = browser_square_from_usi(usi[2:4])

    piece = board_after.get(to_square)
    return MoveRecord(
        ply=ply,
        color="+" if board_before_move.turn == cshogi.BLACK else "-",
        from_square=from_square,
        to_square=to_square,
        piece=piece.kind if piece else None,
        usi_like=usi,
    )


def repetition_key(board: cshogi.Board) -> str:
    """功能：處理 repetition_key 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return " ".join(board.sfen().split()[:3])


def replay_usi_moves(
    moves_usi: list[str],
) -> tuple[cshogi.Board, list[MoveRecord], dict[str, int], int]:
    """功能：處理 replay_usi_moves 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    board = cshogi.Board()
    records: list[MoveRecord] = []
    position_counts = {repetition_key(board): 1}
    max_repetition_count = 1

    for ply, usi in enumerate(moves_usi, start=1):
        move = board.move_from_usi(usi)
        if not board.is_legal(move):
            raise ValueError(f"illegal move at ply {ply}: {usi}")
        records.append(move_record_from_usi(board, move, ply))
        board.push(move)
        key = repetition_key(board)
        position_counts[key] = position_counts.get(key, 0) + 1
        max_repetition_count = max(max_repetition_count, position_counts[key])

    return board, records, position_counts, max_repetition_count


def serialize_legal_move(board: cshogi.Board, move: int) -> dict[str, Any]:
    """功能：處理 serialize_legal_move 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    usi = cshogi.move_to_usi(move)
    record = move_record_from_usi(board, move, 1)
    return {
        "usi": usi,
        "from": record.from_square,
        "to": record.to_square,
        "piece": record.piece,
        "label": PIECE_NAMES.get(record.piece or "", ""),
        "isDrop": "*" in usi,
        "isPromotion": usi.endswith("+"),
    }


def serialize_self_play_state(
    board: cshogi.Board,
    moves: list[MoveRecord],
    max_repetition_count: int,
) -> dict[str, Any]:
    """功能：處理 serialize_self_play_state 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    board_data, hands = board_from_cshogi(board)
    legal_moves = list(board.legal_moves)
    return {
        "game": {
            "id": "self-play",
            "name": "自行對奕",
            "moves": len(moves),
            "black": "先手",
            "white": "後手",
            "event": "",
            "opening": "",
            "result": "",
            "startTime": "",
        },
        "ply": len(moves),
        "maxPly": len(moves),
        "turn": "+" if board.turn == cshogi.BLACK else "-",
        "turnLabel": "先手" if board.turn == cshogi.BLACK else "後手",
        "board": board_grid(board_data),
        "hands": hands,
        "handOrder": HAND_ORDER,
        "pieceNames": PIECE_NAMES,
        "lastMove": serialize_move(moves[-1] if moves else None),
        "moves": [serialize_move(move) for move in moves],
        "isCheck": bool(board.is_check()),
        "legalMovesCount": len(legal_moves),
        "legalMoves": [serialize_legal_move(board, move) for move in legal_moves],
        "repetitionCount": max_repetition_count,
        "isSennichite": max_repetition_count >= 4,
    }


def serialize_ai_play_state(
    board: cshogi.Board,
    moves: list[MoveRecord],
    max_repetition_count: int,
    player_side: str,
    search: dict[str, Any] | None = None,
    resigned_side: str | None = None,
    policy_candidates: list[dict[str, Any]] | None = None,
    value_estimate: float | None = None,
) -> dict[str, Any]:
    """功能：處理 serialize_ai_play_state 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    state = serialize_self_play_state(board, moves, max_repetition_count)
    state["game"] = {
        **state["game"],
        "id": "ai-play",
        "name": "AI 對弈",
        "black": "你" if player_side == "+" else "AI",
        "white": "你" if player_side == "-" else "AI",
    }
    state["playerSide"] = player_side
    state["aiSide"] = "-" if player_side == "+" else "+"
    state["search"] = search
    state["resignedSide"] = resigned_side
    state["policyCandidates"] = policy_candidates or []
    state["valueEstimate"] = value_estimate
    state["isCheckmate"] = state["legalMovesCount"] == 0 and state["isCheck"]
    state["isGameOver"] = bool(
        state["isSennichite"] or state["isCheckmate"] or resigned_side is not None
    )
    if resigned_side is not None:
        state["result"] = "resignation"
        state["winner"] = "-" if resigned_side == "+" else "+"
    elif state["isSennichite"]:
        state["result"] = "sennichite"
        state["winner"] = None
    elif state["isCheckmate"]:
        state["result"] = "checkmate"
        state["winner"] = "-" if state["turn"] == "+" else "+"
    else:
        state["result"] = ""
        state["winner"] = None
    return state


def csa_square_from_usi(square_text: str) -> str:
    """功能：處理 csa_square_from_usi 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    rank = ord(square_text[1]) - ord("a") + 1
    return f"{square_text[0]}{rank}"


def move_to_csa_line(board_before_move: cshogi.Board, move: int) -> str:
    """功能：處理 move_to_csa_line 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    usi = cshogi.move_to_usi(move)
    color = "+" if board_before_move.turn == cshogi.BLACK else "-"
    from_square = "00" if "*" in usi else csa_square_from_usi(usi[0:2])
    to_square = csa_square_from_usi(usi[2:4] if "*" in usi else usi[2:4])

    board_after_move = board_before_move.copy()
    board_after_move.push(move)
    piece_type = int(board_after_move.piece_type(cshogi.move_to(move)))
    return f"{color}{from_square}{to_square}{TYPE_TO_KIND[piece_type]}"


CSA_RESULT_CODES = {"", "TORYO", "SENNICHITE", "JISHOGI"}


def build_csa_text(moves_usi: list[str], black_name: str, white_name: str, result_code: str = "") -> str:
    """功能：處理 build_csa_text 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if result_code not in CSA_RESULT_CODES:
        raise ValueError("unsupported result code")
    board = cshogi.Board()
    lines = [
        "V2.2",
        f"N+{black_name or '先手'}",
        f"N-{white_name or '後手'}",
        "PI",
        "+",
    ]

    for ply, usi in enumerate(moves_usi, start=1):
        move = board.move_from_usi(usi)
        if not board.is_legal(move):
            raise ValueError(f"illegal move at ply {ply}: {usi}")
        lines.append(move_to_csa_line(board, move))
        board.push(move)

    if result_code:
        lines.append(f"%{result_code}")

    return "\n".join(lines) + "\n"


def serialize_piece(piece: Piece | None) -> dict[str, str] | None:
    """功能：處理 serialize_piece 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if piece is None:
        return None
    return {
        "color": piece.color,
        "piece": piece.kind,
        "label": PIECE_NAMES[piece.kind],
        "promoted": piece.kind in UNPROMOTE,
    }


def serialize_move(move: MoveRecord | None) -> dict[str, Any] | None:
    """功能：處理 serialize_move 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if move is None:
        return None
    return {
        "ply": move.ply,
        "color": move.color,
        "from": move.from_square,
        "to": move.to_square,
        "piece": move.piece,
        "label": PIECE_NAMES.get(move.piece or "", ""),
        "text": move.usi_like,
        "captured": move.captured,
    }


def board_grid(board: dict[str, Piece]) -> list[list[dict[str, Any]]]:
    """功能：處理 board_grid 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    rows = []
    for rank in BOARD_RANKS:
        row = []
        for file_number in BOARD_FILES:
            square = f"{file_number}{rank}"
            row.append({"square": square, "piece": serialize_piece(board.get(square))})
        rows.append(row)
    return rows


def serialize_position(game: Game, position: Position) -> dict[str, Any]:
    """功能：處理 serialize_position 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return {
        "game": serialize_game_summary(game),
        "ply": position.ply,
        "maxPly": len(game.moves),
        "turn": position.turn,
        "turnLabel": "先手" if position.turn == "+" else "後手",
        "board": board_grid(position.board),
        "hands": position.hands,
        "handOrder": HAND_ORDER,
        "pieceNames": PIECE_NAMES,
        "lastMove": serialize_move(position.last_move),
        "moves": [serialize_move(move) for move in game.moves],
    }


def serialize_game_summary(game: Game) -> dict[str, Any]:
    """功能：處理 serialize_game_summary 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    return {
        "id": game.id,
        "name": game.name,
        "moves": len(game.moves),
        "black": game.metadata.get("black", "先手"),
        "white": game.metadata.get("white", "後手"),
        "event": game.metadata.get("event", ""),
        "startTime": game.metadata.get("start_time", ""),
        "result": game.metadata.get("result", ""),
    }


class CsaBrowserHandler(BaseHTTPRequestHandler):
    """功能：定義 CsaBrowserHandler 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    server_version = "CsaBrowser/0.2"
    source: GameSource
    policy_predictor: PolicyValuePredictor | None = None
    opening_book: OpeningBook | None = None
    match_engine_cache: dict[tuple[str, str, int, int, int], MatchEngine] = {}
    value_weight = 0
    policy_order_ply = 2

    def do_GET(self) -> None:
        """功能：處理 do_GET 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        try:
            self.route_get()
        except FileNotFoundError:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        """功能：處理 do_POST 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        try:
            self.route_post()
        except FileNotFoundError:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def route_get(self) -> None:
        """功能：處理 route_get 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/games":
            filters = {key: values[0] for key, values in parse_qs(parsed.query).items() if values and values[0].strip()}
            self.send_json({"games": self.source.list_games(filters)})
            return
        if path == "/api/db/stats":
            self.send_json({"stats": self.source.stats()})
            return
        if path == "/api/model-match/models":
            self.send_json({"models": self.model_match_models()})
            return
        if path.startswith("/api/games/"):
            self.api_position(path.removeprefix("/api/games/"), parsed.query)
            return
        self.serve_static(path)

    def route_post(self) -> None:
        """功能：處理 route_post 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        parsed = urlparse(self.path)
        if parsed.path == "/api/self-play/state":
            payload = self.read_json_body()
            moves = self.parse_moves_payload(payload)
            board, records, _, max_repetition_count = replay_usi_moves(moves)
            self.send_json(serialize_self_play_state(board, records, max_repetition_count))
            return
        if parsed.path == "/api/self-play/csa":
            payload = self.read_json_body()
            moves = self.parse_moves_payload(payload)
            csa = build_csa_text(
                moves,
                str(payload.get("blackName", "先手")).strip() or "先手",
                str(payload.get("whiteName", "後手")).strip() or "後手",
                str(payload.get("result", "")).strip(),
            )
            self.send_json({"csa": csa})
            return
        if parsed.path == "/api/ai-play/state":
            payload = self.read_json_body()
            moves = self.parse_moves_payload(payload)
            player_side = self.parse_player_side(payload)
            resigned_side = self.parse_optional_side(payload.get("resignedSide"))
            board, records, _, max_repetition_count = replay_usi_moves(moves)
            policy_candidates = self.serialize_policy_candidates(board, limit=5)
            value_estimate = self.value_estimate(board)
            self.send_json(
                serialize_ai_play_state(
                    board,
                    records,
                    max_repetition_count,
                    player_side=player_side,
                    resigned_side=resigned_side,
                    policy_candidates=policy_candidates,
                    value_estimate=value_estimate,
                )
            )
            return
        if parsed.path == "/api/ai-play/move":
            payload = self.read_json_body()
            moves = self.parse_moves_payload(payload)
            player_side = self.parse_player_side(payload)
            board, records, position_counts, max_repetition_count = replay_usi_moves(moves)
            ai_side = "-" if player_side == "+" else "+"
            if ("+" if board.turn == cshogi.BLACK else "-") != ai_side:
                raise ValueError("it is not the AI turn")
            if max_repetition_count >= 4:
                self.send_json(
                    serialize_ai_play_state(
                        board,
                        records,
                        max_repetition_count,
                        player_side=player_side,
                    )
                )
                return

            book_move = self.opening_book.find(board) if self.opening_book is not None else None
            selected_move: int | None = None
            if book_move is not None:
                selected_move = board.move_from_usi(book_move.move_usi)
                search_payload = {
                    "source": "openingBook",
                    "score": 0,
                    "depth": 0,
                    "nodes": 0,
                    "timedOut": False,
                    "pv": [book_move.move_usi],
                    "bookCount": book_move.count,
                    "bookTotal": book_move.total,
                    "bookRate": book_move.rate,
                }
            else:
                depth = self.parse_search_depth(payload)
                time_limit_ms = self.parse_time_limit_ms(payload)
                result = search_best_move(
                    board,
                    position_counts,
                    depth,
                    time_limit_ms,
                    move_orderer=self.order_moves_with_policy if self.policy_predictor else None,
                    root_move_evaluator=self.root_value_bonus
                    if self.policy_predictor and self.value_weight > 0
                    else None,
                    move_orderer_max_ply=self.policy_order_ply,
                )
                selected_move = result.move
                search_payload = {
                    "source": "search",
                    "score": result.score,
                    "depth": result.depth,
                    "nodes": result.nodes,
                    "timedOut": result.timed_out,
                    "pv": [cshogi.move_to_usi(move) for move in result.pv],
                }
            if selected_move is not None:
                records.append(move_record_from_usi(board, selected_move, len(records) + 1))
                board.push(selected_move)
                key = repetition_key(board)
                position_counts[key] = position_counts.get(key, 0) + 1
                max_repetition_count = max(max_repetition_count, position_counts[key])

            policy_candidates = self.serialize_policy_candidates(board, limit=5)
            value_estimate = self.value_estimate(board)
            self.send_json(
                serialize_ai_play_state(
                    board,
                    records,
                    max_repetition_count,
                    player_side=player_side,
                    search=search_payload,
                    policy_candidates=policy_candidates,
                    value_estimate=value_estimate,
                )
            )
            return
        if parsed.path == "/api/policy/candidates":
            payload = self.read_json_body()
            moves = self.parse_moves_payload(payload)
            board, _, _, _ = replay_usi_moves(moves)
            self.send_json(
                {
                    "available": self.policy_predictor is not None,
                    "valueEstimate": self.value_estimate(board),
                    "candidates": self.serialize_policy_candidates(
                        board,
                        limit=self.parse_candidate_limit(payload),
                    ),
                }
            )
            return
        if parsed.path == "/api/model-match/step":
            payload = self.read_json_body()
            self.send_json(self.run_model_match_step(payload))
            return
        if parsed.path == "/api/model-match/run":
            payload = self.read_json_body()
            self.send_json({"match": self.run_model_match(payload)})
            return
        raise FileNotFoundError(parsed.path)

    def api_position(self, game_id: str, query: str) -> None:
        """功能：處理 api_position 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        params = parse_qs(query)
        ply_text = params.get("ply", ["0"])[0]
        try:
            ply = int(ply_text)
        except ValueError as exc:
            raise ValueError("ply must be an integer") from exc

        self.send_json(self.source.get_position(unquote(game_id), ply))

    def read_json_body(self) -> dict[str, Any]:
        """功能：處理 read_json_body 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    @staticmethod
    def parse_moves_payload(payload: dict[str, Any]) -> list[str]:
        """功能：處理 parse_moves_payload 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        moves = payload.get("moves", [])
        if not isinstance(moves, list) or not all(isinstance(move, str) for move in moves):
            raise ValueError("moves must be a list of USI strings")
        return moves

    @staticmethod
    def parse_player_side(payload: dict[str, Any]) -> str:
        """功能：處理 parse_player_side 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        side = str(payload.get("playerSide", "+")).strip()
        if side not in {"+", "-"}:
            raise ValueError("playerSide must be '+' or '-'")
        return side

    @staticmethod
    def parse_optional_side(value: Any) -> str | None:
        """功能：處理 parse_optional_side 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if value in {None, ""}:
            return None
        side = str(value).strip()
        if side not in {"+", "-"}:
            raise ValueError("side must be '+' or '-'")
        return side

    @staticmethod
    def parse_search_depth(payload: dict[str, Any]) -> int:
        """功能：處理 parse_search_depth 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        try:
            depth = int(payload.get("depth", 3))
        except (TypeError, ValueError) as exc:
            raise ValueError("depth must be an integer") from exc
        if not 1 <= depth <= 5:
            raise ValueError("depth must be between 1 and 5")
        return depth

    @staticmethod
    def parse_time_limit_ms(payload: dict[str, Any]) -> int | None:
        """功能：處理 parse_time_limit_ms 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        raw = payload.get("timeLimitMs", 1000)
        if raw in {None, ""}:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("timeLimitMs must be an integer") from exc
        if not 50 <= value <= 60_000:
            raise ValueError("timeLimitMs must be between 50 and 60000")
        return value

    @staticmethod
    def parse_candidate_limit(payload: dict[str, Any]) -> int:
        """功能：處理 parse_candidate_limit 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        try:
            limit = int(payload.get("limit", 5))
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be an integer") from exc
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        return limit

    def order_moves_with_policy(self, board: cshogi.Board, legal_moves: Any) -> list[int]:
        """功能：處理 order_moves_with_policy 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if self.policy_predictor is None:
            return list(legal_moves)
        return [candidate.move for candidate in self.policy_predictor.rank_legal_moves(board, legal_moves)]

    def serialize_policy_candidates(self, board: cshogi.Board, limit: int = 5) -> list[dict[str, Any]]:
        """功能：處理 serialize_policy_candidates 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if self.policy_predictor is None:
            return []
        ranked = self.policy_predictor.rank_legal_moves(board)[:limit]
        candidates = []
        for candidate in ranked:
            serialized = serialize_legal_move(board, candidate.move)
            serialized["policyScore"] = candidate.score
            serialized["probability"] = candidate.probability
            candidates.append(serialized)
        return candidates

    def evaluate_with_value_head(self, board: cshogi.Board) -> int:
        """功能：處理 evaluate_with_value_head 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if self.policy_predictor is None:
            return evaluate_position(board)
        value_bonus = int(round(self.policy_predictor.value_for_board(board) * self.value_weight))
        return evaluate_position(board) + value_bonus

    def root_value_bonus(self, board_after_ai_move: cshogi.Board) -> int:
        """功能：處理 root_value_bonus 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if self.policy_predictor is None:
            return 0
        return int(round(-self.policy_predictor.value_for_board(board_after_ai_move) * self.value_weight))

    def value_estimate(self, board: cshogi.Board) -> float | None:
        """功能：處理 value_estimate 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if self.policy_predictor is None:
            return None
        return self.policy_predictor.value_for_board(board)

    def model_match_models(self) -> list[dict[str, Any]]:
        models = []
        for path in sorted((ROOT / "out").glob("policy_model*.pt")):
            if not path.is_file():
                continue
            stat = path.stat()
            models.append(
                {
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "name": path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
            )
        return models

    def resolve_model_path(self, value: Any) -> Path:
        text = str(value or "").strip().replace("\\", "/")
        if not text:
            raise ValueError("model path is required")
        path = (ROOT / text).resolve()
        out_root = (ROOT / "out").resolve()
        if out_root != path.parent and out_root not in path.parents:
            raise ValueError("model path must be inside out/")
        if not path.is_file() or not path.name.startswith("policy_model") or path.suffix.lower() != ".pt":
            raise ValueError(f"invalid policy model: {text}")
        return path

    def resolve_optional_model_path(self, value: Any) -> Path | None:
        text = str(value or "").strip()
        if not text:
            return None
        return self.resolve_model_path(text)

    def parse_model_match_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        engine_a_payload = payload.get("engineA") if isinstance(payload.get("engineA"), dict) else {}
        engine_b_payload = payload.get("engineB") if isinstance(payload.get("engineB"), dict) else {}
        new_model = self.resolve_optional_model_path(engine_a_payload.get("model", payload.get("newModel")))
        old_model = self.resolve_optional_model_path(engine_b_payload.get("model", payload.get("oldModel")))
        new_name = str(engine_a_payload.get("name") or payload.get("newName") or "Engine A").strip() or "Engine A"
        old_name = str(engine_b_payload.get("name") or payload.get("oldName") or "Engine B").strip() or "Engine B"
        new_depth = self.clamp_int(engine_a_payload.get("depth", payload.get("depth", 2)), 1, 5, "engineA.depth")
        old_depth = self.clamp_int(engine_b_payload.get("depth", payload.get("depth", 2)), 1, 5, "engineB.depth")
        new_time_limit_ms = self.min_int(
            engine_a_payload.get("timeLimitMs", payload.get("timeLimitMs", 300)),
            50,
            "engineA.timeLimitMs",
        )
        old_time_limit_ms = self.min_int(
            engine_b_payload.get("timeLimitMs", payload.get("timeLimitMs", 300)),
            50,
            "engineB.timeLimitMs",
        )
        new_policy_order_ply = self.clamp_int(
            engine_a_payload.get("policyOrderPly", payload.get("policyOrderPly", 2)),
            0,
            5,
            "engineA.policyOrderPly",
        )
        old_policy_order_ply = self.clamp_int(
            engine_b_payload.get("policyOrderPly", payload.get("policyOrderPly", 2)),
            0,
            5,
            "engineB.policyOrderPly",
        )
        return {
            "games": self.clamp_int(payload.get("games", 2), 1, 10, "games"),
            "max_plies": self.clamp_int(payload.get("maxPlies", 120), 10, 256, "maxPlies"),
            "adjudicate_score": self.clamp_int(payload.get("adjudicateScore", 1000), 0, 10000, "adjudicateScore"),
            "new_name": new_name,
            "old_name": old_name,
            "new_model": new_model,
            "old_model": old_model,
            "new_depth": new_depth,
            "old_depth": old_depth,
            "new_time_limit_ms": new_time_limit_ms,
            "old_time_limit_ms": old_time_limit_ms,
            "new_policy_order_ply": new_policy_order_ply,
            "old_policy_order_ply": old_policy_order_ply,
        }

    def cached_match_engine(
        self,
        name: str,
        model: Path | None,
        depth: int,
        time_limit_ms: int,
        policy_order_ply: int,
    ) -> MatchEngine:
        key = (name, str(model or ""), depth, time_limit_ms, policy_order_ply)
        engine = self.match_engine_cache.get(key)
        if engine is None:
            engine = load_engine(
                name,
                model,
                model is None,
                depth=depth,
                time_limit_ms=time_limit_ms,
                policy_order_ply=policy_order_ply,
            )
            self.match_engine_cache[key] = engine
        return engine

    def model_match_settings_payload(self, config: dict[str, Any]) -> dict[str, Any]:
        new_model = config["new_model"]
        old_model = config["old_model"]
        return {
            "engineA": {
                "name": config["new_name"],
                "model": str(new_model.relative_to(ROOT)).replace("\\", "/") if new_model else "",
                "depth": config["new_depth"],
                "timeLimitMs": config["new_time_limit_ms"],
                "policyOrderPly": config["new_policy_order_ply"],
            },
            "engineB": {
                "name": config["old_name"],
                "model": str(old_model.relative_to(ROOT)).replace("\\", "/") if old_model else "",
                "depth": config["old_depth"],
                "timeLimitMs": config["old_time_limit_ms"],
                "policyOrderPly": config["old_policy_order_ply"],
            },
            "games": config["games"],
            "maxPlies": config["max_plies"],
            "adjudicateScore": config["adjudicate_score"],
        }

    def run_model_match_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = self.parse_model_match_config(payload)
        game_index = self.clamp_int(payload.get("game", 1), 1, config["games"], "game")
        moves = self.parse_moves_payload(payload)
        if len(moves) > config["max_plies"]:
            raise ValueError("moves exceeds maxPlies")

        new_engine = self.cached_match_engine(
            config["new_name"],
            config["new_model"],
            config["new_depth"],
            config["new_time_limit_ms"],
            config["new_policy_order_ply"],
        )
        old_engine = self.cached_match_engine(
            config["old_name"],
            config["old_model"],
            config["old_depth"],
            config["old_time_limit_ms"],
            config["old_policy_order_ply"],
        )
        if game_index % 2 == 1:
            black_engine, white_engine = new_engine, old_engine
        else:
            black_engine, white_engine = old_engine, new_engine

        raw_scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
        scores = {
            config["new_name"]: float(raw_scores.get(config["new_name"], 0) or 0),
            config["old_name"]: float(raw_scores.get(config["old_name"], 0) or 0),
        }
        board, records, position_counts, max_repetition_count = replay_usi_moves(moves)

        result = "running"
        reason = "playing"
        winner_side: str | None = None
        search_payload: dict[str, Any] | None = None

        terminal = terminal_result(board)
        if terminal is not None:
            result, winner_side, _, reason = terminal
        elif max_repetition_count >= 4:
            result = "draw"
            reason = "sennichite"
        elif len(moves) >= config["max_plies"]:
            result, winner_side, reason = adjudicate_max_plies(board, config["adjudicate_score"])
        else:
            engine = black_engine if board.turn == cshogi.BLACK else white_engine
            search = search_best_move(
                board,
                position_counts,
                engine.depth,
                engine.time_limit_ms,
                move_orderer=engine.order_moves if engine.predictor is not None else None,
                move_orderer_max_ply=engine.policy_order_ply,
            )
            search_payload = {
                "engine": engine.name,
                "score": search.score,
                "depth": search.depth,
                "nodes": search.nodes,
                "timedOut": search.timed_out,
                "pv": [cshogi.move_to_usi(move) for move in search.pv],
            }
            if search.move is None:
                result = "draw"
                reason = "no selected move"
            else:
                scores[engine.name] = scores.get(engine.name, 0.0) + search.score
                moves = [*moves, cshogi.move_to_usi(search.move)]
                records.append(move_record_from_usi(board, search.move, len(records) + 1))
                board.push(search.move)
                key = repetition_key(board)
                position_counts[key] = position_counts.get(key, 0) + 1
                max_repetition_count = max(max_repetition_count, position_counts[key])

                terminal = terminal_result(board)
                if terminal is not None:
                    result, winner_side, _, reason = terminal
                elif max_repetition_count >= 4:
                    result = "draw"
                    reason = "sennichite"
                elif len(moves) >= config["max_plies"]:
                    result, winner_side, reason = adjudicate_max_plies(board, config["adjudicate_score"])

        winner_name = None
        if winner_side is not None:
            winner_name = black_engine.name if winner_side == "black" else white_engine.name

        game = {
            "game": game_index,
            "black": black_engine.name,
            "white": white_engine.name,
            "result": result,
            "winner": winner_name,
            "winner_side": winner_side,
            "plies": len(moves),
            "reason": reason,
            "moves": moves,
            "new_score": scores.get(config["new_name"], 0.0),
            "old_score": scores.get(config["old_name"], 0.0),
        }
        return {
            "game": game,
            "state": serialize_self_play_state(board, records, max_repetition_count),
            "done": result != "running",
            "scores": scores,
            "search": search_payload,
        }

    def run_model_match(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = self.parse_model_match_config(payload)
        old_engine = self.cached_match_engine(
            config["old_name"],
            config["old_model"],
            config["old_depth"],
            config["old_time_limit_ms"],
            config["old_policy_order_ply"],
        )
        new_engine = self.cached_match_engine(
            config["new_name"],
            config["new_model"],
            config["new_depth"],
            config["new_time_limit_ms"],
            config["new_policy_order_ply"],
        )
        results = []
        for game_index in range(1, config["games"] + 1):
            if game_index % 2 == 1:
                black_engine, white_engine = new_engine, old_engine
            else:
                black_engine, white_engine = old_engine, new_engine
            results.append(
                play_game(
                    game_index=game_index,
                    black_engine=black_engine,
                    white_engine=white_engine,
                    new_name=config["new_name"],
                    old_name=config["old_name"],
                    max_plies=config["max_plies"],
                    adjudicate_score=config["adjudicate_score"],
                )
            )
        return {
            **summarize(results, config["new_name"], config["old_name"]),
            "settings": self.model_match_settings_payload(config),
        }

    @staticmethod
    def clamp_int(value: Any, minimum: int, maximum: int, name: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if not minimum <= parsed <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
        return parsed

    @staticmethod
    def min_int(value: Any, minimum: int, name: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if parsed < minimum:
            raise ValueError(f"{name} must be at least {minimum}")
        return parsed

    def serve_static(self, request_path: str) -> None:
        """功能：處理 serve_static 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        if request_path in {"", "/"}:
            request_path = "/index.html"
        relative = unquote(request_path.lstrip("/")).replace("\\", "/")
        path = (WEB_DIR / relative).resolve()
        web_root = WEB_DIR.resolve()
        if web_root != path and web_root not in path.parents:
            raise FileNotFoundError(relative)
        if not path.is_file():
            raise FileNotFoundError(relative)

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        """功能：處理 send_json 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """功能：處理 log_message 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
        print(f"{self.address_string()} - {format % args}")


def parse_args() -> argparse.Namespace:
    """功能：解析命令列參數，讓使用者可以調整輸入、輸出與執行選項。"""
    parser = argparse.ArgumentParser(description="Serve a CSA game browser and JSON API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--source", choices=["mysql", "csa"], default="mysql")
    parser.add_argument("--db-host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--db-user", default=os.getenv("MYSQL_USER"))
    parser.add_argument("--db-password", default=os.getenv("MYSQL_PASSWORD"))
    parser.add_argument("--db-name", default=os.getenv("MYSQL_DATABASE", "DB11211213"))
    parser.add_argument("--policy-model", type=Path, default=ROOT / "out" / "policy_model.pt")
    parser.add_argument(
        "--value-weight",
        type=int,
        default=0,
        help="Value-head bonus weight for root move scoring; 0 disables value scoring",
    )
    parser.add_argument(
        "--policy-order-ply",
        type=int,
        default=2,
        help="Use neural policy move ordering only before this search ply; lower values are faster",
    )
    parser.add_argument(
        "--opening-book-ply",
        type=int,
        default=30,
        help="Use database opening book before this ply; 0 disables opening book",
    )
    parser.add_argument(
        "--opening-book-min-count",
        type=int,
        default=2,
        help="Minimum database frequency required for a book move",
    )
    return parser.parse_args()


def build_mysql_config(args: argparse.Namespace) -> MySqlConfig:
    """功能：處理 build_source 流程，整理輸入資料、執行核心邏輯，並回傳後續程式需要的結果。"""
    if not args.db_user:
        raise SystemExit("Missing --db-user or MYSQL_USER.")
    password = args.db_password
    if password is None:
        password = getpass.getpass(f"MySQL password for {args.db_user}@{args.db_host}: ")
    return MySqlConfig(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=password,
        database=args.db_name,
    )


def build_source(args: argparse.Namespace, mysql_config: MySqlConfig | None = None) -> GameSource:
    """?嚗???build_source 瘚?嚗?撓?亥??銵敹?頛荔?銝血??喳?蝥?撘?閬?蝯???"""
    if args.source == "csa":
        return CsaFileSource()
    return MySqlSource(mysql_config or build_mysql_config(args))


def main() -> int:
    """功能：串接本檔案的主要執行流程。"""
    args = parse_args()
    mysql_config = build_mysql_config(args) if args.source == "mysql" else None
    CsaBrowserHandler.source = build_source(args, mysql_config)
    CsaBrowserHandler.policy_predictor = (
        PolicyValuePredictor(args.policy_model) if args.policy_model.is_file() else None
    )
    CsaBrowserHandler.opening_book = None
    if mysql_config is not None and args.opening_book_ply > 0:
        try:
            CsaBrowserHandler.opening_book = OpeningBook.from_mysql(
                mysql_config,
                max_ply=max(0, args.opening_book_ply),
                min_count=max(1, args.opening_book_min_count),
            )
            print(
                "Opening book loaded: "
                f"{len(CsaBrowserHandler.opening_book.entries)} positions, "
                f"max ply {CsaBrowserHandler.opening_book.max_ply}, "
                f"min count {CsaBrowserHandler.opening_book.min_count}"
            )
        except Exception as exc:
            print(f"Opening book disabled: {exc}")
    CsaBrowserHandler.value_weight = max(0, args.value_weight)
    CsaBrowserHandler.policy_order_ply = max(0, args.policy_order_ply)
    server = ThreadingHTTPServer((args.host, args.port), CsaBrowserHandler)
    print(f"CSA browser running at http://{args.host}:{args.port}")
    print(f"Data source: {args.source}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
