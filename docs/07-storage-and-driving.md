# 07 — What gets written first

**A fetch got through a wall. What do you do with it before anything can go
wrong?**

Write it to disk, unparsed.

The fetch is the expensive artifact; the parser is cheap and will be wrong at
least once. So raw bytes land first, unconditionally, and only then does a
parser run. Two things follow, and both are why this is a module rather than a
habit:

- a parser crash costs nothing — `reparse` re-runs it over cached bytes with no
  browser and no network, so iterating on extraction cannot get you rate-limited
- the **parsed** file, not the raw one, is the completion sentinel

That second point is what makes a re-run cheap and correct. The driver skips an
item when its parsed file exists *and is non-empty* — a zero-byte file from an
interrupted write is retried rather than trusted.

Both runtimes use the same layout, so either can reparse what the other fetched.
There is a test in both directions, because when that drifts the cheap recovery
path stops working and nobody notices until they need it.

## Driving

Three habits, each bought with a rate-limit somewhere:

**Skip what is done, by sentinel.** Re-running after a partial failure fetches
only the gaps.

**Retry flat, not exponentially.** Thirty seconds outlasts a transient
rate-flag and keeps the worst case predictable. Each attempt gets a hard
timeout, because a hung browser outlives its own internal ones. A failure is
logged and skipped, never fatal: the rest of the list still runs and the gap is
picked up next sweep.

**Jitter the gap between items.** Not politeness alone — a metronome does not
look like a reader. The spacing is drawn per item from a band, and a test
asserts the intervals are not all equal. Skipped items cost no pause.

All timing is injectable, so the tests prove this in milliseconds rather than
minutes.

Pinned by: `tests/test_rawstore.py`, `tests/test_rawstore_cross.py`,
`tests/test_drive.py`
