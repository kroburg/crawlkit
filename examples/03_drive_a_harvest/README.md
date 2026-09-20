# 03 — drive a harvest

`ck-drive` runs one fetch command per work-list item, politely (jittered
gaps, retries) and resumably. "Resumable" means a completion sentinel on
disk, not a run log: `fetch_one.py` stores each page raw-first via
`crawlkit.rawstore`, and the *parsed* file is what `ck-drive` checks before
deciding an item needs fetching at all.

Run `run.sh` and compare the two `ck-drive` calls over the identical
work-list (`--jitter 0:0` so nothing here takes real wall-clock time). The
first run fetches all three items and reports `done 3 skipped 0 failed 0`.
The second run, against the same `out/raw` directory, reports `done 0
skipped 3 failed 0` — every item is skipped by sentinel, with no network
call and no jitter sleep, because `out/raw/*.json` already exists from the
first pass.
