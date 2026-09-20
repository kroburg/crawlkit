"""The fixture must be proven before anything is tested against it.

If an endpoint quietly stops imitating its wall, every suite downstream goes
green for the wrong reason. So each endpoint is asserted here, at the HTTP
level, with no crawler code involved.
"""

import http.cookies
import json
import ssl
import time
import urllib.error
import urllib.request

import pytest

from fixtures import hosts, media


def _get(url, method="GET", headers=None, timeout=20):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def test_health(fixture_http):
    assert _get(f"{fixture_http}/health")[0] == 200


# -- challenge endpoints -------------------------------------------------


def test_challenge_stub_is_large_markup_but_almost_no_text(fixture_http):
    """The trap for a body-length check written against innerHTML."""
    _, body, _ = _get(f"{fixture_http}/challenge/never")
    html = body.decode()
    assert len(html) > 20000, "stub should be bulky markup"
    assert "Just a moment" in html
    # Strip tags crudely: what a reader would actually see is tiny.
    visible = html.split("<div id='cf'>")[1].split("</div>")[0]
    assert len(visible) < 100


def test_challenge_clears_after_n_hits_for_one_session(fixture_http):
    jar = None
    seen = []
    for _ in range(4):
        headers = {"Cookie": jar} if jar else {}
        status, body, hdrs = _get(f"{fixture_http}/challenge/clears-after/3", headers=headers)
        assert status == 200
        if "Set-Cookie" in hdrs:
            cookie = http.cookies.SimpleCookie(hdrs["Set-Cookie"])
            jar = f"ck_session={cookie['ck_session'].value}"
        seen.append(b"Just a moment" in body)
    assert seen == [True, True, True, False], seen


def test_challenge_counter_is_per_session_not_global(fixture_http):
    """A second client starts at the wall again — otherwise the test order leaks."""
    for _ in range(4):
        _get(f"{fixture_http}/challenge/clears-after/3")
    _, body, _ = _get(f"{fixture_http}/challenge/clears-after/3")
    assert b"Just a moment" in body


def test_autoreload_stub_carries_its_own_reload(fixture_http):
    _, body, _ = _get(f"{fixture_http}/challenge/autoreload")
    assert b"location.reload()" in body


def test_never_clearing_challenge_never_clears(fixture_http):
    for _ in range(5):
        _, body, _ = _get(f"{fixture_http}/challenge/never")
        assert b"Just a moment" in body


# -- probe-ladder endpoints ---------------------------------------------


def test_head405_but_get_200(fixture_http):
    assert _get(f"{fixture_http}/head405", method="HEAD")[0] == 405
    assert _get(f"{fixture_http}/head405")[0] == 200


def test_head404_but_get_200(fixture_http):
    assert _get(f"{fixture_http}/head404", method="HEAD")[0] == 404
    assert _get(f"{fixture_http}/head404")[0] == 200


def test_dead_is_404_both_ways(fixture_http):
    """The negative control: the ladder must still report a real 404."""
    assert _get(f"{fixture_http}/dead", method="HEAD")[0] == 404
    assert _get(f"{fixture_http}/dead")[0] == 404


def test_slow_endpoint_actually_delays(fixture_http):
    start = time.monotonic()
    status, _, headers = _get(f"{fixture_http}/slow.pdf?delay=1.0")
    assert status == 200
    assert headers["Content-Type"] == "application/pdf"
    assert time.monotonic() - start >= 1.0


def test_cyrillic_path_requires_correct_encoding(fixture_http):
    ok = _get(
        f"{fixture_http}/%D0%BF%D1%80%D0%B8%D0%BC%D0%B5%D1%80/%D1%81%D1%82%D1%80%D0%B0%D0%BD%D0%B8%D1%86%D0%B0.pdf"
    )
    assert ok[0] == 200
    assert _get(f"{fixture_http}/%25D0%25BF/nope.pdf")[0] == 404


def test_untrusted_tls_chain_is_rejected_by_stdlib(fixture_https, named_hosts):
    with pytest.raises(urllib.error.URLError) as caught:
        urllib.request.urlopen(f"{fixture_https}/health", timeout=10)
    assert isinstance(caught.value.reason, ssl.SSLError)


