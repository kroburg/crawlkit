"""Store shape and writer discipline."""

import json

from crawlkit import linkstate


def state(tmp_path, data=None):
    return linkstate.LinkState(tmp_path / "state.json", data if data is not None else {})


def test_prober_writes_only_its_own_fields(tmp_path):
    st = state(tmp_path)
    st.set_verdict("http://h/a", "cutoff", "ok", notes="checked by hand", when="2026-01-01")
    st.set_http("http://h/a", 200, when="2026-02-02")
    rec = st.record("http://h/a")
    assert rec["verdicts"]["cutoff"] == {
        "content_status": "ok",
        "semantic_verified_at": "2026-01-01",
        "notes": "checked by hand",
    }
    assert rec["last_checked"] == "2026-02-02"


def test_verifier_writes_only_its_own_fields(tmp_path):
    st = state(tmp_path)
    st.set_http("http://h/a", 404, when="2026-02-02")
    st.set_verdict("http://h/a", "quota", "wrong_topic", when="2026-03-03")
    rec = st.record("http://h/a")
    assert rec["http_status"] == 404 and rec["last_checked"] == "2026-02-02"


def test_a_second_verdict_kind_leaves_the_first_alone(tmp_path):
    st = state(tmp_path)
    st.set_verdict("http://h/a", "quota", "ok")
    st.set_verdict("http://h/a", "ege", "wrong_topic")
    assert set(st.record("http://h/a")["verdicts"]) == {"quota", "ege"}


def test_saved_file_is_sorted_and_indented_for_review(tmp_path):
    st = state(tmp_path)
    st.set_http("http://h/b", 200)
    st.set_http("http://h/a", 200)
    st.save()
    text = st.path.read_text(encoding="utf-8")
    assert text.index('"http://h/a"') < text.index('"http://h/b"')
    assert "\n  " in text and text.endswith("\n")
    assert json.loads(text)


def test_non_ascii_is_stored_readable_not_escaped(tmp_path):
    st = state(tmp_path)
    st.set_verdict("http://h/a", "quota", "ok", notes="страница верная")
    st.save()
    assert "страница верная" in st.path.read_text(encoding="utf-8")


def test_roundtrip_through_disk(tmp_path):
    st = state(tmp_path)
    st.mark_verified_via("http://h/a", "home", notes="rendered fine")
    st.save()
    assert linkstate.LinkState(st.path).is_sticky("http://h/a")


# -- closed-world schema -------------------------------------------------


def test_clean_store_has_no_schema_errors(tmp_path):
    st = state(tmp_path)
    st.set_http("http://h/a", 200)
    st.set_verdict("http://h/a", "quota", "ok")
    st.mark_verified_via("http://h/b", "home")
    assert linkstate.schema_errors(st.data) == []


def test_unknown_top_level_key_is_an_error():
    problems = linkstate.schema_errors({"http://h/a": {"http_status": 200, "content_status": "ok"}})
    assert any("unknown top-level keys" in p for p in problems)


def test_unknown_verdict_key_is_an_error():
    data = {"http://h/a": {"verdicts": {"quota": {"content_status": "ok", "note": "typo"}}}}
    assert any("unknown verdict keys" in p for p in linkstate.schema_errors(data))


def test_unknown_content_status_is_an_error():
    data = {"http://h/a": {"verdicts": {"quota": {"content_status": "probably_fine"}}}}
    assert any("unknown content_status" in p for p in linkstate.schema_errors(data))


def test_unknown_marker_is_an_error():
    data = {"http://h/a": {"http_status": 200, "verified_via": "vibes"}}
    assert any("unknown verified_via" in p for p in linkstate.schema_errors(data))
