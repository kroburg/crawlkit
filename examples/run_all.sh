#!/usr/bin/env bash
# Start the fixture server once, run every examples/*/run.sh against it in
# order, stop the server, report which passed. Each run.sh also works
# standalone if CRAWLKIT_FIXTURE is already set — this script just supplies it.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd .. && pwd)"
PY="$ROOT/.venv/bin/python"

LOG="$(mktemp)"
SERVER_PID=""
cleanup() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" >/dev/null 2>&1 || true
  rm -f "$LOG"
}
trap cleanup EXIT

(cd "$ROOT" && exec "$PY" -m fixtures.server --port 0) >"$LOG" 2>&1 &
SERVER_PID=$!

line=""
for _ in $(seq 1 200); do
  line="$(grep -m1 '^LISTENING http' "$LOG" 2>/dev/null || true)"
  [ -n "$line" ] && break
  sleep 0.1
done
if [ -z "$line" ]; then
  echo "fixture server did not start:" >&2
  cat "$LOG" >&2
  exit 1
fi

export CRAWLKIT_FIXTURE="${line#LISTENING }"
echo "fixture: $CRAWLKIT_FIXTURE"
echo

pass=0
fail=0
failed_names=()

for dir in */; do
  name="${dir%/}"
  [ -f "${dir}run.sh" ] || continue
  echo "== $name =="
  if bash "${dir}run.sh"; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    failed_names+=("$name")
  fi
  echo
done

echo "passed: $pass  failed: $fail"
if [ "$fail" -gt 0 ]; then
  echo "failed: ${failed_names[*]}"
  exit 1
fi
