"""One function, two metrics: pick the best candidate, then refuse it.

Geo matching and label matching were each written once as "take the nearest
candidate" and each shipped a confident wrong answer — a place 40 km away
standing in for the real one, a verdict glued onto the wrong target because
it happened to score highest. Ranking candidates was never the missing part;
the missing part was a floor the winner has to clear before it counts as a
match at all. That rule lives here, once, so `geo.py` and `tokens.py` are
nothing but a distance function and a threshold.

This module must stay ignorant of what a distance *means*. `geo.py` computes
metres and `tokens.py` computes a converted overlap, but neither concept
belongs here — the day this file imports `math` or reaches into `geo`/`tokens`
is the day "one function, two metrics" quietly becomes "two copies of the
same function", and tests/test_match_floor.py checks that by parsing this
file's own imports.
"""

from typing import Any, NamedTuple


class Match(NamedTuple):
    candidate: Any
    provenance: dict


def best_under(candidates, distance_fn, floor, *, metric=None):
    """Rank by `distance_fn`, then refuse the winner if it doesn't clear `floor`.

    The winner must be strictly under the floor, not merely the smallest of a
    bad lot — a candidate list that is uniformly wrong must still be able to
    come back empty. `runner_up`/`margin` in the provenance exist because a
    distance alone can't tell a human whether a match was decisive or a coin
    flip; "won by 2 metres out of 1500" is the case this is meant to surface,
    not hide behind a bare accept.

    A `distance_fn` that raises on one candidate must not sink the whole
    search — one malformed record poisoning an otherwise good match is worse
    than silently skipping it, so skips are counted and named in provenance
    instead.
    """
    scored = []
    skipped = 0
    for candidate in candidates:
        try:
            distance = distance_fn(candidate)
        except Exception:
            skipped += 1
            continue
        scored.append((distance, candidate))

    if not scored:
        return None

    scored.sort(key=lambda pair: pair[0])
    distance, candidate = scored[0]
    if not distance < floor:
        return None

    runner_up = scored[1][0] if len(scored) > 1 else None
    margin = (runner_up - distance) if runner_up is not None else None

    provenance = {
        "metric": metric,
        "distance": distance,
        "floor": floor,
        "runner_up": runner_up,
        "margin": margin,
        "skipped": skipped,
    }
    return Match(candidate, provenance)
