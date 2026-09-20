# 08 — node warm profile

Two node entry points, two different offline stories. `harvest-page.js` opens
a real (branded) Chrome on a persistent profile and fetches one page — this
needs Chrome and `node/node_modules`, so `run.sh` self-skips it with one line
when either is missing. `batch-fanout.js --dry-run` needs neither a browser
nor a model: it only discovers files and plans agent calls, so it always
runs.

Run `run.sh`. If Chrome is available, the first block fetches `/lazy` and
stores it raw-first under `out/raw/` (`.html` plus the parsed `.json`
sentinel) — the same `crawlkit.rawstore` layout the Python side uses, so
either runtime can reparse what the other fetched. The second block reads
`batches/` (two committed sample files) and prints the planned agent calls,
one per file, each with a model pinned explicitly — `assertModelPinned`
makes an unpinned call a hard error instead of a fleet that silently
inherits whatever model the session happens to be running.
