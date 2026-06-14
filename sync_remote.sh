#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIVE_CRAWLER_DIR="${CLIMBBUG_LIVE_DIR:-$HOME/climbbug}"
MESSAGE="${1:-Sync big-data host $(date '+%Y-%m-%d %H:%M:%S')}"

mkdir -p "$ROOT/climbbug/data" "$ROOT/climbbug/data_1"

for directory in data data_1; do
    if [[ -d "$LIVE_CRAWLER_DIR/$directory" ]]; then
        cp -a "$LIVE_CRAWLER_DIR/$directory/." "$ROOT/climbbug/$directory/"
    fi
done

for file in CB.py CC.py readme.txt game_urls.txt failed_urls.txt; do
    if [[ -f "$LIVE_CRAWLER_DIR/$file" ]]; then
        cp -p "$LIVE_CRAWLER_DIR/$file" "$ROOT/climbbug/$file"
    fi
done

"$ROOT/sync_repo.sh" "$MESSAGE"

mkdir -p "$LIVE_CRAWLER_DIR/data" "$LIVE_CRAWLER_DIR/data_1"
for directory in data data_1; do
    cp -a "$ROOT/climbbug/$directory/." "$LIVE_CRAWLER_DIR/$directory/"
done
for file in CB.py CC.py readme.txt game_urls.txt failed_urls.txt; do
    cp -p "$ROOT/climbbug/$file" "$LIVE_CRAWLER_DIR/$file"
done
