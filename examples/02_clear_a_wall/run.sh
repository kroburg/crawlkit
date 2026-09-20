#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../.. && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
CK_RENDER="$ROOT/.venv/bin/ck-render"
[ -x "$CK_RENDER" ] || CK_RENDER="$(command -v ck-render)"

: "${CRAWLKIT_FIXTURE:?set CRAWLKIT_FIXTURE=http://127.0.0.1:<port> — see examples/run_all.sh}"

if ! "$PY" -c "import playwright" >/dev/null 2>&1; then
  echo "SKIP: playwright not installed (pip install -e '.[browser]' && playwright install chromium)"
  exit 0
fi

rm -rf out
mkdir -p out

# clears-after/0: the wall clears on the very first hit a session makes. Note
# the /0, not the /3 you might expect — ck-render opens a brand-new browser
# context per invocation, so it never accumulates hits across runs the way a
# real multi-visit session would. A wall that needs several hits from the
# SAME session (clears-after/3, .../never) is exactly what the warm-profile
# Node harvester (see 08) exists for; ck-render is the one-shot rescue tool.
echo "== clears-after/0 (require-growth) =="
"$CK_RENDER" "$CRAWLKIT_FIXTURE/challenge/clears-after/0" --require-growth --timeout 5000 \
  --out out/cleared.html
echo "cleared: $(grep -o '<h1[^>]*>[^<]*' out/cleared.html)"

# challenge/never: the wall that, true to its name, never clears — --require-growth
# turns that into a real, distinguishable exit code instead of silently
# archiving the interstitial stub as if it were content.
echo "== challenge/never (require-growth) =="
set +e
"$CK_RENDER" "$CRAWLKIT_FIXTURE/challenge/never" --require-growth --timeout 5000 \
  >out/never.out 2>out/never.err
code=$?
set -e
echo "exit code: $code"
cat out/never.err

if [ "$code" -ne 3 ]; then
  echo "expected exit 3 (CHALLENGE_NOT_CLEARED), got $code" >&2
  exit 1
fi
