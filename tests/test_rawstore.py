"""Raw-first: the expensive artifact survives a cheap mistake."""

import json

import pytest

from crawlkit import rawstore


def test_raw_is_written_even_when_the_parser_explodes(tmp_path):
    def broken(_html):
        raise ValueError("parser bug")

    with pytest.raises(ValueError):
        rawstore.harvest(tmp_path, "page1", "<html>expensive</html>", broken)

    assert rawstore.read_raw(tmp_path, "page1") == "<html>expensive</html>"
    assert not rawstore.sentinel_ok(tmp_path, "page1"), "a crashed parse is not a finished item"


def test_reparse_needs_no_network_and_fixes_the_record(tmp_path):
    rawstore.harvest(
        tmp_path,
        "page1",
        "<h1>Title</h1>",
        lambda html: {"title": None},
        meta={"url": "http://h/p"},
    )
    assert rawstore.read_parsed(tmp_path, "page1")["title"] is None

    fixed = rawstore.reparse(
        tmp_path, "page1", lambda html: {"title": html.split("<h1>")[1].split("<")[0]}
    )
    assert fixed["title"] == "Title"
    assert fixed["url"] == "http://h/p", "provenance the parser does not produce is carried forward"


def test_sentinel_is_the_parsed_file_not_the_raw_one(tmp_path):
    rawstore.write_raw(tmp_path, "page1", "<html></html>")
    assert not rawstore.sentinel_ok(tmp_path, "page1")
    rawstore.write_parsed(tmp_path, "page1", {"ok": True})
    assert rawstore.sentinel_ok(tmp_path, "page1")


def test_zero_byte_sentinel_counts_as_unfinished(tmp_path):
    rawstore.sentinel_path(tmp_path, "page1").parent.mkdir(parents=True, exist_ok=True)
    rawstore.sentinel_path(tmp_path, "page1").write_text("")
    assert not rawstore.sentinel_ok(tmp_path, "page1")


def test_pending_lists_only_unfinished_items(tmp_path):
    rawstore.harvest(tmp_path, "a", "x", lambda html: {"ok": 1})
    assert rawstore.pending(tmp_path, ["a", "b", "c"]) == ["b", "c"]


def test_parsed_file_is_sorted_and_utf8_readable(tmp_path):
    rawstore.write_parsed(tmp_path, "p", {"b": 1, "a": "тест"})
    text = rawstore.sentinel_path(tmp_path, "p").read_text(encoding="utf-8")
    assert text.index('"a"') < text.index('"b"')
    assert "тест" in text
    assert json.loads(text)["a"] == "тест"
