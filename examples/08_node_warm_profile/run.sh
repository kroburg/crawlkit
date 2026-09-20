#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

: "${CRAWLKIT_FIXTURE:?set CRAWLKIT_FIXTURE=http://127.0.0.1:<port> — see examples/run_all.sh}"

rm -rf out
mkdir -p out

# Part 1 needs a real Chrome and puppeteer-core; self-skip with one line
# rather than let the harness treat a missing browser as a failure.
have_chrome=1
command -v node >/dev/null 2>&1 || have_chrome=0
[ -d "$ROOT/node/node_modules/puppeteer-core" ] || have_chrome=0
if [ "$have_chrome" = "1" ]; then
  chrome_path="$("$PY" -c "
import os
from crawlkit import contract
print(os.environ.get('CRAWLKIT_CHROME') or contract.get('browser.branded_chrome'))
")"
  [ -x "$chrome_path" ] || have_chrome=0
fi

echo "== harvest-page.js (warm profile, needs Chrome) =="
if [ "$have_chrome" = "1" ]; then
  node "$ROOT/node/bin/harvest-page.js" "$CRAWLKIT_FIXTURE/lazy" lazy-demo --dir out/raw --no-wall
  echo "-- stored --"
  ls out/raw
else
  echo "SKIP: no Chrome (set CRAWLKIT_CHROME=<path> or install node/node_modules) — see node/lib/launch.js"
fi

echo
echo "== batch-fanout.js --dry-run (pure, always runs) =="
node "$ROOT/node/workflows/batch-fanout.js" --dry-run \
  --batchDir=batches --model=stub-model --prompt='harvest {{file}}'
