"""功能：提供 Jupyter Notebook 內的棋盤視覺化工具，用來檢視 CSA 回放與 npz 樣本。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cshogi
from cshogi import CSA
import numpy as np


@dataclass(frozen=True)
class BoardSample:
    """功能：定義 BoardSample 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    index: int
    board: cshogi.Board
    move: int | None
    move_usi: str | None
    value: float | None = None
    move_label: int | None = None
    source: str | None = None
    ply: int | None = None
    sfen: str | None = None

    def _repr_html_(self) -> str:
        """功能：產生 Jupyter 可直接顯示的 HTML 內容。"""
        value = "" if self.value is None else f"<dt>value</dt><dd>{self.value:+.1f}</dd>"
        move_label = "" if self.move_label is None else f"<dt>move label</dt><dd>{self.move_label}</dd>"
        source = "" if self.source is None else f"<dt>source</dt><dd>{self.source}</dd>"
        ply = "" if self.ply is None else f"<dt>ply</dt><dd>{self.ply}</dd>"
        move = "" if self.move_usi is None else f"<dt>move</dt><dd>{self.move_usi}</dd>"
        sfen = "" if self.sfen is None else f"<details><summary>SFEN</summary><code>{self.sfen}</code></details>"
        lastmove = self.move if self.move is not None else cshogi.MOVE_NONE
        return f"""
        <section style="display:grid;grid-template-columns:auto minmax(220px,1fr);gap:16px;align-items:start">
          <div>{self.board.to_svg(lastmove=lastmove, scale=1.35)}</div>
          <div style="font-family:system-ui,sans-serif">
            <h3 style="margin:0 0 12px">sample #{self.index}</h3>
            <dl style="display:grid;grid-template-columns:84px minmax(0,1fr);gap:6px 12px;margin:0">
              {ply}
              {move}
              {value}
              {move_label}
              {source}
            </dl>
            {sfen}
          </div>
        </section>
        """


@dataclass(frozen=True)
class BoardSampleCollection:
    """功能：定義 BoardSampleCollection 的資料結構與行為，讓相關流程可以以結構化方式使用。"""
    samples: list[BoardSample]

    def _repr_html_(self) -> str:
        """功能：產生 Jupyter 可直接顯示的 HTML 內容。"""
        return "\n".join(sample._repr_html_() for sample in self.samples)


def csa_boards(path: str | Path, encoding: str = "utf-8", game_index: int = 0) -> list[BoardSample]:
    """功能：Return replayable CSA positions as Jupyter-displayable BoardSample objects."""
    games = CSA.Parser.parse_file(str(path), encoding=encoding)
    parser = games[game_index]
    board = cshogi.Board(parser.sfen)
    samples: list[BoardSample] = []

    for index, move in enumerate(parser.moves):
        if not board.is_legal(move):
            raise ValueError(f"illegal move at ply {index + 1}: {cshogi.move_to_usi(move)}")
        samples.append(
            BoardSample(
                index=index,
                board=board.copy(),
                move=move,
                move_usi=cshogi.move_to_usi(move),
                source=str(path),
                ply=index + 1,
                sfen=board.sfen(),
            )
        )
        board.push(move)
    return samples


def npz_samples(path: str | Path) -> list[BoardSample]:
    """功能：Return .npz samples as Jupyter-displayable BoardSample objects."""
    data = np.load(path, allow_pickle=False)
    moves = data["moves"]
    values = data["values"]
    meta = data["meta"]
    samples: list[BoardSample] = []

    for index, meta_text in enumerate(meta):
        item = json.loads(str(meta_text))
        board = cshogi.Board(item["sfen"])
        move = board.move_from_usi(item["move_usi"])
        samples.append(
            BoardSample(
                index=index,
                board=board,
                move=move,
                move_usi=item["move_usi"],
                value=float(values[index]),
                move_label=int(moves[index]),
                source=item["source"],
                ply=int(item["ply"]),
                sfen=item["sfen"],
            )
        )
    return samples


def show(sample: BoardSample) -> BoardSample:
    """功能：Return one BoardSample. In Jupyter, the returned object displays as HTML."""
    return sample


def show_many(samples: Iterable[BoardSample], limit: int = 10) -> BoardSampleCollection:
    """功能：Return several BoardSample objects as one Jupyter-displayable collection."""
    return BoardSampleCollection(list(samples)[:limit])


def board_from_sfen(sfen: str) -> cshogi.Board:
    """功能：Create a cshogi.Board that displays directly as SVG in Jupyter."""
    return cshogi.Board(sfen)
