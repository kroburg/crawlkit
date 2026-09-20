"""Every advertised command must exist and start.

`pip install .` happily installs a console script whose target module does not
exist; the failure surfaces the first time a user runs it, as a traceback. Four
of the seven commands here were in that state, so this reads the entry points
out of the packaging metadata and proves each one imports and responds to
--help.
"""

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def entry_points():
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return sorted(config["project"]["scripts"].items())


@pytest.mark.parametrize("name,target", entry_points())
def test_the_target_of_every_console_script_exists(name, target):
    module_name, _, attribute = target.partition(":")
    module = importlib.import_module(module_name)
    assert callable(getattr(module, attribute, None)), f"{name} -> {target} is not callable"


@pytest.mark.parametrize("name,target", entry_points())
def test_every_console_script_answers_help(name, target):
    """In a subprocess: --help must exit 0 without touching the network or the
    filesystem, which is also the cheapest possible smoke test of the imports."""
    module_name, _, _ = target.partition(":")
    done = subprocess.run(
        [sys.executable, "-m", module_name, "--help"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, f"{name}: {done.stderr[:400]}"
    assert done.stdout.strip(), f"{name} printed no help"


def test_the_advertised_commands_are_the_ones_that_exist():
    """A command removed from the package but left in pyproject is the same
    broken promise as one that was never written."""
    declared = {name for name, _ in entry_points()}
    modules = {
        path.stem
        for path in (REPO / "crawlkit" / "cli").glob("*.py")
        if not path.stem.startswith("_")
    }
    expected = {f"ck-{stem.replace('check_links', 'probe')}" for stem in modules}
    assert declared == expected, f"declared {sorted(declared)} but found {sorted(expected)}"
