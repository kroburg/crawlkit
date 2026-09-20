"""One fixture server per test session, shared by every suite.

Node's suite spawns the same module as a subprocess, so the endpoint semantics
cannot drift between the two runtimes' tests.
"""

import importlib.util
import os
import shutil
import socket
import time
import urllib.request
from pathlib import Path

import pytest

from crawlkit import contract
from fixtures import hosts, server


def pytest_report_header(config):
    """Say up front which optional gates are satisfied.

    Without this a clean checkout silently runs a much smaller suite than the
    author's machine, and the newcomer has to read skipif decorators to find out
    why. Each 'no' below names the switch that turns it on.
    """
    have = {
        "playwright": importlib.util.find_spec("playwright") is not None,
        "pillow": importlib.util.find_spec("PIL") is not None,
        "node": shutil.which("node") is not None,
        "chrome": Path(
            os.environ.get("CRAWLKIT_CHROME") or contract.get("browser.branded_chrome")
        ).exists(),
        "corpus": bool(os.environ.get("CRAWLKIT_CORPUS")),
        "live": os.environ.get("CRAWLKIT_LIVE") == "1",
    }
    flags = " ".join(f"{name}={'yes' if ok else 'no'}" for name, ok in have.items())
    lines = [f"crawlkit: {flags}"]
    hints = []
    if not have["playwright"]:
        hints.append("playwright: pip install -e '.[browser]' && playwright install chromium")
    if not have["chrome"]:
        hints.append("chrome: install Chrome or set CRAWLKIT_CHROME=<path>")
    if not have["corpus"]:
        hints.append("corpus: set CRAWLKIT_CORPUS=<dir> (see tests/test_corpus_opt_in.py)")
    if hints:
        lines.append("crawlkit: to enable — " + "; ".join(hints))
    return lines


def _wait(port, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.05)
    raise RuntimeError(f"fixture server did not come up on {port}")


@pytest.fixture(scope="session")
def fixture_http():
    httpd, port = server.serve(host="")
    _wait(port)
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


@pytest.fixture(scope="session")
def fixture_port(fixture_http):
    return int(fixture_http.rsplit(":", 1)[1])


@pytest.fixture(scope="session")
def fixture_https():
    """TLS with an untrusted issuer — the stdlib rejects it, by design."""
    httpd, port = server.serve(host="127.0.0.1", https=True)
    yield f"https://badchain.test:{port}"
    httpd.shutdown()


@pytest.fixture
def named_hosts():
    """Real hostnames resolving to loopback, for bucketing and IDNA tests."""
    with hosts.resolving() as mapping:
        yield mapping


@pytest.fixture(scope="session")
def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
