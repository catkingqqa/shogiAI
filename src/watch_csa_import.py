"""Poll a directory and import newly completed CSA files into MySQL."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch-dir", type=Path, required=True)
    parser.add_argument("--importer", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--settle-seconds", type=float, default=10)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "140.135.65.53"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER", "11211213"))
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", "DB11211213"))
    parser.add_argument("--create-tables", action="store_true")
    parser.add_argument(
        "--initialize-existing",
        action="store_true",
        help="Mark files present at startup as processed without importing them.",
    )
    parser.add_argument(
        "--initialize-from-database",
        action="store_true",
        help="Initialize state from CSA original_file_name values already in MySQL.",
    )
    return parser.parse_args()


def load_state(path: Path) -> tuple[set[str], dict[str, str]]:
    if not path.exists():
        return set(), {}
    state = json.loads(path.read_text(encoding="utf-8"))
    return set(state.get("processed", [])), dict(state.get("failed", {}))


def save_state(path: Path, processed: set[str], failed: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {"processed": sorted(processed), "failed": failed},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def database_file_names(args: argparse.Namespace) -> set[str]:
    import pymysql

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=os.environ["MYSQL_PASSWORD"],
        database=args.database,
        charset="utf8mb4",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT original_file_name
                FROM game_records
                WHERE source_format = 'CSA'
                  AND original_file_name IS NOT NULL
                """
            )
            return {str(row[0]).split("#game", 1)[0] for row in cursor.fetchall()}
    finally:
        connection.close()


def completed_files(
    watch_dir: Path,
    processed: set[str],
    failed: dict[str, str],
    settle_seconds: float,
) -> list[Path]:
    cutoff = time.time() - settle_seconds
    return [
        path
        for path in sorted(watch_dir.glob("*.csa"))
        if path.name not in processed
        and path.name not in failed
        and path.stat().st_mtime <= cutoff
    ]


def prepare_staging(staging_dir: Path, files: list[Path]) -> None:
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)
    for source in files:
        shutil.copy2(source, staging_dir / source.name)


def import_batch(args: argparse.Namespace, files: list[Path]) -> tuple[set[str], dict[str, str]] | None:
    prepare_staging(args.staging_dir, files)
    command = [
        sys.executable,
        str(args.importer),
        "--input",
        str(args.staging_dir),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--user",
        args.user,
        "--database",
        args.database,
        "--skip-existing",
    ]
    if args.create_tables:
        command.append("--create-tables")
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)

    try:
        summary = json.loads(result.stdout[result.stdout.index("{") :])
    except (ValueError, json.JSONDecodeError):
        return None

    errors = {
        Path(item["source"]).name: str(item["error"])
        for item in summary.get("errors") or []
    }
    successful = {path.name for path in files} - set(errors)
    return successful, errors


def main() -> int:
    args = parse_args()
    args.watch_dir = args.watch_dir.resolve()
    args.importer = args.importer.resolve()
    args.state_file = args.state_file.resolve()
    args.staging_dir = args.staging_dir.resolve()

    processed, failed = load_state(args.state_file)
    if args.initialize_existing and not args.state_file.exists():
        processed.update(path.name for path in args.watch_dir.glob("*.csa"))
        save_state(args.state_file, processed, failed)
        print(f"Initialized state with {len(processed)} existing files.", flush=True)
    elif args.initialize_from_database and not args.state_file.exists():
        processed.update(database_file_names(args))
        save_state(args.state_file, processed, failed)
        print(f"Initialized state with {len(processed)} files already in MySQL.", flush=True)

    print(f"Watching {args.watch_dir} for new CSA files.", flush=True)
    while True:
        pending = completed_files(args.watch_dir, processed, failed, args.settle_seconds)
        for start in range(0, len(pending), args.batch_size):
            batch = pending[start : start + args.batch_size]
            print(f"Importing {len(batch)} files: {batch[0].name} .. {batch[-1].name}", flush=True)
            result = import_batch(args, batch)
            if result is None:
                print("Import failed; the batch will be retried.", flush=True)
                break
            successful, errors = result
            processed.update(successful)
            failed.update(errors)
            save_state(args.state_file, processed, failed)
            print(
                f"Batch complete; processed: {len(processed)}, failed: {len(failed)}",
                flush=True,
            )
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
