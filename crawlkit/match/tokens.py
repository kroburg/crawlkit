"""Which target an unlabelled verdict belongs to.

The usual comparison here is a short label against a long title, and that
shape breaks Jaccard: a five-word label against a forty-word title scores
near zero even when every one of those five words is in the title, because
Jaccard divides by the size of the *union*. Containment — divide by the
smaller side instead — is what actually answers "is the label describing
this title", so that's what `overlap` computes.

The other trap is direction. `core.best_under` always wants a *distance*
where lower is better, but overlap is a *similarity* where higher is better,
and the floor for a similarity is a minimum while the floor for a distance is
a maximum. Converting the wrong way — passing the floor through unchanged —
doesn't raise; it silently turns "refuse anything below 5% overlap" into
"accept anything above 95% distance", which is nearly everything. A matcher
that fails open like that is worse than no matcher, so the conversion happens
exactly once, right here, next to an assertion that would catch a future edit
undoing it.
"""

import re

from crawlkit import contract
from crawlkit.match.core import best_under

# 4+ word characters, Latin or Cyrillic, so a short article ("на", "the",
# "of") never counts as a shared token — those are exactly the words two
# unrelated titles have in common.
_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ]{4,}")


def tokenize(text):
    """Casefolded words of 4+ letters, Latin and Cyrillic both."""
    return frozenset(match.group(0).casefold() for match in _TOKEN_RE.finditer(text or ""))


def overlap(a, b):
    """Containment: |A ∩ B| / min(|A|, |B|). 0.0 when either side is empty."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _default_key(candidate):
    return candidate


def best_label(text, candidates, *, key=None, floor=None):
    """The candidate label `text` overlaps most, refused below the floor.

    `floor` here is a *minimum overlap* (contract's convention, and the one a
    caller reasons in), but `best_under` only knows *maximum distance* — so
    this is the one place that conversion happens, guarded by an assertion
    that the two floors sum to 1, which is what would break silently and
    dangerously if a future edit flipped the sign back.
    """
    key = key or _default_key
    floor = contract.get("match.floors.token_overlap") if floor is None else floor
    distance_floor = 1 - floor
    assert distance_floor + floor == 1, "overlap floor must convert to a distance floor via 1 - x"

    text_tokens = tokenize(text)

    def distance_fn(candidate):
        return 1 - overlap(text_tokens, tokenize(key(candidate)))

    return best_under(candidates, distance_fn, distance_floor, metric="token_overlap")
