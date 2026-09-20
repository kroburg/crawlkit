"""Coverage for soft_error.py beyond what tests/test_locales.py already pins.

test_locales.py owns: locale selection honoured by `inspect`, the length
ceiling on the phrase-alone case, and the "brevity or missing title alone is
not enough" cases. This file covers the pieces that test doesn't touch:
the helper functions in isolation, the error-icon signal, an explicit
`marker_ceiling` override, and the wrapper's equivalence to `inspect`.
"""

from crawlkit.qa import soft_error

# -- visible_text / title_of --------------------------------------------


def test_visible_text_strips_tags_and_collapses_whitespace():
    html = "<html><body><p>Hello\n\n  world</p></body></html>"
    assert soft_error.visible_text(html) == "Hello world"


def test_visible_text_drops_script_and_style_content_not_just_their_tags():
    html = "<html><body><script>var x = 'error';</script><p>Real text</p></body></html>"
    text = soft_error.visible_text(html)
    assert "error" not in text
    assert "Real text" in text


def test_visible_text_of_none_is_empty():
    assert soft_error.visible_text(None) == ""


def test_title_of_extracts_the_title_text():
    assert soft_error.title_of("<html><head><title> Home </title></head></html>") == "Home"


def test_title_of_missing_title_is_none():
    assert soft_error.title_of("<html><body>no head here</body></html>") is None


# -- the error-icon signal ------------------------------------------------


def test_an_error_icon_is_one_of_the_counted_signals():
    html = "<html><body><img src='/static/error.png'>Short body</body></html>"
    suspect, reasons = soft_error.inspect(html, min_text=500)
    assert any("error icon" in reason for reason in reasons)
    assert suspect  # paired with the short-body signal, two reasons


def test_an_unrelated_icon_is_not_mistaken_for_an_error_icon():
    html = "<html><body><img src='/static/logo.png'>text</body></html>"
    _, reasons = soft_error.inspect(html)
    assert not any("error icon" in reason for reason in reasons)


# -- the conclusive-alone branch: phrase + under the ceiling ---------------


def test_the_phrase_alone_is_conclusive_when_short_enough_even_with_a_title():
    """Isolates the `conclusive` branch in inspect(): a titled page, long
    enough to dodge the brevity signal, still trips on the phrase alone as
    long as it stays under the length ceiling."""
    body = "Please try again later. " * 25 + " access denied "
    html = f"<html><head><title>Notice</title></head><body>{body}</body></html>"
    text_len = len(soft_error.visible_text(html))
    assert 500 <= text_len < 500 * 4  # inside min_text..ceiling, and titled
    suspect, reasons = soft_error.inspect(html, min_text=500)
    assert suspect
    assert reasons == [reason for reason in reasons if "error phrase" in reason]


def test_marker_ceiling_can_be_tightened_below_the_default():
    """A caller who only trusts the phrase over a much narrower window can say
    so explicitly, rather than being stuck with min_text * 4."""
    body = "Please try again later. " * 25 + " access denied "
    html = f"<html><head><title>Notice</title></head><body>{body}</body></html>"
    text_len = len(soft_error.visible_text(html))
    suspect, reasons = soft_error.inspect(html, min_text=500, marker_ceiling=text_len - 1)
    assert not suspect, reasons  # phrase is now only one weak-ish signal, not conclusive


# -- edge cases -----------------------------------------------------------


def test_a_completely_empty_response_body_is_suspect():
    suspect, reasons = soft_error.inspect("")
    assert suspect
    assert len(reasons) >= 2


def test_none_body_behaves_like_an_empty_one():
    assert soft_error.inspect(None) == soft_error.inspect("")


# -- is_soft_error is exactly inspect()[0] --------------------------------


def test_is_soft_error_matches_inspect_first_element():
    html = "<html><body>Session has expired</body></html>"
    assert soft_error.is_soft_error(html) == soft_error.inspect(html)[0]

    html_ok = "<html><head><title>Fine</title></head><body>" + "content " * 200 + "</body></html>"
    assert soft_error.is_soft_error(html_ok) == soft_error.inspect(html_ok)[0]
