"""Fill-rate accounting, and the regression gate built on top of it.

`is_empty` gets tested in isolation because every other guarantee in this
module — the census table, the thin-field list, the regression gate — is
only as trustworthy as that one definition being applied consistently.
"""

from crawlkit.qa import census

# -- is_empty: the one definition -----------------------------------------


def test_none_is_empty():
    assert census.is_empty(None)


def test_empty_string_and_containers_are_empty():
    assert census.is_empty("")
    assert census.is_empty([])
    assert census.is_empty({})


def test_placeholder_sentinels_are_empty_regardless_of_case():
    assert census.is_empty("-")
    assert census.is_empty("n/a")
    assert census.is_empty("N/A")
    assert census.is_empty(" N/a ")


def test_a_real_value_is_not_empty():
    assert not census.is_empty("Paris")
    assert not census.is_empty(0)
    assert not census.is_empty(False)
    assert not census.is_empty(["x"])


# -- census -----------------------------------------------------------------


def test_census_counts_fill_rate_per_field():
    records = [
        {"id": "a", "title": "A", "price": "10"},
        {"id": "b", "title": "B", "price": ""},
        {"id": "c", "title": "", "price": "30"},
    ]
    result = census.census(records, fields=["title", "price"])
    assert result.total == 3
    assert result.filled == {"title": 2, "price": 2}
    assert result.rate["title"] == 2 / 3
    assert result.rate["price"] == 2 / 3


def test_fields_none_means_every_key_seen_anywhere():
    records = [{"id": "a", "x": "1"}, {"id": "b", "y": "2"}]
    result = census.census(records)
    assert set(result.rate) == {"x", "y"}
    assert result.filled == {"x": 1, "y": 1}


def test_empty_records_are_those_with_every_field_empty():
    records = [
        {"id": "a", "title": "A", "price": "10"},
        {"id": "b", "title": "", "price": "-"},
    ]
    result = census.census(records, fields=["title", "price"])
    assert result.empty_records == ["b"]


def test_census_of_no_records_does_not_divide_by_zero():
    result = census.census([], fields=["title"])
    assert result.total == 0
    assert result.rate == {"title": 0.0}


def test_render_lists_the_worst_field_first():
    records = [
        {"id": "a", "good": "x", "bad": ""},
        {"id": "b", "good": "y", "bad": ""},
    ]
    result = census.census(records, fields=["good", "bad"])
    text = result.render()
    assert text.index("bad") < text.index("good")


def test_thin_reports_fields_below_the_floor():
    records = [
        {"id": "a", "sparse": "x", "solid": "1"},
        {"id": "b", "sparse": "", "solid": "2"},
        {"id": "c", "sparse": "", "solid": "3"},
        {"id": "d", "sparse": "", "solid": "4"},
    ]
    result = census.census(records, fields=["sparse", "solid"])
    assert result.thin() == ["sparse"]
    assert result.thin(floor=0.0) == []


# -- compare: the regression gate -----------------------------------------


def test_compare_reports_a_negative_delta_when_a_field_regresses():
    before = census.census([{"id": "a", "x": "1"}, {"id": "b", "x": "1"}], fields=["x"])
    after = census.census([{"id": "a", "x": "1"}, {"id": "b", "x": ""}], fields=["x"])
    deltas = census.compare(before, after)
    assert deltas["x"] < 0


def test_compare_reports_a_positive_delta_when_a_field_improves():
    before = census.census([{"id": "a", "x": ""}], fields=["x"])
    after = census.census([{"id": "a", "x": "1"}], fields=["x"])
    deltas = census.compare(before, after)
    assert deltas["x"] > 0


def test_compare_is_zero_for_an_unchanged_field():
    before = census.census([{"id": "a", "x": "1"}], fields=["x"])
    after = census.census([{"id": "a", "x": "2"}], fields=["x"])
    assert census.compare(before, after)["x"] == 0.0


def test_tolerance_absorbs_a_small_drop():
    before = census.census(
        [{"id": str(i), "x": "1"} for i in range(100)],
        fields=["x"],
    )
    records = [{"id": str(i), "x": "1"} for i in range(100)]
    records[0]["x"] = ""  # one record regresses: a 1% drop
    after = census.census(records, fields=["x"])
    assert census.compare(before, after, tolerance=0.02)["x"] == 0.0
    assert census.compare(before, after, tolerance=0.0)["x"] < 0


def test_compare_covers_a_field_absent_from_one_side():
    before = census.FieldCensus(total=1, filled={}, rate={}, empty_records=[])
    after = census.census([{"id": "a", "new_field": "1"}], fields=["new_field"])
    deltas = census.compare(before, after)
    assert deltas["new_field"] == 1.0
