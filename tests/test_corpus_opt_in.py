"""The same assertions against a full local corpus, for anyone who has one.

A fixture server proves the logic; a real harvest proves the calibration. If
you have a directory of pages and photographs you actually fetched, point
CRAWLKIT_CORPUS at it and these run against the real thing:

    CRAWLKIT_CORPUS=~/harvests pytest -m corpus

Expected layout, all parts optional:

    <dir>/pages/*.html          pages fetched after any wall was cleared
    <dir>/photos/**/*.jpg       images downloaded from a real CDN
    <dir>/link_state.json       a state file written by ck-probe

No path in this file points anywhere in particular, which is the difference
between an opt-in test and a test that only its author can run.
"""

import json
import os
import re
from pathlib import Path

import pytest

from crawlkit import contract, linkstate
from crawlkit.qa import jpeg_frame

pytestmark = pytest.mark.corpus

ROOT = (
    Path(os.environ["CRAWLKIT_CORPUS"]).expanduser() if os.environ.get("CRAWLKIT_CORPUS") else None
)

needs_corpus = pytest.mark.skipif(
    ROOT is None, reason="set CRAWLKIT_CORPUS=<dir> to run against a real harvest"
)


def pages():
    return sorted((ROOT / "pages").glob("*.html")) if ROOT else []


def photos():
    return sorted((ROOT / "photos").rglob("*.jpg")) if ROOT else []


def visible_text(html):
    stripped = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", stripped)).strip()


@needs_corpus
def test_no_harvested_page_is_mistaken_for_a_wall():
    found = pages()
    if not found:
        pytest.skip("no pages/ in the corpus")
    pattern = contract.get("challenge.title_pattern")
    flagged = [p.name for p in found if pattern in p.read_text(errors="ignore").lower()]
    assert flagged == [], f"these were harvested successfully but read as walls: {flagged}"


@needs_corpus
def test_report_how_many_pages_fall_under_the_default_floor():
    """Not an assertion so much as a calibration reading: it tells you what to
    set `--min-body` to for this target before you turn the gate on."""
    found = pages()
    if not found:
        pytest.skip("no pages/ in the corpus")
    floor = contract.get("challenge.min_body")
    lengths = sorted(len(visible_text(p.read_text(errors="ignore"))) for p in found)
    thin = [n for n in lengths if n <= floor]
    print(f"\n{len(thin)}/{len(lengths)} pages below min_body={floor}; thinnest={lengths[0]}")
    assert lengths[0] > 0


@needs_corpus
def test_the_validator_accepts_every_real_photograph():
    found = photos()
    if not found:
        pytest.skip("no photos/ in the corpus")
    rejected = [
        (p.name, jpeg_frame.describe(p.read_bytes()))
        for p in found
        if not jpeg_frame.is_valid(p.read_bytes())
    ]
    assert rejected == [], f"false positives on real downloads: {rejected}"


@needs_corpus
def test_the_truncation_detector_clears_every_real_photograph():
    pytest.importorskip("PIL")
    found = photos()
    if not found:
        pytest.skip("no photos/ in the corpus")
    from crawlkit.qa import jpeg_bands

    assert jpeg_bands.scan(found) == []


@needs_corpus
def test_a_real_state_file_satisfies_the_closed_world_schema():
    path = ROOT / "link_state.json"
    if not path.is_file():
        pytest.skip("no link_state.json in the corpus")
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = linkstate.schema_errors(data)
    assert problems == [], problems[:10]
