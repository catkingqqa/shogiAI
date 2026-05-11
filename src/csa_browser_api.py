from __future__ import annotations

import argparse
import json
import mimetypes
import re
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"

MOVE_RE = re.compile(r"^[+-][0-9]{4}[A-Z]{2}$")
BOARD_RANKS = range(1, 10)
BOARD_FILES = range(9, 0, -1)

PIECE_NAMES = {
    "FU": "步",
    "KY": "香",
    "KE": "桂",
    "GI": "銀",
    "KI": "金",
    "KA": "角",
    "HI": "飛",
    "OU": "玉",
    "TO": "と",
    "NY": "成香",
    "NK": "成桂",
    "NG": "成銀",
    "UM": "馬",
    "RY": "龍",
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
    color: str
    kind: str


@dataclass
class MoveRecord:
    ply: int
    color: str
    from_square: str | None
    to_square: str
    piece: str
    usi_like: str
    captured: str | None = None


@dataclass
class Position:
    ply: int
    turn: str
    board: dict[str, Piece]
    hands: dict[str, dict[str, int]]
    last_move: MoveRecord | None


@dataclass
class Game:
    id: str
    path: Path
    metadata: dict[str, str] = field(default_factory=dict)
    positions: list[Position] = field(default_factory=list)
    moves: list[MoveRecord] = field(default_factory=list)


def clone_board(board: dict[str, Piece]) -> dict[str, Piece]:
    return {square: Piece(piece.color, piece.kind) for square, piece in board.items()}


def clone_hands(hands: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return {color: dict(counts) for color, counts in hands.items()}


def square_name(file_digit: str, rank_digit: str) -> str:
    return f"{file_digit}{rank_digit}"


def opponent(color: str) -> str:
    return "-" if color == "+" else "+"


def empty_hands() -> dict[str, dict[str, int]]:
    return {"+": {piece: 0 for piece in HAND_ORDER}, "-": {piece: 0 for piece in HAND_ORDER}}


def add_hand(hands: dict[str, dict[str, int]], color: str, piece: str, delta: int) -> None:
    base_piece = UNPROMOTE.get(piece, piece)
    hands[color].setdefault(base_piece, 0)
    hands[color][base_piece] += delta
    if hands[color][base_piece] < 0:
        raise ValueError(f"negative hand count for {color}{base_piece}")


def initial_board() -> dict[str, Piece]:
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
    compact = content.replace(" ", "")
    for index in range(0, len(compact), 4):
        token = compact[index : index + 4]
        if not token:
            continue
        if len(token) != 4 or token[:2] != "00" or token[2:] not in PIECE_NAMES:
            raise ValueError(f"invalid hand token: {token!r}")
        add_hand(hands, color, token[2:], 1)


def parse_metadata(line: str, metadata: dict[str, str]) -> None:
    if line.startswith("N+") or line.startswith("N-"):
        metadata["black" if line[1] == "+" else "white"] = line[2:].strip()
    elif line.startswith("$") and ":" in line:
        key, value = line[1:].split(":", 1)
        metadata[key.strip().lower()] = value.strip()


def compact_move_text(line: str) -> str:
    return line[0] + line[1:5] + line[5:7]


def csa_move_to_usi_like(color: str, from_square: str | None, to_square: str, piece: str) -> str:
    if from_square is None:
        return f"{PIECE_NAMES.get(piece, piece)}*{to_square}"
    return f"{from_square}-{to_square}{PIECE_NAMES.get(piece, piece)}"


def apply_move(
    board: dict[str, Piece],
    hands: dict[str, dict[str, int]],
    ply: int,
    line: str,
) -> MoveRecord:
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
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_csa(path: Path, game_id: str) -> Game:
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
            positions.append(
                Position(
                    ply=0,
                    turn=turn,
                    board=clone_board(board),
                    hands=clone_hands(hands),
                    last_move=None,
                )
            )
            continue

        if MOVE_RE.match(line):
            if not has_board_rows:
                board = initial_board()
                has_board_rows = True
                if not positions:
                    positions.append(
                        Position(
                            ply=0,
                            turn=turn,
                            board=clone_board(board),
                            hands=clone_hands(hands),
                            last_move=None,
                        )
                    )
            move = apply_move(board, hands, len(moves) + 1, compact_move_text(line))
            moves.append(move)
            turn = opponent(move.color)
            positions.append(
                Position(
                    ply=len(moves),
                    turn=turn,
                    board=clone_board(board),
                    hands=clone_hands(hands),
                    last_move=move,
                )
            )
            continue

        if line.startswith("%"):
            metadata["result"] = line[1:].strip()

    if not positions:
        if not has_board_rows:
            board = initial_board()
        positions.append(
            Position(ply=0, turn=turn, board=clone_board(board), hands=clone_hands(hands), last_move=None)
        )

    return Game(id=game_id, path=path, metadata=metadata, positions=positions, moves=moves)


def game_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    return sorted(path for path in DATA_DIR.rglob("*.csa") if path.is_file())


def safe_game_path(game_id: str) -> Path:
    decoded = unquote(game_id).replace("\\", "/")
    path = (DATA_DIR / decoded).resolve()
    data_root = DATA_DIR.resolve()
    if data_root != path and data_root not in path.parents:
        raise FileNotFoundError(game_id)
    if path.suffix.lower() != ".csa" or not path.is_file():
        raise FileNotFoundError(game_id)
    return path


def serialize_piece(piece: Piece | None) -> dict[str, str] | None:
    if piece is None:
        return None
    return {
        "color": piece.color,
        "piece": piece.kind,
        "label": PIECE_NAMES[piece.kind],
        "promoted": piece.kind in UNPROMOTE,
    }


def serialize_move(move: MoveRecord | None) -> dict[str, Any] | None:
    if move is None:
        return None
    return {
        "ply": move.ply,
        "color": move.color,
        "from": move.from_square,
        "to": move.to_square,
        "piece": move.piece,
        "label": PIECE_NAMES[move.piece],
        "text": move.usi_like,
        "captured": move.captured,
    }


def serialize_position(game: Game, position: Position) -> dict[str, Any]:
    board = []
    for rank in BOARD_RANKS:
        row = []
        for file_number in BOARD_FILES:
            square = f"{file_number}{rank}"
            row.append({"square": square, "piece": serialize_piece(position.board.get(square))})
        board.append(row)

    return {
        "game": serialize_game_summary(game),
        "ply": position.ply,
        "maxPly": len(game.moves),
        "turn": position.turn,
        "turnLabel": "先手" if position.turn == "+" else "後手",
        "board": board,
        "hands": position.hands,
        "handOrder": HAND_ORDER,
        "pieceNames": PIECE_NAMES,
        "lastMove": serialize_move(position.last_move),
        "moves": [serialize_move(move) for move in game.moves],
    }


def serialize_game_summary(game: Game) -> dict[str, Any]:
    return {
        "id": game.id,
        "name": game.path.name,
        "moves": len(game.moves),
        "black": game.metadata.get("black", "先手"),
        "white": game.metadata.get("white", "後手"),
        "event": game.metadata.get("event", ""),
        "startTime": game.metadata.get("start_time", ""),
        "result": game.metadata.get("result", ""),
    }


class CsaBrowserHandler(BaseHTTPRequestHandler):
    server_version = "CsaBrowser/0.1"

    def do_GET(self) -> None:
        try:
            self.route_get()
        except FileNotFoundError:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def route_get(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/games":
            self.api_games()
            return
        if path.startswith("/api/games/"):
            self.api_position(path.removeprefix("/api/games/"), parsed.query)
            return
        self.serve_static(path)

    def api_games(self) -> None:
        games = []
        for path in game_files():
            game_id = path.relative_to(DATA_DIR).as_posix()
            try:
                game = parse_csa(path, game_id)
                games.append(serialize_game_summary(game))
            except Exception as exc:
                games.append({"id": game_id, "name": path.name, "error": str(exc)})
        self.send_json({"games": games})

    def api_position(self, game_id: str, query: str) -> None:
        params = parse_qs(query)
        ply_text = params.get("ply", ["0"])[0]
        try:
            ply = int(ply_text)
        except ValueError as exc:
            raise ValueError("ply must be an integer") from exc

        path = safe_game_path(game_id)
        game = parse_csa(path, unquote(game_id))
        if ply < 0 or ply >= len(game.positions):
            raise ValueError(f"ply must be between 0 and {len(game.positions) - 1}")
        self.send_json(serialize_position(game, game.positions[ply]))

    def serve_static(self, request_path: str) -> None:
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
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a CSA game browser and JSON API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), CsaBrowserHandler)
    print(f"CSA browser running at http://{args.host}:{args.port}")
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
