"""Safe ingest: the whitelist, the buckets, and the census gate.

The test that matters most is the first one. It reproduces a real incident: a
harvester that sorted reply files by modification time and let the newest win
silently overwrote hand-curated records when unrelated agents from an earlier
run finished late.
"""

import json

import pytest

from crawlkit.agents import census_gate, fenced, ingest
from crawlkit.agents.worklist import Worklist


def reply(records, item_id="item-1", header=None):
    body = json.dumps({"item_id": item_id, "records": records})
    head = f"{header}\n\n" if header else ""
    return f"{head}Here you go.\n\n```json\n{body}\n```\n"


def result(agent_id, text, item_id=None):
    return ingest.Result(agent_id=agent_id, text=text, item_id=item_id)


# -- authorization --------------------------------------------------------


def test_a_stale_agent_outside_the_whitelist_cannot_overwrite_a_curated_record(tmp_path):
    """The incident, reproduced: the unauthorized reply is newer and richer,
    and must still be ignored. Time is not evidence of authority."""
    import os
    import time

    good = tmp_path / "a111.json"
    good.write_text(reply([{"id": 1, "title": "curated"}]))
    stale = tmp_path / "b999.json"
    stale.write_text(reply([{"id": 1, "title": "stale but bigger"}, {"id": 2}]))

    # Make the unauthorized file unambiguously newer.
    later = time.time() + 60
    os.utime(stale, (later, later))

    report = ingest.ingest(ingest.read_results(tmp_path), ["a111"])

    assert report.counts["unauthorized"] == 1
    assert len(report.applied) == 1
    assert report.applied["item-1"]["records"][0]["title"] == "curated"


def test_an_empty_whitelist_is_an_error_not_permission():
    """There must be no spelling of this call that means 'take everything'."""
    with pytest.raises(ValueError):
        ingest.ingest([result("a", reply([{"id": 1}]))], [])
    with pytest.raises(ValueError):
        ingest.ingest([result("a", reply([{"id": 1}]))], None)


def test_a_truncated_id_still_authorizes():
    """Ids get truncated when a human copies them; this is the one softness."""
    allowed, rejected = ingest.authorize([result("a316a9a917c156157", "x")], ["a316"])
    assert len(allowed) == 1 and not rejected


# -- the rejection buckets ------------------------------------------------


def test_a_reply_with_no_fenced_block_is_counted_not_raised():
    report = ingest.ingest([result("a", "I could not do this.")], ["a"])
    assert report.counts["no-block"] == 1
    assert report.applied == {}


def test_malformed_json_is_counted():
    text = '```json\n{"item_id": "x", "records": [}\n```'
    report = ingest.ingest([result("a", text)], ["a"])
    assert report.counts["unparseable"] == 1


def test_a_well_formed_empty_result_cannot_blank_an_existing_record():
    """A dead agent succeeding at nothing must not be mistaken for data."""
    report = ingest.ingest([result("a", reply([]))], ["a"])
    assert report.counts["empty-result"] == 1
    assert report.applied == {}


def test_a_key_outside_the_known_set_is_rejected_not_guessed():
    report = ingest.ingest(
        [result("a", reply([{"id": 1}], item_id="who-is-this"))],
        ["a"],
        keymap={"item-1": "item-1"},
    )
    assert report.counts["unknown-key"] == 1


def test_an_unexpected_schema_key_is_rejected():
    text = '```json\n{"item_id": "item-1", "records": [1], "surprise": true}\n```'
    report = ingest.ingest([result("a", text)], ["a"], schema_keys={"item_id", "records"})
    assert report.counts["unknown-key"] == 1


def test_a_clean_run_reports_ok():
    report = ingest.ingest([result("a", reply([{"id": 1}]))], ["a"])
    assert report.ok()
    assert report.counts == dict.fromkeys(ingest.BUCKETS, 0)


# -- normalization is last ------------------------------------------------


