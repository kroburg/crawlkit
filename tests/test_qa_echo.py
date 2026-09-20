"""An extractor field that leaked its own input instead of the page's content.

The two conclusive checks (a URL, a percent-escape) each have to stand alone
without a second signal, and the weak checks each have to stay switched off
for the ordinary text that resembles them — a bare `%` above all, because
that is the rule someone reaches for first and the one with the worst
false-positive rate in the wild.
"""

from crawlkit.qa import echo

# -- conclusive signals -----------------------------------------------------


def test_a_bare_url_is_conclusive_on_its_own():
    suspect, reasons = echo.looks_echoed("https://shop.example/item/4471")
    assert suspect
    assert any("URL" in reason for reason in reasons)


def test_an_http_url_is_conclusive_too():
    suspect, _ = echo.looks_echoed("http://example.test/path")
    assert suspect


def test_a_percent_escape_is_conclusive_on_its_own():
    suspect, reasons = echo.looks_echoed("Caf%C3%A9 de Paris")
    assert suspect
    assert any("percent-escape" in reason for reason in reasons)


# -- the corrected rule: a bare percent sign is not an escape ---------------


def test_a_discount_percentage_in_russian_is_not_flagged():
    suspect, reasons = echo.looks_echoed("Скидка 50% на всё")
    assert not suspect, reasons


def test_an_inflation_percentage_in_english_is_not_flagged():
    suspect, reasons = echo.looks_echoed("Inflation rose 5% last year")
    assert not suspect, reasons


def test_a_percent_sign_not_followed_by_two_hex_digits_never_matches():
    assert not echo.PERCENT_ESCAPE.search("100% sure, %  not escaped, %g also not")


# -- weak signals require two -------------------------------------------------


def test_a_single_weak_signal_alone_is_not_enough():
    # Ends in .html but is short and has plenty of whitespace and letters:
    # only one weak signal fires.
    suspect, reasons = echo.looks_echoed("The Story So Far.html")
    assert not suspect, reasons


def test_a_long_run_with_no_whitespace_and_a_file_extension_is_two_signals():
    value = "product-catalog-page-listing-detail.html"
    suspect, reasons = echo.looks_echoed(value)
    assert suspect
    assert len(reasons) >= 2


def test_a_short_run_with_no_whitespace_does_not_trip_the_floor():
    suspect, _ = echo.looks_echoed("SKU-4471")
    assert not suspect


def test_mostly_punctuation_combined_with_no_whitespace_trips_two_signals():
    value = "//::--__==++~~!!??..,,;;''\"\"##"
    suspect, reasons = echo.looks_echoed(value)
    assert suspect
    assert len(reasons) >= 2


def test_punctuation_heavy_but_genuine_prose_is_not_flagged():
    suspect, reasons = echo.looks_echoed("Q3 2024: Revenue Up 12%, Margins Hold")
    assert not suspect, reasons


# -- non-string / empty values ------------------------------------------------


def test_none_is_not_suspect():
    assert echo.looks_echoed(None) == (False, [])


def test_empty_string_is_not_suspect():
    assert echo.looks_echoed("") == (False, [])


def test_a_non_string_value_is_not_suspect():
    assert echo.looks_echoed(12345) == (False, [])


# -- kind labels the reason, not the check ------------------------------------


def test_kind_labels_the_reason():
    _, reasons = echo.looks_echoed("https://x.test", kind="description")
    assert any("description" in reason for reason in reasons)


# -- scan_records --------------------------------------------------------


def test_scan_records_reports_record_id_field_and_reasons():
    records = [
        {"id": "a", "title": "https://x.test/a", "summary": "A perfectly normal summary."},
        {"id": "b", "title": "Ordinary title", "summary": "Another fine one."},
    ]
    found = echo.scan_records(records, ["title", "summary"])
    assert len(found) == 1
    hit = found[0]
    assert hit.record_id == "a"
    assert hit.field == "title"
    assert hit.value == "https://x.test/a"
    assert hit.reasons


def test_scan_records_finds_nothing_in_clean_data():
    records = [{"id": "a", "title": "Скидка 50% на всё"}]
    assert echo.scan_records(records, ["title"]) == []


def test_scan_records_uses_the_given_key():
    records = [{"pk": "z9", "title": "http://x.test"}]
    found = echo.scan_records(records, ["title"], key="pk")
    assert found[0].record_id == "z9"
