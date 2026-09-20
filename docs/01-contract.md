# 01 — One file, two languages

**Why does a JSON file get read by both a Python package and a Node library?**

Because the alternative was tried and it failed silently. When two runtimes each
hold their own copy of a shared fact — a user-agent string, the set of HTTP
statuses that count as "live", how long to wait for a challenge — the copies
drift. Nothing breaks loudly. One half of the system pins an older browser
version than the other, and you find out when a site treats the two differently.

So `crawlkit/contract/constants.json` is the only place a shared constant is
written. `node/lib/contract.js` resolves that exact path — not a copy, not a
generated mirror — and a test shells out to Node, pulls the whole object back
and deep-compares it against what Python sees. If the path ever breaks, the
suite fails instead of the two halves parting company.

## What lives there, and why each is shared rather than local

A constant belongs in the contract when **two things must agree about it**:

- the user-agent registry, because a mismatch between runtimes is a fingerprint
- exit codes, because a driver script keys retry behaviour on them
- `live_statuses`, because the probe ladder and the sticky override must agree
  on what "reachable" means
- the challenge poll and `min_body`, because both runtimes wait out walls
- the fanout marker, so an agent dispatched from either side writes the token
  the other's recovery reads
- the closed vocabularies, with a gloss and an `offer_to_agent` flag per value

Anything only one module cares about stays a module constant. The contract is
not a dumping ground for numbers; it is the set of facts that have to match.

## The vocabularies are the interesting part

Each verdict value carries a gloss and a flag saying whether an agent may
report it. `agents/sections.verdict_guide()` renders the in-prompt guide from
that object, filtered by the flag, and `agents/verdicts.py` validates against
the same object. The relation "what a prompt offers is a subset of what the
ingester accepts" is therefore structural rather than remembered.

Maintained as two lists, they skew. The symptom is a whole fanout's worth of
rejected records and no obvious cause.

## Locales

Block pages are written in the language of the site that serves them, so
matching one is language-specific by nature. Hardcoding a list inside a
detector is wrong twice over: it narrows the tool to wherever it was written,
and extending it means editing code. The phrases are data — English by default,
`CRAWLKIT_LOCALES=en,ru` to add more — and a parity test fails any locale
missing a category, because a half-populated language is worse than an absent
one. You enable it and get no coverage where you think you have some.

Pinned by: `tests/test_contract_parity.py`, `tests/test_locales.py`
