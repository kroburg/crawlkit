#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
CK_DRIVE="$ROOT/.venv/bin/ck-drive"
[ -x "$CK_DRIVE" ] || CK_DRIVE="$(command -v ck-drive)"

: "${CRAWLKIT_FIXTURE:?set CRAWLKIT_FIXTURE=http://127.0.0.1:<port> — see examples/run_all.sh}"

rm -rf out
mkdir -p out
sed "s|__FIXTURE__|$CRAWLKIT_FIXTURE|g" items.json.tmpl > out/items.json

echo "== first run: nothing stored yet =="
"$CK_DRIVE" out/items.json --dir out/raw --jitter 0:0 \
  -- "$PY" fetch_one.py "{id}" "{url}" --dir out/raw

echo
echo "== second run: same work-list, sentinels already on disk =="
"$CK_DRIVE" out/items.json --dir out/raw --jitter 0:0 \
  -- "$PY" fetch_one.py "{id}" "{url}" --dir out/raw

echo
echo "stored files:"
ls out/raw
