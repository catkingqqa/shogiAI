#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MESSAGE="${1:-Sync repository $(date '+%Y-%m-%d %H:%M:%S')}"
cd "$ROOT"

git add -A
if ! git diff --cached --quiet; then
    git commit -m "$MESSAGE"
fi

git pull --rebase origin main
git push origin main
