#!/usr/bin/env bash
# Full pipeline for one edition year.
#   ./run.sh 2025            fetch, extract, analyze
#   ./run.sh 2025 2024       ...then compare against the 2024 edition
set -euo pipefail
cd "$(dirname "$0")"
PY="./.venv/bin/python"
YEAR="${1:?usage: ./run.sh <year> [compare-against-year]}"
BASE="${2:-}"

echo "==> fetching $YEAR"
$PY scripts/fetch.py   --year "$YEAR" --workers 3
echo "==> extracting $YEAR"
$PY scripts/extract.py --year "$YEAR"
echo "==> analyzing $YEAR"
$PY scripts/analyze.py --year "$YEAR"

if [ -n "$BASE" ]; then
  echo "==> comparing $BASE -> $YEAR"
  $PY scripts/compare.py "$BASE" "$YEAR"
fi
echo "==> done. See output/"
