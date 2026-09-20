"""The scrape reports success and the record is hollow.

A fetch failure raises, or comes back with a status code, or trips one of the
other detectors in this package — some layer notices. A parser that silently
stops finding a field notices nothing: the page loaded, the record got
written, the pipeline moved on. The only way to see the gap is to count how
often each field was actually filled, across the whole batch, and compare
that count to what it used to be.

`compare` is the part that turns a one-off report into a gate a CI job can
fail on: run the same parser over the same saved pages twice (before and
after a change) and any field whose fill rate dropped is a regression, full
stop — no page needs to look broken for this to catch it, which is exactly
the case a page saved mid-hydration or a parser typo produces.
"""

from dataclasses import dataclass

# Where `census.thin()` draws the line between "some records lack this field"
# and "this field is functionally missing". Half is a floor, not a target —
# a field a caller actually depends on should be nowhere near it.
THIN_FLOOR = 0.5

# Values a scraper writes to mean "nothing here" instead of leaving the key
# out entirely — a placeholder from a template, not real content.
EMPTY_SENTINELS = frozenset({"-", "n/a"})


def is_empty(value) -> bool:
    """The one definition of "no data here", used by every check in this module.

    Two definitions drifting apart is how a census silently stops counting a
    field's "-" placeholder as empty, or starts counting a legitimate empty
    list as filled.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value == "" or value.strip().lower() in EMPTY_SENTINELS
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


@dataclass(frozen=True)
class FieldCensus:
    total: int
    filled: dict[str, int]
    rate: dict[str, float]
    empty_records: list[str]

    def render(self) -> str:
        """A table, worst field first — the order a human should read it in."""
        header = f"{'field':<28}{'filled':>8}{'total':>8}{'rate':>8}"
        lines = [header, "-" * len(header)]
        for field in sorted(self.rate, key=lambda f: self.rate[f]):
            lines.append(
                f"{field:<28}{self.filled[field]:>8}{self.total:>8}{self.rate[field]:>8.1%}"
            )
        lines.append(f"\n{len(self.empty_records)} record(s) with every field empty")
        return "\n".join(lines)

    def thin(self, floor=THIN_FLOOR) -> list[str]:
        """Fields filled in fewer than `floor` of records — candidates for a broken selector."""
        return [field for field, rate in self.rate.items() if rate < floor]


def census(records, fields=None, key="id") -> FieldCensus:
    records = list(records)
    if fields is None:
        # Every key seen anywhere, not just in the first record: a field that
        # only appears once a parser variant kicks in must still be counted.
        # The identifier itself is excluded — it is filled by construction.
        fields = list(dict.fromkeys(name for record in records for name in record if name != key))

    total = len(records)
    filled = {field: 0 for field in fields}
    for record in records:
        for field in fields:
            if not is_empty(record.get(field)):
                filled[field] += 1

    rate = {field: (filled[field] / total if total else 0.0) for field in fields}
    empty_records = [
        record.get(key)
        for record in records
        if all(is_empty(record.get(field)) for field in fields)
    ]
    return FieldCensus(total=total, filled=filled, rate=rate, empty_records=empty_records)


def compare(before: FieldCensus, after: FieldCensus, *, tolerance=0.0) -> dict:
    """field -> rate delta (after - before). Negative is a regression.

    `tolerance` absorbs sampling noise between two runs (a handful of records
    landing differently) so it does not have to be re-tuned every time the
    corpus shifts slightly; deltas within it are reported as exactly 0.0
    rather than a false positive.
    """
    fields = dict.fromkeys(list(before.rate) + list(after.rate))
    deltas = {}
    for field in fields:
        delta = after.rate.get(field, 0.0) - before.rate.get(field, 0.0)
        deltas[field] = 0.0 if abs(delta) <= tolerance else delta
    return deltas
