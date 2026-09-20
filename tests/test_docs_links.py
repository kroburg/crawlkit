"""Documentation that points at things which exist.

Every chapter ends by naming the tests that pin it, and the README links the
chapters. Both rot: a test gets renamed, a chapter gets moved, and the doc keeps
claiming a guarantee nobody can find. Since the whole premise here is that each
concept has a test behind it, a dangling citation is not a typo — it is the
premise failing quietly.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

MARKDOWN = sorted(DOCS.glob("*.md")) + [REPO / "README.md"]
TEST_PATH = re.compile(r"`(tests/[\w/]+\.py)(?:::(\w+))?`")
NODE_PATH = re.compile(r"`(node/test/[\w.]+\.js)`")
RELATIVE_LINK = re.compile(r"\[[^\]]+\]\((?!https?://)([^)#]+)(?:#[^)]*)?\)")


@pytest.fixture(scope="module")
def collected():
    """Every test id pytest can actually see."""
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "not corpus"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    ids = set()
    files = set()
    for line in done.stdout.splitlines():
        if "::" not in line:
            continue
        path, _, rest = line.partition("::")
        files.add(path)
        ids.add(f"{path}::{rest.split('[')[0]}")
    assert files, done.stdout[-2000:]
    return files, ids


@pytest.mark.parametrize("document", MARKDOWN, ids=lambda p: p.name)
def test_every_cited_test_exists(document, collected):
    files, ids = collected
    missing = []
    for path, name in TEST_PATH.findall(document.read_text(encoding="utf-8")):
        if not (REPO / path).is_file():
            missing.append(path)
        elif name and path in files and f"{path}::{name}" not in ids:
            # Only check the function when the module was collected here. A
            # file skipped for a missing optional dependency is still a valid
            # citation — otherwise the docs would fail on a bare install.
            missing.append(f"{path}::{name}")
    assert not missing, f"{document.name} cites tests that do not exist: {missing}"


@pytest.mark.parametrize("document", MARKDOWN, ids=lambda p: p.name)
def test_every_cited_node_test_file_exists(document):
    missing = [
        path
        for path in NODE_PATH.findall(document.read_text(encoding="utf-8"))
        if not (REPO / path).is_file()
    ]
    assert not missing, f"{document.name} cites missing node tests: {missing}"


@pytest.mark.parametrize("document", MARKDOWN, ids=lambda p: p.name)
def test_every_relative_link_resolves(document):
    broken = []
    for target in RELATIVE_LINK.findall(document.read_text(encoding="utf-8")):
        if not (document.parent / target).resolve().exists():
            broken.append(target)
    assert not broken, f"{document.name} links to missing files: {broken}"


def test_the_readme_lists_every_chapter():
    """A chapter nobody links to is a chapter nobody reads."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    chapters = sorted(p.name for p in DOCS.glob("[0-9][0-9]-*.md"))
    unlisted = [name for name in chapters if name not in readme]
    assert not unlisted, f"chapters missing from the README index: {unlisted}"


def test_every_chapter_says_what_pins_it():
    """The claim this repo makes is that each concept has code and a test
    behind it. A chapter with no citation is an essay."""
    silent = [
        path.name
        for path in DOCS.glob("[0-9][0-9]-*.md")
        if "Pinned by:" not in path.read_text(encoding="utf-8")
    ]
    assert not silent, f"chapters with no test citation: {silent}"
