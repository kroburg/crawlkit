"""Emission framing, the recovery marker, and work-list selection.

The marker is the quiet load-bearing piece. Recovering a dead fanout means
answering "which item was this agent working on", and the alternative to a
machine-readable token is regexing the interpolated id back out of the prompt
prose — which works until somebody rewords the prompt.
"""

from crawlkit.agents import emit, version, worklist
from crawlkit.agents.worklist import Worklist


def test_every_emitted_prompt_carries_a_machine_readable_identity():
    block = emit.block("do the thing", "item-42", run="run-1")
    assert emit.parse_marker(block) == "item-42"


def test_the_marker_survives_being_quoted_inside_a_transcript():
    """Recovery reads this out of an agent's own transcript, where the prompt
    is embedded in JSON among unrelated text."""
    transcript = 'blah {"content": "' + emit.block("p", "item-7").replace('"', '\\"') + '"} blah'
    assert emit.parse_marker(transcript) == "item-7"


def test_text_without_a_marker_yields_nothing_rather_than_a_guess():
    assert emit.parse_marker("an ordinary prompt about item-7") is None
    assert emit.parse_marker("") is None


def test_a_group_qualified_marker_round_trips():
    block = emit.block("p", "item-7", group="batch-3")
    assert emit.parse_marker(block) == "batch-3/item-7"


def test_each_block_is_visually_separable_for_copy_paste():
    text = emit.emit([("a", "prompt a"), ("b", "prompt b")], run="r")
    assert text.count("=" * 10) >= 4
    assert "prompt a" in text and "prompt b" in text


def test_a_run_id_is_stable_within_a_minute_and_distinct_across_labels():
    import datetime

    when = datetime.datetime(2026, 1, 2, 3, 4)
    assert emit.run_id("harvest", when) == emit.run_id("harvest", when)
    assert emit.run_id("harvest", when) != emit.run_id("verify", when)


def test_dry_run_lists_the_work_without_emitting_any_prompt():
    items = Worklist([{"id": "a", "url": "http://h/a"}, {"id": "b", "url": "http://h/b"}])
    listing = emit.dry_run(items)
    assert "a" in listing and "b" in listing
    assert "2 items" in listing


# -- selection ------------------------------------------------------------


def test_only_finished_work_is_skipped():
    """Anything that failed or could not be measured is re-planned. Skipping
    those would turn one bad run into a permanent blind spot."""
    items = [{"id": name} for name in ("done", "failed", "manual", "fresh")]
    done = {"done": "ok", "failed": "undercoverage", "manual": "manual"}
    remaining = worklist.select(items, done).ids()
    assert remaining == ["failed", "manual", "fresh"]


def test_reverify_takes_everything_back():
    items = [{"id": "done"}]
    assert worklist.select(items, {"done": "ok"}, reverify=True).ids() == ["done"]


def test_a_boolean_done_map_is_understood_too():
    items = [{"id": "a"}, {"id": "b"}]
    assert worklist.select(items, {"a": True}).ids() == ["b"]


def test_the_key_set_is_the_denominator_the_census_gate_uses():
    items = Worklist([{"id": "a"}, {"id": "b"}])
    assert items.key_set() == {"a", "b"}
    assert items.get("a") == {"id": "a"}
    assert items.get("nope") is None


def test_batches_cover_every_item_exactly_once():
    items = Worklist([{"id": str(n)} for n in range(10)])
    batches = items.batches(4)
    assert [len(b) for b in batches] == [4, 4, 2]
    flat = [item["id"] for batch in batches for item in batch]
    assert flat == items.ids()


def test_loading_rejects_an_entry_with_no_key(tmp_path):
    import json

    import pytest

    path = tmp_path / "w.json"
    path.write_text(json.dumps([{"url": "http://h/a"}]))
    with pytest.raises(ValueError):
        Worklist.load(path)


# -- the prompt document's own version -----------------------------------

VERSIONED = """# Harvest prompt

**Prompt version: 3 (2026-01-15).**

<!-- BEGIN PROMPT -->
body
<!-- END PROMPT -->

## Drift guard

- phrases asserted against the emitted prompt

## Provenance

- every rule traces to a source
"""


def test_a_prompt_document_states_its_version():
    assert version.version_of(VERSIONED) == (3, "2026-01-15")


def test_an_unversioned_document_is_rejected():
    """A prompt is an interface. Changing it invalidates in-flight agent
    output, so a fanout must be able to say which contract it ran against."""
    import pytest

    with pytest.raises(version.VersionError):
        version.version_of("# Harvest prompt\n\nbody")


def test_a_document_must_document_how_to_amend_it():
    import pytest

    assert version.check_protocol(VERSIONED)
    with pytest.raises(version.VersionError):
        version.check_protocol("**Prompt version: 1 (2026-01-01).**\n")


def test_missing_drift_guards_are_reported_against_the_emitted_text():
    """Asserted against what was emitted, not against the document: a guard
    that exists in the source and is dropped by composition is still gone."""
    assert version.guard_phrases_present("a b c", ["a", "c"]) == []
    assert version.guard_phrases_present("a b c", ["a", "zzz"]) == ["zzz"]


def test_a_guard_survives_the_paragraph_being_rewrapped():
    """A drift guard is a claim about what the prompt says, not about where its
    line breaks fall. Matching literally means reflowing a paragraph silently
    deletes a guarantee, which is the opposite of what the guard is for."""
    emitted = "NEVER cite from\nprior knowledge — only what you fetched."
    assert version.guard_phrases_present(emitted, ["NEVER cite from prior knowledge"]) == []