def test_a_known_spelling_is_folded_and_a_drop_is_a_drop():
    record, changed = ingest.normalize(
        {"status": "OK", "junk": "n/a"}, {"status": {"OK": "ok"}, "junk": {"n/a": None}}
    )
    assert record == {"status": "ok"}
    assert len(changed) == 2


def test_an_unknown_value_passes_through_to_the_schema_gate():
    """Coercing it here would hide the drift the gate exists to catch."""
    record, _ = ingest.normalize({"status": "weird"}, {"status": {"OK": "ok"}})
    assert record["status"] == "weird"


# -- block selection ------------------------------------------------------


def test_the_marked_block_wins_over_a_larger_unmarked_one():
    text = (
        "```json\n" + json.dumps({"quoted": "x" * 500}) + "\n```\n"
        '```json\n{"item_id": "item-1", "marker-here": 1}\n```\n'
    )
    block = fenced.select(text, marker="marker-here")
    assert "marker-here" in block.body


def test_a_short_illustrative_fence_does_not_win_over_the_payload():
    text = "```json\n{}\n```\n" + "```json\n" + json.dumps({"records": [1, 2, 3]}) + "\n```"
    assert "records" in fenced.select(text).body


def test_the_self_report_header_the_prompt_asks_for_is_the_one_the_parser_reads():
    """Prompt shape and parser shape, pinned together. Otherwise the header is
    reworded once and the denominator quietly stops being read."""
    from crawlkit.agents import sections

    shape = sections.self_report_header("the source", "today")
    assert "<N> of <M>" in shape

    emitted = "// verification: 8 of 53 records from the source, 2026-01-01. Excluded: a, b."
    assert fenced.parse_self_report(emitted) == {"n": 8, "m": 53, "excluded": ["a", "b"]}


def test_an_explicit_none_is_not_an_exclusion_list():
    parsed = fenced.parse_self_report("verification: 3 of 3 from x, y. Excluded: none.")
    assert parsed["excluded"] == []


# -- the census gate ------------------------------------------------------


def test_both_directions_are_reported():
    work = Worklist([{"id": "a"}, {"id": "b"}, {"id": "c"}])
    census = census_gate.compare(work, {"a": {}, "z": {}})
    assert census.missing == ["b", "c"]
    assert census.extra == ["z"]
    assert not census.ok()


def test_an_invented_id_never_reaches_the_output_file(tmp_path):
    """The gate is the write path, not a warning printed beside it."""
    work = Worklist([{"id": "a"}])
    report = ingest.IngestReport(applied={"a": {"ok": 1}, "invented": {"ok": 2}})
    out = tmp_path / "records.json"
    ingest.apply(report, out, worklist=work)
    assert json.loads(out.read_text()) == {"a": {"ok": 1}}


def test_the_census_sentence_and_the_gate_share_one_denominator():
    """The 8-of-53 shipment, as an executable test: the prompt says 53 because
    the work-list holds 53, and the gate counts against that same object."""
    from crawlkit.agents import sections

    work = Worklist([{"id": f"item-{n}"} for n in range(53)], label="records")
    assert "53 records" in sections.census_rule(work, "the source lists it")

    produced = {f"item-{n}": {} for n in range(8)}
    census = census_gate.compare(work, produced)
    assert len(census.missing) == 45
    assert "45 missing" in census.render()


def test_the_never_dispatched_class_is_counted_apart_from_the_missing_one():
    """'Everything we dispatched came back' must not read as 'we covered
    everything' — the items with no source were never sent at all."""
    work = Worklist([{"id": "a"}])
    census = census_gate.compare(work, {"a": {}}, universe=[{"id": "a"}, {"id": "no-source"}])
    assert census.ok()
    assert census.invisible == ["no-source"]
    assert "1 never dispatched" in census.render()


def test_the_census_persists_for_review(tmp_path):
    work = Worklist([{"id": "a"}, {"id": "b"}])
    census = census_gate.compare(work, {"a": {}})
    path = census_gate.persist(census, tmp_path / "census.json")
    assert json.loads(path.read_text())["missing"] == ["b"]
