#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
CK_QA="$ROOT/.venv/bin/ck-qa"

rm -rf out
mkdir -p out

# All three checks below run offline against records already on disk, and all
# three fire — on purpose. Every one of these failures looks like success at
# fetch time: the request returned 200, the parser did not raise, the file has
# content. Non-zero exits here are the expected, correct result.
echo "== ck-qa echo: does a field echo the extractor's own input? =="
set +e
"$CK_QA" echo records.json --fields title
echo "exit: $?"
set -e

echo
echo "== ck-qa census: which fields did this harvest fail to fill? =="
set +e
"$CK_QA" census records.json
echo "exit: $?"
set -e

echo
echo "== ck-qa agree: what do two independent passes actually agree on? =="
set +e
"$CK_QA" agree records.json pass_b.json --fields title,access --into out/auto_applicable.json
echo "exit: $?"
set -e

echo
echo "-- auto-applicable values (only what both passes agreed on) --"
cat out/auto_applicable.json
