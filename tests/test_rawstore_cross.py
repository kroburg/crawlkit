"""Either runtime can reparse what the other fetched.

The two halves of this toolkit meet at exactly two places, and this is the
important one: a page harvested by the Node warm session must be re-parseable
by Python without a browser, and vice versa. If the layout drifts, the cheap
recovery path silently stops working — so it is asserted in both directions.
"""

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from crawlkit import rawstore

REPO = Path(__file__).resolve().parents[1]
node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run_node(script):
    return subprocess.run(
        ["node", "-e", script], cwd=REPO, capture_output=True, text=True, check=True
    )


@node
def test_node_reparses_what_python_harvested(tmp_path):
    rawstore.harvest(
        tmp_path,
        "page",
        "<title>From Python</title>",
        lambda html: {"title": None},
        meta={"url": "http://h/p"},
    )

    run_node(
        textwrap.dedent(
            f"""
            const raw = require('./node/lib/rawFirst.js')
            const generic = require('./node/parsers/generic.js')
            const out = raw.reparse({json.dumps(str(tmp_path))}, 'page', generic.parse)
            if (out.title !== 'From Python') throw new Error('bad title: ' + out.title)
            """
        )
    )

    fixed = rawstore.read_parsed(tmp_path, "page")
    assert fixed["title"] == "From Python"
    assert fixed["url"] == "http://h/p", "provenance survives a cross-runtime reparse"


@node
def test_python_reparses_what_node_harvested(tmp_path):
    run_node(
        textwrap.dedent(
            f"""
            const raw = require('./node/lib/rawFirst.js')
            raw.harvest({json.dumps(str(tmp_path))}, 'page', '<title>From Node</title>',
                        () => ({{ title: null }}), {{ url: 'http://h/n' }})
            """
        )
    )

    assert rawstore.sentinel_ok(tmp_path, "page")
    fixed = rawstore.reparse(
        tmp_path, "page", lambda html: {"title": html.split("<title>")[1].split("<")[0]}
    )
    assert fixed["title"] == "From Node"
    assert fixed["url"] == "http://h/n"


@node
def test_both_runtimes_agree_on_the_sentinel_rule(tmp_path):
    """Non-empty parsed file, in both languages, or resume logic diverges."""
    rawstore.write_raw(tmp_path, "half", "<html></html>")
    rawstore.sentinel_path(tmp_path, "half").write_text("")

    out = run_node(
        textwrap.dedent(
            f"""
            const raw = require('./node/lib/rawFirst.js')
            process.stdout.write(JSON.stringify({{
              half: raw.sentinelOk({json.dumps(str(tmp_path))}, 'half'),
              missing: raw.sentinelOk({json.dumps(str(tmp_path))}, 'nope'),
            }}))
            """
        )
    )
    seen = json.loads(out.stdout)
    assert seen == {"half": False, "missing": False}
    assert not rawstore.sentinel_ok(tmp_path, "half")
    assert not rawstore.sentinel_ok(tmp_path, "nope")
