"""The durable override, pinned four ways.

The scenario being defended: a host that only a real browser can reach is confirmed once, by
hand, at real cost — and then the next automated sweep quietly overwrites that
verdict with a false "broken" and the source is deleted in review.

The last test is the one that matters: the prober is rigged to return 503 for
*anything* it touches, so if the override ever leaks, the assertion fails.
"""

import pytest

from crawlkit import linkstate
from crawlkit.cli import check_links


def state(tmp_path, data):
    return linkstate.LinkState(tmp_path / "state.json", data)


def exploding(url):
    raise AssertionError(f"a confirmed URL must not be probed: {url}")


def test_marker_with_a_live_status_skips_the_network(tmp_path):
    st = state(tmp_path, {"http://walled/a": {"http_status": 200, "verified_via": "fetch_js"}})
    assert st.resolve_status("http://walled/a", exploding) == (200, False)


def test_no_marker_falls_through_to_the_probe(tmp_path):
    """The override is opt-in: a dead record with no marker is re-probed."""
    st = state(tmp_path, {"http://plain/a": {"http_status": -1}})
    assert st.resolve_status("http://plain/a", lambda url: 200) == (200, True)


def test_marker_over_a_dead_status_is_not_trusted(tmp_path):
    """Defensive: the conjunction, not the marker alone, grants the skip."""
    st = state(tmp_path, {"http://walled/a": {"http_status": -1, "verified_via": "fetch_js"}})
    assert st.resolve_status("http://walled/a", lambda url: 404) == (404, True)


@pytest.mark.parametrize("status", [200, 301, 308])
def test_every_live_status_can_be_made_sticky(tmp_path, status):
    st = state(tmp_path, {"http://w/a": {"http_status": status, "verified_via": "fetch_js"}})
    assert st.is_sticky("http://w/a")


def test_a_full_sweep_does_not_downgrade_a_confirmed_url(tmp_path):
    st = state(
        tmp_path,
        {
            "http://walled/a": {"http_status": 200, "verified_via": "fetch_js"},
            "http://plain/b": {"http_status": 200},
        },
    )
    results = check_links.run(
        st,
        ["http://walled/a", "http://plain/b"],
        check=lambda url: 503,
        interval_s=0,
        report=lambda line: None,
    )

    by_url = {url: (status, probed) for url, status, probed in results}
    assert by_url["http://walled/a"] == (200, False)
    assert by_url["http://plain/b"] == (503, True)

    assert st.record("http://walled/a")["http_status"] == 200
    assert st.record("http://walled/a")["verified_via"] == "fetch_js"
    assert st.record("http://plain/b")["http_status"] == 503


def test_a_sweep_refreshes_last_checked_on_sticky_records_too(tmp_path):
    st = state(
        tmp_path,
        {
            "http://walled/a": {
                "http_status": 200,
                "verified_via": "fetch_js",
                "last_checked": "2020-01-01",
            }
        },
    )
    check_links.run(
        st, ["http://walled/a"], check=exploding, interval_s=0, report=lambda line: None
    )
    assert st.record("http://walled/a")["last_checked"] != "2020-01-01"


def test_confirmation_writes_both_halves_at_once(tmp_path):
    st = state(tmp_path, {})
    st.mark_verified_via("http://walled/a", "quota", notes="rendered; probe blocked")
    rec = st.record("http://walled/a")
    assert rec["http_status"] == 200
    assert rec["verified_via"] == "fetch_js"
    assert rec["verdicts"]["quota"]["content_status"] == "ok"
    assert linkstate.schema_errors(st.data) == []


def test_confirmation_preserves_verdicts_for_other_kinds(tmp_path):
    st = state(tmp_path, {})
    st.set_verdict("http://walled/a", "quota", "ok", notes="already good")
    st.mark_verified_via("http://walled/a", "ege")
    verdicts = st.record("http://walled/a")["verdicts"]
    assert verdicts["quota"]["notes"] == "already good"
    assert set(verdicts) == {"quota", "ege"}
