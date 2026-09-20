# 09 — Did it all come back, and who decides?

**Two questions a fanout will not answer honestly on its own.**

## Enumerate, do not sample

Asked to "produce records for X", an agent's default is a representative
sample. It costs fewer tokens and looks finished. One fanout shipped eight
records out of fifty-three that way, and nothing in the output said so.

The fix has two halves that must agree. The prompt carries a census sentence
naming the real denominator, and the gate counts what came back against the
same number. They agree because they are rendered from **the same work-list
object** — a prompt asking for 53 while a gate expects 40 is not a thing that
can happen here.

The gate reports both directions, because they fail differently:

- **missing** — dispatched and never returned: a dead agent, an unparseable
  reply, a record rejected on the way in
- **extra** — a record nobody asked for: an agent that widened its scope, or
  answered about the wrong item

and a third bucket that is easy to forget: **never dispatched**. Items with no
source were not part of the fanout at all. Keeping them separate is what stops
"everything we sent came back" from being read as "we covered everything".

`strict_join` is the write path rather than a warning printed beside it, so an
invented id cannot land even if a caller ignores the report.

## The agent measures; the script judges

Ask an agent whether coverage is good enough and it will say yes. Ask it how
many items the source lists and it will count. The difference is not honesty —
it is that the first question requires knowing what answer passes, and once
that is knowable it is reachable.

So the agent returns one number and a status. The threshold, the ratio and the
verdict name never appear in the prompt (there is a test asserting exactly
that), and every comparison happens in the script against a local count it
**re-reads at apply time** — so a number counted when the work was planned
cannot go stale in between.

Two traps encoded here. `0 ÷ 0` is not 1.0: an unreadable source is *unknown*,
which is its own verdict and is never scored as passing. And a derived verdict
is not something an agent may report — an agent naming `manual` has decided its
own result is unmeasurable and pre-empted the conclusion it was being measured
by, so from an agent that is a rejection.

Pinned by: `tests/test_ingest_authorization.py`, `tests/test_verdicts_and_scalar.py`
