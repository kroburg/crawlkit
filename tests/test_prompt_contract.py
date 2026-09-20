"""The prompt document's guarantees, asserted against the emitted text.

Against the *emitted* prompt, not the document: one assertion then covers the
slicer, the substitution and the document together, so a rule that survives in
the source and is dropped during composition still fails the build.
"""

import json
from pathlib import Path

import pytest

from crawlkit.agents import version
from crawlkit.cli import plan

REPO = Path(__file__).resolve().parents[1]
HARVEST = REPO / "docs" / "prompts" / "harvest.md"
SCHEMA = REPO / "docs" / "prompts" / "schema.md"


@pytest.fixture(scope="module")
def worklist_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("plan") / "items.json"
    path.write_text(
        json.dumps(
            [
                {"id": "item-1", "title": "First", "url": "https://example.invalid/a"},
                {"id": "item-2", "title": "Second", "url": "https://example.invalid/b"},
            ]
        )
    )
    return path


@pytest.fixture(scope="module")
def emitted(tmp_path_factory, worklist_file):
    out = tmp_path_factory.mktemp("prompts")
    code = plan.main(
        [
            "--worklist",
            str(worklist_file),
            "--prompt",
            str(HARVEST),
            "--schema",
            str(SCHEMA),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    return out


DRIFT_GUARDS = [
    "Census, not sample",
    "DO NOT WRITE FILES",
    "verification: <N> of <M>",
    "Excluded:",
    "NEVER cite from prior knowledge",
    "BLOCKED:",
    "Work on this one only",
    "do not paraphrase",
]


@pytest.mark.parametrize("phrase", DRIFT_GUARDS)
def test_the_emitted_prompt_carries_every_drift_guard(emitted, phrase):
    text = (emitted / "item-1.md").read_text(encoding="utf-8")
    assert version.guard_phrases_present(text, [phrase]) == []


def test_the_document_and_the_test_agree_on_the_guard_list():
    """Otherwise the document grows a rule nothing asserts, or the reverse."""
    assert sorted(plan._guard_phrases(HARVEST.read_text(encoding="utf-8"))) == sorted(DRIFT_GUARDS)


def test_the_schema_arrives_verbatim(emitted):
    from crawlkit.agents import prompt as prompt_mod

    block = prompt_mod.lift_block(SCHEMA.read_text(encoding="utf-8"), "Record schema")
    assert block in (emitted / "item-1.md").read_text(encoding="utf-8")


def test_no_placeholder_survives_substitution(emitted):
    for name in ("item-1.md", "item-2.md"):
        text = (emitted / name).read_text(encoding="utf-8")
        assert "{{" not in text and "}}" not in text


def test_each_prompt_is_scoped_to_its_own_item(emitted):
    first = (emitted / "item-1.md").read_text(encoding="utf-8")
    assert "item-1" in first
    assert "item-2" not in first


def test_every_prompt_carries_the_recovery_marker(emitted):
    from crawlkit.agents import emit as emit_mod

    assert emit_mod.parse_marker((emitted / "item-2.md").read_text(encoding="utf-8")) == "item-2"


def test_the_manifest_records_what_produced_this_run(emitted):
    """So a recovery six weeks later can say which contract the agents ran
    against, rather than inferring it from the prompts themselves."""
    manifest = json.loads((emitted / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["prompt_version"] == version.version_of(HARVEST.read_text("utf-8"))[0]
    assert len(manifest["document_sha256"]) == 64
    assert manifest["items"] == ["item-1", "item-2"]
    assert manifest["run"].startswith("harvest-")


def test_the_shipped_prompt_document_documents_how_to_amend_itself():
    text = HARVEST.read_text(encoding="utf-8")
    assert version.check_protocol(text)
    assert version.version_of(text)[0] >= 1


def test_planning_against_an_unversioned_document_is_refused(tmp_path, worklist_file):
    """A fanout has to be able to say which contract it ran against."""
    bad = tmp_path / "nover.md"
    bad.write_text("<!-- BEGIN PROMPT -->\nbody\n<!-- END PROMPT -->\n")
    assert plan.main(["--worklist", str(worklist_file), "--prompt", str(bad)]) == 1


def test_dry_run_lists_the_work_and_emits_nothing(tmp_path, worklist_file, capsys):
    out = tmp_path / "unused"
    assert (
        plan.main(
            [
                "--worklist",
                str(worklist_file),
                "--prompt",
                str(HARVEST),
                "--out",
                str(out),
                "--dry-run",
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert "item-1" in printed
    assert "DO NOT WRITE FILES" not in printed
    assert not out.exists()


def test_finished_work_is_skipped(tmp_path, worklist_file):
    done = tmp_path / "done.json"
    done.write_text(json.dumps({"item-1": "ok"}))
    out = tmp_path / "prompts"
    assert (
        plan.main(
            [
                "--worklist",
                str(worklist_file),
                "--prompt",
                str(HARVEST),
                "--schema",
                str(SCHEMA),
                "--done",
                str(done),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert not (out / "item-1.md").exists()
    assert (out / "item-2.md").exists()
