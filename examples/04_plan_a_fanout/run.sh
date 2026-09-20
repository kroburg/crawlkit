#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
CK_PLAN="$ROOT/.venv/bin/ck-plan"

: "${CRAWLKIT_FIXTURE:?set CRAWLKIT_FIXTURE=http://127.0.0.1:<port> — see examples/run_all.sh}"

rm -rf out
mkdir -p out
sed "s|__FIXTURE__|$CRAWLKIT_FIXTURE|g" items.json.tmpl > out/items.json

# No model anywhere in this example: ck-plan composes prompts from documents
# on disk. --dry-run shows what would be dispatched without writing anything.
echo "== dry run =="
"$CK_PLAN" \
  --worklist out/items.json \
  --prompt ../../docs/prompts/harvest.md \
  --schema ../../docs/prompts/schema.md \
  --dry-run

echo
echo "== real emit =="
"$CK_PLAN" \
  --worklist out/items.json \
  --prompt ../../docs/prompts/harvest.md \
  --schema ../../docs/prompts/schema.md \
  --out out/prompts

echo
echo "-- schema block landed verbatim in book-1.md --"
sed -n '/```yaml/,/```/p' out/prompts/book-1.md

echo
echo "-- census sentence carries the real denominator (the source URL) --"
grep "verification:" out/prompts/book-1.md

echo
echo "-- the marker recovery reads back --"
grep "crawlkit-item: book-1" out/prompts/book-1.md
