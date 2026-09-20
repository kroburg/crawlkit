"""The state store against a real-shaped file, committed and sanitized.

A schema is only worth having if it survives contact with what the world
actually produces. This sample is derived from a link-state file that recorded
what ~1500 URLs did to a probe over several months: the status distribution,
the verdict classes and the sticky records are real, while hosts, paths and
note text are replaced. What remains is the shape, which is the part the schema
has to tolerate.

It is committed, so it runs everywhere. `tests/test_corpus_opt_in.py` is the
same assertions against a full local corpus, for anyone who has one.
"""

import json
from pathlib import Path

import pytest

from crawlkit import contract, linkstate

SAMPLE = Path(__file__).parent / "data" / "link_state_sample.json"


@pytest.fixture(scope="module")
def recorded():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_the_closed_world_schema_accepts_a_real_shaped_file(recorded):
    assert len(recorded) > 20
    assert linkstate.schema_errors(recorded) == []


def test_the_sample_exercises_every_failure_class_the_vocabulary_models(recorded):
    """If reality produces a class the vocabulary lacks, the vocabulary is a
    tidier fiction than the thing it describes."""
    seen = {
        verdict["content_status"]
        for record in recorded.values()
        for verdict in (record.get("verdicts") or {}).values()
    }
    assert {"js_only", "wrong_topic", "unverifiable", "scanned_pdf"} <= seen
    assert seen <= set(contract.vocabulary("content_status"))


def test_every_browser_confirmed_record_is_recognised_as_sticky(recorded):
    """These are the records that cost a human a browser session; a sweep must
    not quietly overwrite them."""
    state = linkstate.LinkState(SAMPLE, recorded)
    marked = [url for url, record in recorded.items() if record.get("verified_via")]
    assert marked, "sample should contain browser-confirmed records"
    assert all(state.is_sticky(url) for url in marked)


def test_real_traffic_produces_statuses_outside_the_live_set(recorded):
    """A real corpus contains 202, 403, 405, 502 — statuses that are neither
    success nor a clean failure, and that a naive checker guesses about."""
    statuses = {record["http_status"] for record in recorded.values()}
    odd = statuses - set(contract.LIVE_HTTP) - {404, -1}
    assert odd, f"expected unusual statuses, saw {sorted(statuses)}"
    assert not (odd & contract.LIVE_HTTP)


def test_a_months_old_link_file_has_rotted(recorded):
    """The argument for keeping the probe cheap and repeatable: a past sweep is
    not a settled result. Links die after you record them as live."""
    dead = [url for url, record in recorded.items() if record["http_status"] == 404]
    assert dead


def test_the_sample_carries_no_real_host(recorded):
    """The sanitization is part of the fixture's contract, not a one-off."""
    for url in recorded:
        assert ".example.invalid/" in url, url
