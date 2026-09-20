"""The probe ladder against the fixture, one test per false-positive class.

These four classes are the reason the ladder exists. Each of them looks like a
dead link to a HEAD-only checker, and deleting the URL on that evidence is how
a link database quietly loses good sources.
"""

import ssl
import urllib.error

import pytest

from crawlkit import probe
from fixtures import hosts


def test_405_on_head_is_reported_live_after_the_get_fallback(fixture_http):
    assert probe.check_one(f"{fixture_http}/head405") == 200


def test_404_on_head_but_200_on_get_is_reported_live(fixture_http):
    assert probe.check_one(f"{fixture_http}/head404") == 200


def test_a_real_404_is_still_reported_404(fixture_http):
    """Negative control: the fallback must not launder genuine breakage."""
    assert probe.check_one(f"{fixture_http}/dead") == 404


def test_untrusted_tls_chain_retries_relaxed_and_reports_live(fixture_https, named_hosts):
    assert probe.check_one(f"{fixture_https}/health") == 200


def test_slow_pdf_survives_the_longer_timeout_while_the_same_delay_kills_a_non_pdf(fixture_http):
    slow = "?delay=1.6"
    assert probe.check_one(f"{fixture_http}/slow.pdf{slow}", timeout_s=0.4, pdf_timeout_s=8) == 200
    assert (
        probe.check_one(f"{fixture_http}/slow.bin{slow}", timeout_s=0.4, pdf_timeout_s=8)
        == probe.FAILURE
    )


def test_connection_failure_is_the_sentinel_not_an_exception(free_port):
    assert probe.check_one(f"http://127.0.0.1:{free_port}/nothing") == probe.FAILURE


def test_timeout_for_keys_on_the_extension_ignoring_the_query():
    assert probe.timeout_for("http://h/x.pdf") == probe.PDF_TIMEOUT_S
    assert probe.timeout_for("http://h/x.PDF?v=2") == probe.PDF_TIMEOUT_S
    assert probe.timeout_for("http://h/x.html") == probe.TIMEOUT_S


# -- TLS classification --------------------------------------------------


def test_tls_errors_are_recognised_through_all_three_wrappings():
    assert probe.is_tls_error(ssl.SSLError("boom"))
    assert probe.is_tls_error(urllib.error.URLError(ssl.SSLError("boom")))
    assert probe.is_tls_error(Exception("certificate verify failed"))


def test_a_plain_connection_error_is_not_mistaken_for_tls():
    assert not probe.is_tls_error(ConnectionRefusedError("refused"))


# -- URL encoding --------------------------------------------------------


def test_idna_host_and_percent_path_use_their_own_encodings(fixture_port, named_hosts):
    url = f"http://{hosts.IDN_HOST}:{fixture_port}/пример/страница.pdf"
    encoded = probe.encode_url(url)
    assert hosts.IDN_HOST_ASCII in encoded
    assert "%D0%BF" in encoded
    assert probe.check_one(url) == 200


def test_encoding_is_idempotent():
    url = "http://пример.test/путь с пробелом.pdf?q=знач&x=1#фраг"
    once = probe.encode_url(url)
    assert probe.encode_url(once) == once
    assert "%25" not in once


def test_query_and_fragment_keep_their_structural_characters():
    encoded = probe.encode_url("http://h/p?a=1&b=два#раз")
    assert "a=1&b=" in encoded
    assert encoded.endswith("#%D1%80%D0%B0%D0%B7")


def test_port_and_credentials_survive_encoding():
    assert (
        probe.encode_url("http://u:p@пример.test:8080/x") == "http://u:p@xn--e1afmkfd.test:8080/x"
    )


def test_unencodable_host_degrades_instead_of_dropping_the_url():
    long_label = "a" * 80
    assert long_label in probe.encode_url(f"http://{long_label}.test/x")


@pytest.mark.parametrize("bad", ["", "not a url", "http://"])
def test_malformed_input_returns_the_sentinel_rather_than_raising(bad):
    assert probe.check_one(bad) == probe.FAILURE