def test_untrusted_tls_chain_serves_fine_when_verification_is_relaxed(fixture_https, named_hosts):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(f"{fixture_https}/health", timeout=10, context=ctx) as resp:
        assert resp.status == 200


def test_named_hosts_resolve_to_distinct_loopback_addresses(fixture_port, named_hosts):
    for host in ("alpha.test", "beta.test", "gamma.test"):
        status, body, _ = _get(f"http://{host}:{fixture_port}/hostlog")
        assert status == 200
        assert body.decode() == host


def test_idn_host_reaches_the_server_in_punycode(fixture_port, named_hosts):
    status, _, _ = _get(f"http://{hosts.IDN_HOST_ASCII}:{fixture_port}/health")
    assert status == 200


# -- media and API endpoints ---------------------------------------------


def test_media_requires_the_page_referer(fixture_http, fixture_port):
    ident = "aaaaaaaaaaaaaaaaaaaaaa1"
    assert _get(f"{fixture_http}/media/{ident}?w=1400")[0] == 403
    status, body, _ = _get(
        f"{fixture_http}/media/{ident}?w=1400",
        headers={"Referer": f"http://127.0.0.1:{fixture_port}/lazy-images"},
    )
    assert status == 200
    assert body[:2] == b"\xff\xd8"


def test_media_serves_bigger_bytes_for_the_hi_res_width(fixture_http, fixture_port):
    ident = "aaaaaaaaaaaaaaaaaaaaaa1"
    ref = {"Referer": f"http://127.0.0.1:{fixture_port}/lazy-images"}
    small = _get(f"{fixture_http}/media/{ident}?w=800", headers=ref)[1]
    large = _get(f"{fixture_http}/media/{ident}?w=1400", headers=ref)[1]
    assert len(large) > len(small)


def test_truncated_jpeg_has_no_end_marker_and_the_good_one_does(fixture_http):
    trunc = _get(f"{fixture_http}/media/trunc")[1]
    good = _get(f"{fixture_http}/media/good")[1]
    assert trunc[:2] == b"\xff\xd8" and trunc[-2:] != b"\xff\xd9"
    assert good[:2] == b"\xff\xd8" and good[-2:] == b"\xff\xd9"
    assert len(good) > 10000


def test_same_origin_api_rejects_an_out_of_band_call(fixture_http):
    """Plain urllib gets 403 — the whole reason the in-page fetch exists."""
    status, body, _ = _get(f"{fixture_http}/api/items")
    assert status == 403
    assert b"cleared page" in body


def test_same_origin_api_accepts_the_in_page_shaped_request(fixture_http, fixture_port):
    _, _, hdrs = _get(f"{fixture_http}/challenge/clears-after/1")
    cookie = http.cookies.SimpleCookie(hdrs["Set-Cookie"])
    status, body, _ = _get(
        f"{fixture_http}/api/items",
        headers={
            "Sec-Fetch-Site": "same-origin",
            "Referer": f"http://127.0.0.1:{fixture_port}/lazy",
            "Cookie": f"ck_session={cookie['ck_session'].value}",
        },
    )
    assert status == 200
    assert len(json.loads(body)["items"]) == 5


def test_malformed_api_body_is_served_verbatim(fixture_http):
    status, body, _ = _get(f"{fixture_http}/api/items/malformed")
    assert status == 200
    with pytest.raises(json.JSONDecodeError):
        json.loads(body)


# -- generated media -----------------------------------------------------


def test_generated_flat_sky_is_not_the_decoder_fill_colour():
    """The false-positive control must not sit at exactly 128 with no variance."""
    pytest.importorskip("PIL")
    Image = media._pil()
    import io

    img = Image.open(io.BytesIO(media.flat_gray_jpeg())).convert("RGB")
    width, height = img.size
    band = img.crop((0, int(height * 0.7), width, int(height * 0.7) + 4)).resize((16, 1))
    px = [band.getpixel((x, 0)) for x in range(16)]
    avg = [sum(c) / len(px) for c in zip(*px, strict=True)]
    variance = sum(sum((p[k] - avg[k]) ** 2 for k in range(3)) for p in px) / len(px)
    assert not all(abs(avg[k] - 128) < 4 for k in range(3)), avg
    assert variance > 30, variance
