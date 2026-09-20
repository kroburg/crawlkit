"""Did the fanout return everything it was asked for — and nothing else?

Both directions matter and they fail differently. **Missing** is work that was
dispatched and never came back: a dead agent, an unparseable reply, a record
rejected on the way in. **Extra** is a record nobody asked for: an agent that
widened its scope, or answered about the wrong item. Counting only the records
you received tells you neither.

`compare` takes the same `Worklist` object that `sections.census_rule` renders
the prompt sentence from. That is deliberate: the instruction and the check
read one denominator, so a prompt asking for 53 and a gate expecting 40 is not
a thing that can happen.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Census:
    expected: list
    produced: list
    missing: list
    extra: list
    matched: list
    invisible: list = field(default_factory=list)

    def ok(self):
        return not self.missing and not self.extra

    def render(self):
        line = (
            f"{len(self.expected)} expected · {len(self.matched)} matched · "
            f"{len(self.missing)} missing · {len(self.extra)} invented"
        )
        if self.invisible:
            line += f" · {len(self.invisible)} never dispatched"
        return line

    def as_dict(self):
        return {
            "expected": len(self.expected),
            "matched": len(self.matched),
            "missing": self.missing,
            "extra": self.extra,
            "invisible": self.invisible,
        }


def _keys(worklist, key):
    if hasattr(worklist, "key_set"):
        return worklist.key_set()
    return {item[key] if isinstance(item, dict) else item for item in worklist}


def compare(worklist, produced, key="id", universe=None):
    """`produced` may be a mapping keyed by id, or an iterable of records."""
    expected = _keys(worklist, key)
    if isinstance(produced, dict):
        got = set(produced)
    else:
        got = {item[key] if isinstance(item, dict) else item for item in produced}

    return Census(
        expected=sorted(expected),
        produced=sorted(got),
        missing=sorted(expected - got),
        extra=sorted(got - expected),
        matched=sorted(expected & got),
        invisible=report_invisible(worklist, universe, key) if universe else [],
    )


def strict_join(worklist, records, key="id"):
    """Only what was asked for, in work-list order.

    An invented record can never reach the output file even if a caller ignores
    the report — the gate is the write path, not a warning beside it.
    """
    expected = _keys(worklist, key)
    if isinstance(records, dict):
        return {ident: records[ident] for ident in sorted(expected) if ident in records}
    indexed = {item[key]: item for item in records if isinstance(item, dict) and key in item}
    return {ident: indexed[ident] for ident in sorted(expected) if ident in indexed}


def report_invisible(worklist, universe, key="id"):
    """Entities that never became dispatchable work.

    Not missing — nothing was ever sent for them, usually because they had no
    source to read. They get their own number so that "everything we dispatched
    came back" is never read as "we covered everything".
    """
    if universe is None:
        return []
    known = {item[key] if isinstance(item, dict) else item for item in universe}
    return sorted(known - _keys(worklist, key))


def persist(census, path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(census.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
