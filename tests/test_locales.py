"""Block-page matching is language-specific; the language list is data.

Hardcoding one language inside a detector is wrong twice: it silently narrows
the tool to wherever it was written, and extending it means editing a module.
So the phrases live in the contract, English is the default, and a caller opts
into more.
"""

import pytest

from crawlkit import circuit, contract
from crawlkit.qa import soft_error


def test_every_locale_carries_every_category():
    """A half-populated locale is worse than a missing one: you enable it and
    quietly get no soft-error coverage at all."""
    codes = [code for code in contract.get("locales") if not code.startswith("_")]
    assert codes, "no locales defined"
    for code in codes:
        entry = contract.get(f"locales.{code}")
        missing = set(contract.LOCALE_CATEGORIES) - set(entry)
        assert not missing, f"locale {code} is missing {sorted(missing)}"
        for category in contract.LOCALE_CATEGORIES:
            assert isinstance(entry[category], list)


def test_the_default_is_english_only():
    assert contract.locales() == ("en",)
    markers = contract.markers("challenge_markers")
    assert "just a moment" in markers
    assert all(marker.isascii() for marker in markers), markers


def test_selecting_a_locale_adds_its_phrases_without_losing_english():
    markers = contract.markers("challenge_markers", ["en", "ru"])
    assert "just a moment" in markers
    assert "доступ ограничен" in markers


def test_markers_are_lowercased_and_deduped():
    markers = contract.markers("consent_labels", ["en", "en"])
    assert markers == tuple(dict.fromkeys(markers))
    assert all(marker == marker.lower() for marker in markers)


def test_an_unknown_locale_fails_loudly_rather_than_matching_nothing():
    with pytest.raises(KeyError):
        contract.locales(["klingon"])


def test_an_unknown_category_is_a_typo_not_an_empty_list():
    with pytest.raises(KeyError):
        contract.markers("challenge_marker")  # singular


def test_the_env_var_selects_locales(monkeypatch):
    monkeypatch.setenv("CRAWLKIT_LOCALES", "en,ru")
    assert contract.locales() == ("en", "ru")


# -- the detectors honour it ---------------------------------------------


def test_the_breaker_does_not_match_a_language_the_caller_did_not_ask_for():
    english_only = circuit.Breaker()
    assert english_only.classify(status=200, body="Доступ ограничен") is None
    assert english_only.classify(status=200, body="Just a moment...") == "refused"

    bilingual = circuit.Breaker(locales=["en", "ru"])
    assert bilingual.classify(status=200, body="Доступ ограничен") == "refused"


def test_soft_error_honours_the_selected_locales():
    page = "<html><body>Закончилась текущая сессия</body></html>"
    assert not soft_error.is_soft_error(page * 40, locales=["en"])
    assert soft_error.is_soft_error(page, locales=["en", "ru"])


# -- the length ceiling ---------------------------------------------------


def test_a_short_untitled_page_carrying_the_phrase_is_a_soft_error():
    suspect, reasons = soft_error.inspect("<html><body>Session has expired</body></html>")
    assert suspect
    assert any("error phrase" in reason for reason in reasons)


def test_a_long_article_that_merely_discusses_expired_sessions_is_not_flagged():
    """The phrase alone cannot be conclusive, or every article about session
    handling becomes a fetch failure."""
    body = "Session handling in web applications. " * 200
    html = (
        f"<html><head><title>On sessions</title></head><body>{body} session expired</body></html>"
    )
    suspect, reasons = soft_error.inspect(html)
    assert not suspect, reasons


def test_a_terse_but_titled_page_is_not_condemned_by_brevity_alone():
    suspect, _ = soft_error.inspect("<html><head><title>Ok</title></head><body>done</body></html>")
    assert not suspect
