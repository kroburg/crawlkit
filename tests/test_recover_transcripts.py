"""Recovering a fanout that died before anyone collected it.

Against committed miniature fixtures, never against a real session directory —
a test that reads the developer's own machine passes for reasons nobody else
can reproduce.
"""

from pathlib import Path

from crawlkit.agents import ingest, recover

ROOT = Path(__file__).parent / "data" / "transcripts"
SUBAGENTS = ROOT / "example-project" / "session-1" / "subagents"


def load(name):
    return recover.load(SUBAGENTS / name)


def test_identity_comes_from_the_emitted_marker_not_the_sidecar_prose():
    """The sidecar here deliberately describes something else. Reading prose
    works until somebody rewords a prompt; the marker is written for machines."""
    found = load("agent-a1111111.jsonl")
    assert found.target == "item-1"
    assert found.identified_by == "marker"
    assert found.meta["description"] != "item-1"


def test_a_finished_agent_yields_its_final_answer():
    found = load("agent-a1111111.jsonl")
    assert found.complete
    assert found.reason == "ok"
    assert "Recovered" in found.text


def test_an_agent_that_died_mid_tool_call_is_not_offered_as_a_result():
    """Its last words are a fragment. Importing them would look like an answer
    and contain none."""
    found = load("agent-b2222222.jsonl")
    assert not found.complete
    assert found.reason == "incomplete"
    assert recover.to_results([found]) == []


def test_a_crash_sentinel_sidecar_without_a_description_is_tolerated():
    """One sidecar variant carries only {agentType, stoppedByUser}. Recovery
    runs precisely when things went wrong, so it cannot assume tidy inputs."""
    found = load("agent-c3333333.jsonl")
    assert found.target is None
    assert found.identified_by is None
    assert found.reason == "stopped-by-user"


def test_a_torn_final_line_costs_that_line_and_nothing_else():
    """These files are appended live, so the last line of an interrupted one is
    routinely half-written."""
    found = load("agent-c3333333.jsonl")
    assert found.reason != "unreadable"


def test_the_agent_id_comes_from_the_record_not_only_the_filename():
    assert load("agent-a1111111.jsonl").agent_id == "a1111111"


def test_recovery_walks_a_tree_and_reports_what_it_could_not_use():
    found = recover.recover(ROOT)
    assert len(found) == 3
    summary = recover.summarize(found)
    assert summary["recoverable"] == 1
    assert summary["by_reason"]["incomplete"] == 1
    assert summary["by_reason"]["stopped-by-user"] == 1
    assert summary["identified_by"]["marker"] == 2


def test_recovery_can_be_narrowed_to_named_agents():
    assert len(recover.recover(ROOT, agent_ids=["a111"])) == 1


def test_recovered_work_still_has_to_pass_the_whitelist():
    """Recovery finds; ingest authorizes. Otherwise 'recover the dead agents'
    is a route around the guard that stops stale replies landing."""
    results = recover.to_results(recover.recover(ROOT))
    assert [r.item_id for r in results] == ["item-1"]

    blocked = ingest.ingest(results, ["someone-else"])
    assert blocked.counts["unauthorized"] == 1
    assert blocked.applied == {}

    allowed = ingest.ingest(results, ["a1111111"])
    assert allowed.applied["item-1"]["records"][0]["title"] == "Recovered"


def test_an_absent_root_is_empty_rather_than_an_error(tmp_path):
    assert recover.recover(tmp_path / "nothing-here") == []


def test_the_recovered_directory_chains_into_ingest_as_documented(tmp_path):
    """The printed next step must actually work.

    Recovery names files after the item; ingest authorizes by agent. Without the
    index that travels between them, the documented chain fails authorization —
    which looks like a permissions problem and is really a naming one.
    """
    from crawlkit.cli import recover as recover_cli

    out = tmp_path / "recovered"
    assert recover_cli.main(["--root", str(ROOT), "--out", str(out), "--quiet"]) == 0

    results = ingest.read_results(out, suffix=".txt")
    assert [r.agent_id for r in results] == ["a1111111"]
    assert [r.item_id for r in results] == ["item-1"]

    report = ingest.ingest(results, ["a1111111"])
    assert report.applied["item-1"]["records"][0]["title"] == "Recovered"
