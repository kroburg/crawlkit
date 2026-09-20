"""Two independent passes, and the rule that a lone value never counts as a tie.

`test_absence_is_not_treated_as_agreement` is the load-bearing test: it is
exactly the shortcut a tired implementation reaches for (one pass has a
value, the other has nothing, so just use the one that exists) and exactly
the bug the module's docstring calls out by name.
"""

from crawlkit.qa import agreement


def test_matching_values_are_agreed():
    pass_a = [{"id": "1", "title": "Blue Widget"}]
    pass_b = [{"id": "1", "title": "Blue Widget"}]
    result = agreement.compare(pass_a, pass_b, ["title"])
    assert result.agreed == {"1": {"title": "Blue Widget"}}
    assert result.disputed == {}


def test_values_that_normalize_the_same_are_agreed():
    pass_a = [{"id": "1", "title": "Blue  Widget "}]
    pass_b = [{"id": "1", "title": "blue widget"}]
    result = agreement.compare(pass_a, pass_b, ["title"])
    assert result.agreed == {"1": {"title": "Blue  Widget "}}


def test_conflicting_values_are_disputed():
    pass_a = [{"id": "1", "title": "Blue Widget"}]
    pass_b = [{"id": "1", "title": "Red Widget"}]
    result = agreement.compare(pass_a, pass_b, ["title"])
    assert result.disputed == {"1": {"title": {"a": "Blue Widget", "b": "Red Widget"}}}
    assert result.agreed == {}


def test_absence_is_not_treated_as_agreement():
    """A value only pass A produced is not a tie pass A wins by default."""
    pass_a = [{"id": "1", "title": "Blue Widget"}]
    pass_b = [{"id": "1"}]
    result = agreement.compare(pass_a, pass_b, ["title"])
    assert result.agreed == {}
    assert result.disputed == {}
    assert result.only_in_a == {"1": {"title": "Blue Widget"}}
    assert result.only_in_b == {}


def test_a_record_missing_from_one_pass_entirely_is_only_in_the_other():
    pass_a = [{"id": "1", "title": "Blue Widget"}]
    pass_b = []
    result = agreement.compare(pass_a, pass_b, ["title"])
    assert result.only_in_a == {"1": {"title": "Blue Widget"}}


def test_neither_pass_producing_a_value_reports_nothing():
    pass_a = [{"id": "1", "title": ""}]
    pass_b = [{"id": "1"}]
    result = agreement.compare(pass_a, pass_b, ["title"])
    assert result.agreed == {}
    assert result.disputed == {}
    assert result.only_in_a == {}
    assert result.only_in_b == {}


def test_a_record_may_be_partly_agreed_and_partly_disputed():
    pass_a = [{"id": "1", "title": "Blue Widget", "price": "10"}]
    pass_b = [{"id": "1", "title": "Blue Widget", "price": "20"}]
    result = agreement.compare(pass_a, pass_b, ["title", "price"])
    assert result.agreed == {"1": {"title": "Blue Widget"}}
    assert result.disputed == {"1": {"price": {"a": "10", "b": "20"}}}


# -- number_norm ------------------------------------------------------------


def test_number_norm_treats_close_numbers_as_equal():
    pass_a = [{"id": "1", "count": "100"}]
    pass_b = [{"id": "1", "count": "100.6"}]
    result = agreement.compare(
        pass_a, pass_b, ["count"], normalize={"count": agreement.number_norm(1)}
    )
    assert result.agreed == {"1": {"count": "100"}}


def test_number_norm_still_disputes_numbers_far_apart():
    pass_a = [{"id": "1", "count": "100"}]
    pass_b = [{"id": "1", "count": "150"}]
    result = agreement.compare(
        pass_a, pass_b, ["count"], normalize={"count": agreement.number_norm(1)}
    )
    assert result.disputed == {"1": {"count": {"a": "100", "b": "150"}}}


def test_number_norm_falls_back_to_text_for_non_numeric_values():
    norm = agreement.number_norm(1)
    assert norm("abc") == agreement.text_norm("abc")


# -- rate ---------------------------------------------------------------


def test_rate_is_fraction_of_comparable_values_that_agreed():
    pass_a = [{"id": "1", "a": "x", "b": "y"}]
    pass_b = [{"id": "1", "a": "x", "b": "z"}]
    result = agreement.compare(pass_a, pass_b, ["a", "b"])
    assert result.rate() == 0.5


def test_rate_excludes_coverage_gaps_from_the_denominator():
    """A field only one pass ever produces must not drag the rate down —
    that is a coverage story, not a disagreement story."""
    pass_a = [{"id": "1", "a": "x", "extra": "only here"}]
    pass_b = [{"id": "1", "a": "x"}]
    result = agreement.compare(pass_a, pass_b, ["a", "extra"])
    assert result.rate() == 1.0


def test_rate_is_vacuously_one_with_nothing_comparable():
    result = agreement.compare([{"id": "1"}], [{"id": "1"}], ["title"])
    assert result.rate() == 1.0


def test_render_includes_the_rate_and_counts():
    result = agreement.compare([{"id": "1", "a": "x"}], [{"id": "1", "a": "x"}], ["a"])
    text = result.render()
    assert "100.0%" in text
    assert "agreed: 1" in text


# -- auto_applicable ------------------------------------------------------


def test_auto_applicable_returns_only_the_agreed_values():
    pass_a = [{"id": "1", "title": "Blue Widget", "price": "10"}]
    pass_b = [{"id": "1", "title": "Blue Widget"}]
    result = agreement.compare(pass_a, pass_b, ["title", "price"])
    assert agreement.auto_applicable(result) == {"1": {"title": "Blue Widget"}}


def test_auto_applicable_never_includes_a_value_present_in_only_one_pass():
    pass_a = [{"id": "1", "title": "Blue Widget"}]
    pass_b = [{"id": "1"}]
    result = agreement.compare(pass_a, pass_b, ["title"])
    assert agreement.auto_applicable(result) == {}


# -- text_norm ------------------------------------------------------------


def test_text_norm_folds_case_and_whitespace():
    assert agreement.text_norm("  Blue   Widget  ") == agreement.text_norm("blue widget")


def test_text_norm_of_none_is_empty_string():
    assert agreement.text_norm(None) == ""


# -- key --------------------------------------------------------------------


def test_compare_uses_the_given_key():
    pass_a = [{"pk": "z9", "title": "Blue Widget"}]
    pass_b = [{"pk": "z9", "title": "Blue Widget"}]
    result = agreement.compare(pass_a, pass_b, ["title"], key="pk")
    assert result.agreed == {"z9": {"title": "Blue Widget"}}
