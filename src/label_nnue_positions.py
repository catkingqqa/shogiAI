"""替既有 NNUE .npz資料集加入固定節點數的 USI 教師分數。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, TextIO

import numpy as np


def parse_meta(raw_meta: object) -> dict[str, Any]:
    if isinstance(raw_meta, bytes):
        return json.loads(raw_meta.decode("utf-8"))
    return json.loads(str(raw_meta))


def meta_ply(meta: dict[str, Any]) -> int | None:
    for key in ("ply", "move_number", "move_index"):
        if key in meta:
            try:
                return int(meta[key])
            except (TypeError, ValueError):
                return None
    return None


class USITeacher:
    def __init__(self, engine: Path, threads: int, hash_mb: int, extra_options: list[str]) -> None:
        self.process = subprocess.Popen(
            [str(engine)],
            cwd=str(engine.resolve().parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("failed to open USI engine pipes")
        self.stdin: TextIO = self.process.stdin
        self.stdout: TextIO = self.process.stdout
        self._send("usi")
        self._read_until("usiok")
        self._send(f"setoption name Threads value {threads}")
        self._send(f"setoption name USI_Hash value {hash_mb}")
        for option in extra_options:
            self._send(f"setoption name {option}")
        self._send("isready")
        self._read_until("readyok")
        self._send("usinewgame")

    def _send(self, command: str) -> None:
        self.stdin.write(command + "\n")
        self.stdin.flush()

    def _read_until(self, token: str) -> None:
        for line in self.stdout:
            if line.strip().startswith(token):
                return
        raise RuntimeError(f"USI engine ended before {token}")

    def evaluate(self, sfen: str, nodes: int, mate_score: int) -> float:
        self._send(f"position sfen {sfen}")
        self._send(f"go nodes {nodes}")
        last_score: float | None = None
        for raw_line in self.stdout:
            line = raw_line.strip()
            tokens = line.split()
            if "score" in tokens:
                score_index = tokens.index("score")
                if score_index + 2 < len(tokens):
                    score_type = tokens[score_index + 1]
                    score_value = tokens[score_index + 2]
                    try:
                        if score_type == "cp":
                            last_score = float(int(score_value))
                        elif score_type == "mate":
                            mate_distance = int(score_value)
                            last_score = float(mate_score if mate_distance > 0 else -mate_score)
                    except ValueError:
                        pass
            if line.startswith("bestmove"):
                break
        return float("nan") if last_score is None else last_score

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self._send("quit")
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()

    def __enter__(self) -> "USITeacher":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 USI 將棋引擎產生 NNUE 教師分數。")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--engine", required=True, type=Path, help="やねうら王或其他 USI 引擎的路徑")
    parser.add_argument("--nodes", type=int, default=20_000)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--hash-mb", type=int, default=256)
    parser.add_argument("--min-ply", type=int, default=30)
    parser.add_argument("--max-ply", type=int, default=None)
    parser.add_argument("--stride", type=int, default=1, help="每 N 筆符合條件的資料評估一筆")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mate-score", type=int, default=30_000)
    parser.add_argument("--setoption", action="append", default=[], help='額外 USI 選項，例如 "EvalDir value eval"')
    parser.add_argument("--progress-every", type=int, default=1000)
    return parser.parse_args()


def save_teacher_dataset(output: Path, arrays: dict[str, np.ndarray], scores: np.ndarray) -> None:
    """先寫入暫存檔，再原子取代正式檔案，避免中斷時破壞既有進度。"""
    temporary = output.with_name(output.name + ".tmp.npz")
    np.savez_compressed(temporary, **arrays, teacher_scores=scores)
    os.replace(temporary, output)


def main() -> int:
    args = parse_args()
    if not args.engine.is_file():
        raise SystemExit(
            f"找不到 USI 引擎：{args.engine}\n"
            "請先執行 prepare_yaneuraou.ps1，或將 --engine 改成真實的 .exe 路徑。"
        )
    data = np.load(args.input, allow_pickle=True)
    if "meta" not in data.files:
        raise SystemExit("input dataset has no meta array")
    # 教師資料只需要局面資訊、勝負及教師分數。原始 states/moves 仍保留在
    # samples.npz，不在每次 checkpoint 時重複壓縮，可大幅縮短存檔時間。
    arrays = {key: data[key] for key in ("meta", "values") if key in data.files}
    metas = data["meta"]
    scores = np.full(len(metas), np.nan, dtype=np.float32)
    if args.output.exists():
        previous = np.load(args.output, allow_pickle=True)
        if "teacher_scores" in previous.files and len(previous["teacher_scores"]) == len(scores):
            scores[:] = previous["teacher_scores"].astype(np.float32)

    eligible_seen = completed = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with USITeacher(args.engine, args.threads, args.hash_mb, args.setoption) as teacher:
            for row_index, raw_meta in enumerate(metas):
                if args.limit is not None and completed >= args.limit:
                    break
                if math.isfinite(float(scores[row_index])):
                    continue
                try:
                    meta = parse_meta(raw_meta)
                    ply = meta_ply(meta)
                    if ply is None or ply < args.min_ply or (args.max_ply is not None and ply > args.max_ply):
                        continue
                    if eligible_seen % max(1, args.stride) != 0:
                        eligible_seen += 1
                        continue
                    eligible_seen += 1
                    scores[row_index] = teacher.evaluate(meta["sfen"], args.nodes, args.mate_score)
                    completed += 1
                    if completed % max(1, args.progress_every) == 0:
                        save_teacher_dataset(args.output, arrays, scores)
                        print(f"labeled={completed} row={row_index} output={args.output}")
                except Exception as exc:
                    print(f"warning: row={row_index} skipped: {exc}")
    except KeyboardInterrupt:
        print("\n收到中斷指令，正在保存目前教師分數...")
        save_teacher_dataset(args.output, arrays, scores)
        finite = int(np.isfinite(scores).sum())
        print(f"已保存 teacher_scores={finite}/{len(scores)}；下次可直接續跑。")
        return 130

    save_teacher_dataset(args.output, arrays, scores)
    finite = int(np.isfinite(scores).sum())
    print(f"teacher_scores={finite}/{len(scores)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
