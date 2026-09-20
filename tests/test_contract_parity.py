"""The two runtimes must see byte-identical constants.

This is the test that makes a single shared constants file worth more than a
convention. Copy a literal into seven files and it drifts to two different
values; nothing fails, because nothing compares them.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from crawlkit import contract, ua
from crawlkit.exits import Exit

REPO = Path(__file__).resolve().parents[1]

node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_python_reads_the_packaged_file():
    assert contract.PATH.is_file()
    assert contract.all()["user_agents"]["desktop_chrome"]


@node
def test_node_and_python_see_the_same_object():
    out = subprocess.run(
        [
            "node",
            "-e",
            "process.stdout.write(JSON.stringify(require('./node/lib/contract.js').all()))",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(out.stdout) == contract.all()


@node
def test_node_resolves_the_python_packages_file_not_a_copy():
    out = subprocess.run(
        ["node", "-e", "process.stdout.write(require('./node/lib/contract.js').PATH)"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(out.stdout).resolve() == contract.PATH.resolve()


def test_dotted_get_raises_on_typo():
    with pytest.raises(KeyError):
        contract.get("http.timeout_seconds")
    assert contract.get("http.timeout_seconds", 0) == 0


def test_user_agent_carries_no_headless_token():
    assert not ua.has_headless_token(ua.ua())
    with pytest.raises(ValueError):
        ua.assert_no_headless_token("Mozilla/5.0 HeadlessChrome/148.0.0.0")


def test_offered_values_are_a_subset_of_accepted_values():
    """The relation that keeps a prompt's enum from skewing off the ingest enum."""
    for name in ("content_status", "coverage_status", "verify_verdict", "repair_action"):
        accepted = contract.vocabulary(name)
        offered = contract.offered_values(name)
        assert offered, f"{name} offers nothing to an agent"
        assert set(offered) <= set(accepted)
        assert all(v["gloss"].strip() for v in accepted.values()), f"{name} has a gloss-less value"


def test_derived_statuses_are_never_offered_to_an_agent():
    """An agent may not report a verdict the script is supposed to derive."""
    derived = contract.derived_values("coverage_status")
    assert set(derived) == {"manual", "undercoverage"}


def test_exit_codes_are_distinct_integers():
    values = [int(e) for e in Exit]
    assert values == sorted(set(values))
    assert int(Exit.CHALLENGE_NOT_CLEARED) == 3
