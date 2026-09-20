"""Who may say what, and who does the arithmetic."""

import pytest

from crawlkit import contract
from crawlkit.agents import scalar, sections, verdicts

# -- the relation the contract claims -------------------------------------


def test_every_value_a_prompt_offers_is_a_value_the_ingester_accepts():
    """The claim `constants.json` makes about this module, asserted.

    Offered and accepted are one object filtered two ways. Maintained as two
    lists they skew, and the symptom is a fanout's worth of rejected records
    with no obvious cause.
    """
    for name in verdicts.vocabularies():
        assert set(verdicts.offered(name)) <= set(verdicts.accepted(name))
        assert verdicts.offered(name), f"{name} offers nothing to an agent"


def test_the_in_prompt_guide_lists_exactly_the_offered_values():
    for name in ("content_status", "coverage_status", "verify_verdict"):
        guide = sections.verdict_guide(name)
        for value in verdicts.offered(name):
            assert value in guide
        for value in verdicts.derived(name):
            assert value not in guide


def test_a_derived_verdict_from_an_agent_is_rejected_with_a_reason():
    """An agent reporting `manual` has named the conclusion the script was
    about to draw, which is exactly the authority the split withholds."""
    assert verdicts.validate("coverage_status", "manual") == "manual"
    with pytest.raises(verdicts.VerdictError) as caught:
        verdicts.validate("coverage_status", "manual", from_agent=True)
    assert "derived by the caller" in str(caught.value)


def test_an_unknown_value_is_rejected_from_either_side():
    with pytest.raises(verdicts.VerdictError):
        verdicts.validate("content_status", "probably_fine")
    with pytest.raises(verdicts.VerdictError):
        verdicts.validate("content_status", "probably_fine", from_agent=True)


def test_check_record_accumulates_instead_of_raising():
    problems = verdicts.check_record(
        {"content_status": "nope", "coverage_status": "ok"},
        {"content_status": "content_status", "coverage_status": "coverage_status"},
    )
    assert len(problems) == 1


def test_a_missing_field_is_not_a_vocabulary_problem():
    assert verdicts.check_record({}, {"content_status": "content_status"}) == []


def test_every_value_carries_a_gloss():
    for name in verdicts.vocabularies():
        for value in verdicts.accepted(name):
            assert verdicts.gloss(name, value).strip()


# -- the arithmetic the agent never does ----------------------------------


def measurement(**kwargs):
    base = {"item_id": "x", "source_count": 100, "status": "ok"}
    return scalar.parse_measurement({**base, **kwargs})


def test_coverage_at_or_above_the_threshold_passes():
    floor = contract.get("coverage.threshold")
    assessment = scalar.assess(measurement(source_count=100), int(100 * floor))
    assert assessment.verdict == "ok"
    assert assessment.ratio == pytest.approx(floor)


def test_coverage_below_the_threshold_is_undercoverage():
    assert scalar.assess(measurement(source_count=100), 10).verdict == "undercoverage"


def test_a_source_that_could_not_be_read_is_never_scored_as_passing():
    """The tempting arithmetic is 0/0 = 1.0 = complete. Unmeasured is its own
    bucket, because the alternative silently reports perfect coverage of
    everything nobody could open."""
    for status in ("unparseable", "access_blocked"):
        assessment = scalar.assess(measurement(status=status, source_count=0), 0)
        assert assessment.verdict == "manual"
        assert assessment.ratio is None


def test_a_zero_count_from_a_readable_source_is_also_unknown():
    assessment = scalar.assess(measurement(source_count=0), 0)
    assert assessment.verdict == "manual"


def test_storing_more_than_the_source_lists_passes_but_says_so():
    assessment = scalar.assess(measurement(source_count=10), 12)
    assert assessment.verdict == "ok"
    assert "exceeds" in assessment.reason


def test_an_agent_cannot_report_a_derived_status():
    with pytest.raises(verdicts.VerdictError):
        scalar.parse_measurement({"item_id": "x", "source_count": 5, "status": "undercoverage"})


def test_a_non_integer_count_is_rejected():
    for bad in ("12", 1.5, True, None):
        with pytest.raises(scalar.ScalarError):
            scalar.parse_measurement({"item_id": "x", "source_count": bad, "status": "ok"})


def test_a_negative_count_is_rejected():
    with pytest.raises(scalar.ScalarError):
        scalar.parse_measurement({"item_id": "x", "source_count": -1, "status": "ok"})


def test_the_local_side_is_supplied_by_the_caller_not_the_agent():
    """assess_all takes counts the caller read itself; a measurement carries
    only the source side, so a number counted at plan time cannot go stale."""
    measurements = [measurement(item_id="a"), measurement(item_id="b")]
    out = scalar.assess_all(measurements, {"a": 100, "b": 5})
    assert [a.verdict for a in out] == ["ok", "undercoverage"]


def test_an_item_with_no_local_record_is_flagged_rather_than_scored():
    out = scalar.assess_all([measurement(item_id="ghost")], {})
    assert out[0].verdict == "manual"


def test_the_invisible_class_is_reported_separately():
    """Items that never became measurable work are not 'missing' — nothing was
    dispatched for them. Keeping them apart stops '100% of dispatched' from
    reading as '100% of reality'."""
    assert scalar.invisible(["a", "b", "c"], ["a", "b"]) == ["c"]


def test_summarize_counts_by_verdict():
    out = scalar.assess_all(
        [measurement(item_id="a"), measurement(item_id="b", source_count=100)],
        {"a": 100, "b": 1},
    )
    assert scalar.summarize(out) == {"ok": 1, "undercoverage": 1}
