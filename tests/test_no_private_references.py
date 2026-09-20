"""Nothing in this repository points at a private tree.

This code was extracted from two unpublished projects, and extraction leaves
residue: absolute paths from the author's machine, an email address, and
comments that compare the code against "the original" — a codebase no reader
can see, which makes the comment useless to everyone except the person who
wrote it.

A checklist does not survive contact with a year of edits. This does: it walks
every tracked file and fails the build, naming file and line.

The rule for comments, when one trips this: **replace the provenance clause
with the mechanism clause.** A comment may describe a wrong implementation; it
may not describe it as something someone once did. "Ported from X" becomes "the
obvious implementation is X, it fails because Y", or it is deleted, because the
test name already carries the meaning.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# This file necessarily contains every pattern it forbids.
ALLOWLIST = {"tests/test_no_private_references.py"}

BINARY_SUFFIXES = {".jpg", ".png", ".pdf", ".ico", ".gz", ".woff", ".woff2"}

FORBIDDEN = [
    (re.compile(r"/home/[a-z]", re.I), "an absolute path from a developer machine"),
    # Not preceded by ":" or "/" — otherwise a URL userinfo vector (u:p@host)
    # reads as an address.
    (re.compile(r"(?<![:/\w])[\w.+-]+@[\w-]+\.[\w.]+"), "an email address"),
    # Narrow on purpose. "keep the original claim" is domain language; what is
    # forbidden is provenance — a comparison to code the reader cannot see.
    (
        re.compile(
            r"\bin the original\b|\bthe original's\b|\bthe originals\b|"
            r"\bthe original (code|codebase|script|scripts|implementation|tooling|"
            r"project|renderer|checker|harvester|parser|module|version)\b",
            re.I,
        ),
        "a comparison to an unpublished codebase",
    ),
    (re.compile(r"\bsource projects?\b", re.I), "a reference to the unpublished sources"),
    (re.compile(r"\bour own archive\b", re.I), "a reference to private data"),
    (re.compile(r"\bthis machine\b", re.I), "a reference to the author's machine"),
    (re.compile(r"\bported (from|the)\b", re.I), "provenance where a mechanism belongs"),
]


# Project and target names to forbid, supplied from outside the repository.
#
# They are deliberately not written here. A guard that hardcodes the names it
# suppresses publishes them on its first commit, which is precisely the
# disclosure it exists to prevent — and naming a crawl target also dates the
# code, since it says which site was being worked around.
#
#     CRAWLKIT_FORBIDDEN_NAMES=one,two pytest -q
#
# CI supplies this from a secret; locally a gitignored .forbidden-names file
# works. With neither, the generic patterns above still run.
def extra_names():
    from_env = os.environ.get("CRAWLKIT_FORBIDDEN_NAMES", "")
    local = REPO / ".forbidden-names"
    if not from_env and local.is_file():
        from_env = local.read_text(encoding="utf-8").replace("\n", ",")
    return [part.strip() for part in from_env.split(",") if part.strip()]


for _name in extra_names():
    FORBIDDEN.append((re.compile(re.escape(_name), re.I), "names a project or target"))


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True)
    for line in out.stdout.splitlines():
        if line in ALLOWLIST or Path(line).suffix in BINARY_SUFFIXES:
            continue
        yield line


def findings():
    hits = []
    for relative in tracked_files():
        path = REPO / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for pattern, why in FORBIDDEN:
                if pattern.search(line):
                    hits.append(f"{relative}:{number}: {why}\n    {line.strip()[:120]}")
    return hits


def test_no_private_references_in_tracked_files():
    hits = findings()
    assert not hits, "private references found:\n" + "\n".join(hits)


def test_git_history_carries_no_private_paths():
    """HEAD being clean is not enough — a path deleted today is still in the
    commit that added it, and a published repository ships every commit."""
    # The publishable branch only. The working history is kept locally and is
    # deliberately not what gets pushed.
    out = subprocess.run(
        ["git", "log", "-p", "main"], cwd=REPO, capture_output=True, text=True, check=True
    )
    leaked = sorted(set(re.findall(r"/home/[a-z][\w./-]*", out.stdout, re.I)))
    if leaked:
        pytest.fail(
            "the history contains developer paths, which no edit to HEAD removes:\n  "
            + "\n  ".join(leaked[:10])
            + "\nNo edit to HEAD clears this; the publishable history has to be rooted."
        )
