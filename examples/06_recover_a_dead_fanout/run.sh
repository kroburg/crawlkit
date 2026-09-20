#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
PY="$ROOT/.venv/bin/python"
CK_RECOVER="$ROOT/.venv/bin/ck-recover"
CK_INGEST="$ROOT/.venv/bin/ck-ingest"

rm -rf out
mkdir -p out

# Reuses the committed transcript fixture at tests/data/transcripts rather
# than duplicating it here: three dead agents — one complete and marker-
# identified, one that died mid tool-call, one stopped by the user with no
# marker in its prompt at all. Only the first is actually recoverable.
"$CK_RECOVER" --root ../../tests/data/transcripts --out out/recovered

echo
echo "-- recovered replies (named by item id, not agent id) --"
ls out/recovered

# Recovery finds; ingest still authorizes — that separation is the point, and
# it is why recovery cannot become a way around the whitelist. The recovered
# directory names each reply after the item it answers and ships an index.json
# mapping those back to the agents that produced them, so the ids to authorize
# are real agent ids.
ids=$(python3 -c "import json;print(','.join(sorted(json.load(open('out/recovered/index.json')))))")
echo
echo "feeding recovered ids to ck-ingest: --agent-ids $ids"
"$CK_INGEST" out/recovered --agent-ids "$ids" --into out/records.json --suffix .txt

echo
echo "-- what recovery + ingest produced --"
cat out/records.json
