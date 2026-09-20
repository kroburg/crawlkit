"""The scalar split: the agent measures one number, the script judges it.

An agent asked "is our coverage of this source good enough?" will tell you yes.
An agent asked "how many items does this source list?" will count. The
difference is not the model's honesty — it is that the first question requires
knowing what answer passes, and once that is knowable it is reachable.

So the prompt carries no threshold, no ratio and no verdict name (there is a
test for that in tests/test_sections.py), the agent returns a `Measurement`,
and every comparison happens here against a count the script re-reads itself at
apply time. An agent cannot pass its own audit, and a count measured when the
work was planned cannot go stale between then and now.
"""

from dataclasses import dataclass

from crawlkit import contract
from crawlkit.agents import verdicts

THRESHOLD = contract.get("coverage.threshold")


class ScalarError(ValueError):
    pass


@dataclass(frozen=True)
class Measurement:
    """What the agent reported. Nothing derived lives in here."""

    item_id: str
    source_count: int
    status: str
    note: str = ""


@dataclass(frozen=True)
class Assessment:
    """What the script concluded. The agent never sees these fields."""

    item_id: str
    source_count: int | None
    stored_count: int
    ratio: float | None
    threshold: float
    verdict: str
    reason: str


def parse_measurement(payload, item_id=None):
    ident = payload.get("item_id") or item_id
    if not ident:
        raise ScalarError("measurement has no item_id and none was supplied")

    status = payload.get("status")
    if status is None:
        raise ScalarError(f"{ident}: measurement has no status")
    verdicts.validate("coverage_status", status, from_agent=True, where=ident)

    raw = payload.get("source_count", 0)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ScalarError(f"{ident}: source_count must be an integer, got {raw!r}")
    if raw < 0:
        raise ScalarError(f"{ident}: source_count is negative ({raw})")

    return Measurement(ident, raw, status, payload.get("note") or "")


def assess(measurement, stored_count, threshold=None):
    """Compare a measurement against a locally-counted number."""
    floor = THRESHOLD if threshold is None else threshold

    if measurement.status != "ok":
        return Assessment(
            measurement.item_id,
            None,
            stored_count,
            None,
            floor,
            "manual",
            f"source could not be measured ({measurement.status})",
        )

    # The arithmetic trap: 0/0 is not 1.0, and an unreadable source is not full
    # coverage. Unknown gets its own bucket and is never scored as passing.
    if measurement.source_count <= 0:
        return Assessment(
            measurement.item_id,
            measurement.source_count,
            stored_count,
            None,
            floor,
            "manual",
            "source reported zero items; coverage is unknown, not complete",
        )

    ratio = stored_count / measurement.source_count
    if ratio > 1:
        return Assessment(
            measurement.item_id,
            measurement.source_count,
            stored_count,
            round(ratio, 3),
            floor,
            "ok",
            f"stored {stored_count} exceeds the {measurement.source_count} counted at "
            f"source — worth a look, usually an undercount by the agent",
        )
    verdict = "ok" if ratio >= floor else "undercoverage"
    return Assessment(
        measurement.item_id,
        measurement.source_count,
        stored_count,
        round(ratio, 3),
        floor,
        verdict,
        f"{stored_count} of {measurement.source_count}",
    )


def assess_all(measurements, stored_counts, threshold=None):
    """`stored_counts` is re-read by the caller at apply time, never at plan time."""
    out = []
    for measurement in measurements:
        if measurement.item_id not in stored_counts:
            out.append(
                Assessment(
                    measurement.item_id,
                    measurement.source_count,
                    0,
                    None,
                    THRESHOLD if threshold is None else threshold,
                    "manual",
                    "no local record to compare against",
                )
            )
            continue
        out.append(assess(measurement, stored_counts[measurement.item_id], threshold))
    return out


def summarize(assessments):
    counts = {}
    for assessment in assessments:
        counts[assessment.verdict] = counts.get(assessment.verdict, 0) + 1
    return counts


def invisible(universe, measured):
    """Entities that never became measurable work.

    Not "missing" — the fanout never saw them, usually because they had no
    source to measure. They are their own bucket so that "100% of what we
    dispatched" is never mistaken for "100% of what exists".
    """
    return sorted(set(universe) - set(measured))
