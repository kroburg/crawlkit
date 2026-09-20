#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
CK_INGEST="$ROOT/.venv/bin/ck-ingest"

rm -rf out
mkdir -p out

# agent-intruder is deliberately left off --agent-ids: authorization is an
# explicit list of just-dispatched agents, never a directory listing.
set +e
"$CK_INGEST" results \
  --agent-ids agent-aa11,agent-bb22,agent-cc33,agent-dd44 \
  --into out/records.json \
  --worklist items.json
code=$?
set -e

echo
echo "ck-ingest exit code: $code (non-zero: at least one reply was rejected)"
echo
echo "-- what landed --"
cat out/records.json

count=$("$ROOT/.venv/bin/python" -c "import json; print(len(json.load(open('out/records.json'))))")
if [ "$count" != "1" ]; then
  echo "expected exactly one record, got $count" >&2
  exit 1
fi
echo
echo "OK: exactly 1 record landed"

