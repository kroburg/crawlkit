"""Pacing, retries and resumability for a sequential harvest.

Three habits, each bought with a rate-limit somewhere:

**Skip what is already done, by sentinel.** Re-running a harvest after a
partial failure must fetch only the gaps. The check is "non-empty parsed file",
not "file exists", so an interrupted write is retried rather than trusted.

**Retry flat, not exponentially.** Thirty seconds is long enough for a
transient rate-flag to age out, and it keeps the worst case bounded and
predictable. Each attempt gets a hard timeout, because a hung browser can
outlive its own internal timeouts.

**Jitter the gap between items.** A constant interval is itself a signature —
the point is not politeness alone but that a metronome does not look like a
reader. The spacing is drawn per item and deliberately never a round number.

All timing is injectable so the tests run in milliseconds instead of minutes.
"""

import random
import subprocess
import time

from crawlkit import contract, rawstore

ATTEMPTS = contract.get("politeness.attempts")
BACKOFF_S = contract.get("politeness.backoff_s")
ATTEMPT_TIMEOUT_S = contract.get("politeness.attempt_timeout_s")
JITTER_LO_S = contract.get("politeness.jitter_lo_s")
JITTER_HI_S = contract.get("politeness.jitter_hi_s")


def jitter(lo=None, hi=None, rng=random):
    return rng.uniform(JITTER_LO_S if lo is None else lo, JITTER_HI_S if hi is None else hi)


def attempt_command(command, timeout_s=None, run=subprocess.run):
    """One attempt. Returns (ok, returncode). A timeout counts as a failure."""
    try:
        done = run(command, timeout=timeout_s or ATTEMPT_TIMEOUT_S, capture_output=True, text=True)
        return done.returncode == 0, done.returncode
    except subprocess.TimeoutExpired:
        return False, None


def with_retries(work, attempts=None, backoff_s=None, sleep=time.sleep, on_event=None):
    """Run `work` until it reports success. Returns (ok, tries)."""
    tries = attempts or ATTEMPTS
    for index in range(1, tries + 1):
        ok, detail = work()
        if ok:
            return True, index
        if on_event:
            on_event("attempt_failed", {"attempt": index, "of": tries, "detail": detail})
        if index < tries:
            sleep(BACKOFF_S if backoff_s is None else backoff_s)
    return False, tries


def harvest_all(
    items,
    build_command,
    directory,
    attempts=None,
    backoff_s=None,
    jitter_range=None,
    sleep=time.sleep,
    rng=random,
    run=subprocess.run,
    timeout_s=None,
    on_event=None,
):
    """Drive a sequential harvest over `items` of (id, *args).

    `build_command(item)` returns the argv for one fetch. Items whose sentinel
    is already present are skipped without a fetch and without a sleep.
    """
    emit = on_event or (lambda event, data: None)
    lo, hi = jitter_range or (JITTER_LO_S, JITTER_HI_S)
    summary = {"done": [], "skipped": [], "failed": []}
    first = True

    for item in items:
        ident = item[0] if isinstance(item, (tuple, list)) else item
        if rawstore.sentinel_ok(directory, ident):
            summary["skipped"].append(ident)
            emit("skipped", {"id": ident})
            continue

        # Pace between real fetches only: skipping is free and must stay free.
        if not first:
            gap = jitter(lo, hi, rng)
            emit("pacing", {"id": ident, "seconds": round(gap, 2)})
            sleep(gap)
        first = False

        emit("fetching", {"id": ident})
        ok, tries = with_retries(
            lambda item=item: attempt_command(build_command(item), timeout_s, run),
            attempts,
            backoff_s,
            sleep,
            on_event,
        )
        if ok:
            summary["done"].append(ident)
            emit("done", {"id": ident, "attempts": tries})
        else:
            # A failure is logged and skipped, never fatal: the rest of the
            # list still runs and the gap is picked up by the next sweep.
            summary["failed"].append(ident)
            emit("failed", {"id": ident, "attempts": tries})

    return summary
