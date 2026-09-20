#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
CK_PROBE="$ROOT/.venv/bin/ck-probe"
[ -x "$CK_PROBE" ] || CK_PROBE="$(command -v ck-probe)"

: "${CRAWLKIT_FIXTURE:?set CRAWLKIT_FIXTURE=http://127.0.0.1:<port> — see examples/run_all.sh}"

rm -rf out
mkdir -p out
sed "s|__FIXTURE__|$CRAWLKIT_FIXTURE|g" state.json.tmpl > out/state.json

echo "--- state.json before ---"
cat out/state.json

"$CK_PROBE" out/state.json

echo "--- state.json after ---"
cat out/state.json
