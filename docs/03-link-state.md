# 03 — Keeping an expensive verdict alive

**A URL only a real browser can reach was confirmed by hand. How does that
survive the next automated sweep?**

It doesn't, unless you plan for it. A HEAD/GET checker cannot reach a
bot-walled host, so it records failure, and the confirmation that cost a human
a browser session is gone. Next review, the URL is deleted.

## Disjoint writers

The state file holds one record per URL, and two stages write to it:

- the prober owns `http_status` and `last_checked`, and nothing else
- the semantic verifier owns `verdicts[kind]`, and nothing else

Neither can undo the other's work, so they run in any order, any number of
times. The file is written sorted and indented, so it diffs in review; the
schema is closed-world, and an unknown key at either level is an error rather
than an extra — which is what stops a typo'd field from quietly becoming
load-bearing.

## The sticky override

A browser-grade confirmation stamps `verified_via`. The prober then skips the
network for that URL entirely — and the skip happens *before* host bucketing, so
the URL costs no request, no thread, and not even its host's serial slot.

The guard is a conjunction: the marker **and** a recorded status that is
actually live. A marker sitting over a dead status is not trusted and gets
re-probed, so the override cannot freeze a stale lie in place.

One predicate decides this, shared by the single-URL helper and the sweep. The
easy mistake is to keep a tested helper *and* an inline copy in the main loop;
the tests then guard a function the program never calls.

The strongest test rigs the prober to return 503 for anything it touches and
asserts the confirmed URL is still 200 afterwards. If the override ever leaks,
that fails.

Pinned by: `tests/test_sticky_override.py`, `tests/test_linkstate.py`
