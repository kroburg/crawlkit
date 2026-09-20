# 04 — Telling a wall from a thin page

**A fetch returned something. Is it the page, or the thing standing in front of
it?**

Three answers, in increasing order of portability.

## Don't grep for the vendor

The tempting check is to search the body for the challenge provider's name. It
does not work: sites embed those widgets in their own login forms, so the
vendor's name appears on pages that were fetched perfectly well. A detector
built that way marks good harvests as blocked.

## Title, then text

`title_not` waits for a named interstitial to disappear. Precise, and useless
against a wall you have not met.

`body_text_at_least` waits for rendered **text** to grow past a floor. It is the
portable one, for three reasons: no per-vendor string; a stub carries kilobytes
of obfuscated script and almost no text, so measuring `innerText` discriminates
where `innerHTML` does not; and because the predicate is re-evaluated in each
new document, it survives the challenge reloading itself — which is exactly
where a read-then-check fails.

**Never reload during the poll.** A reload restarts the proof-of-work and can
escalate a soft challenge into a hard block. The wait is a poll over one
navigation, and there is a test asserting the server saw exactly one.

## Calibrate the floor

The default is 2000 characters. On one real harvest, seven of twenty-three
genuine pages rendered less than that — they were thin, not blocked. So the
floor is a per-target parameter and the growth gate is **opt-in**: left on at
the default, that harvest would have rejected a third of its own results.

The gap you are exploiting is still enormous — a stub renders tens of
characters, a thin real page renders a thousand — so any floor between the two
works. You just have to pick one per site, and a test fails if anyone makes the
gate the default.

## When the site says no

The breaker is deliberately asymmetric: one refusal opens it and ends the run;
throttles are tolerated briefly; successes decay throttles but never a refusal.

The instinct on a 403 is to change something — another address, another user
agent — and retry. That converts a recoverable situation into a permanent one:
defences escalate per identity and per network, and each retry teaches them more
about you than you learn about them. **A 403 is a decision, not a hiccup.** The
run stops, the cache is on disk, and resuming is something a human does later.

A challenge body counts as a refusal even under a 200, and so does a block page
in any enabled locale.

Pinned by: `tests/test_render.py`, `tests/test_calibration.py`,
`tests/test_robots_and_circuit.py`
