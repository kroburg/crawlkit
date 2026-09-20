"""Every documented example, actually run.

An example nobody executes rots within a month — the command in its README
drifts from the command that actually works, and nobody notices until a
newcomer copies it and it fails. This file is what stops that: it runs every
`examples/*/run.sh` against the same fixture server the rest of the suite
uses, and asserts both a clean exit and one substring that could only appear
if the example did what it claims.

Examples that need Playwright or a real Chrome self-skip *inside* run.sh
(one line, exit 0) rather than being skipped here — this file stays a real
assertion, not a conditional one. Where that self-skip is a live possibility
in a bare environment, the accepted substrings cover both outcomes.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"

# name -> one substring, or a tuple of substrings any of which is acceptable
# (used where the example legitimately self-skips in a bare environment).
EXPECTED = {
    "01_probe_a_rotting_list": "confirmed by rendering, not re-probed",
    "02_clear_a_wall": ("exit code: 3", "SKIP: playwright not installed"),
    "03_drive_a_harvest": "skipped 3",
    "04_plan_a_fanout": "crawlkit-item: book-1",
    "05_ingest_a_fanout": "OK: exactly 1 record landed",
    "06_recover_a_dead_fanout": "applied: 1",
    "07_qa_a_harvest": "disputed: 1",
    "08_node_warm_profile": '"model": "stub-model"',
}


def example_dirs():
    return sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and (p / "run.sh").exists())


@pytest.mark.parametrize("example", example_dirs(), ids=lambda p: p.name)
def test_example_runs_clean_and_shows_its_point(example, fixture_http):
    if example.name not in EXPECTED:
        pytest.fail(f"{example.name}: no expected substring registered in EXPECTED")

    done = subprocess.run(
        ["bash", "run.sh"],
        cwd=example,
        env={**os.environ, "CRAWLKIT_FIXTURE": fixture_http},
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = done.stdout + done.stderr
    assert done.returncode == 0, f"{example.name} exited {done.returncode}\n{output[-4000:]}"

    expected = EXPECTED[example.name]
    candidates = (expected,) if isinstance(expected, str) else expected
    assert any(needle in output for needle in candidates), (
        f"{example.name}: none of {candidates!r} found in output\n{output[-4000:]}"
    )


def test_every_example_directory_is_registered():
    """A ninth example directory with no run.sh wired up here rots silently."""
    names = {p.name for p in example_dirs()}
    assert names == set(EXPECTED), (names, set(EXPECTED))


def test_run_all_script_exists_and_is_a_script():
    script = EXAMPLES / "run_all.sh"
    assert script.exists()
    assert script.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))
