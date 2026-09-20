"""The one test that touches the public internet, and only when told to.

Everything else in this suite runs against `fixtures/server.py`, which proves
the logic. What a fixture cannot prove is that the probe ladder still works
against a real server — real TLS, real redirects, a real DNS lookup.

So there is exactly one live test, it is off by default, and CI reaches it only
through a manually-dispatched workflow. A crawling toolkit whose suite quietly
reaches the internet is one that will eventually reach it from somebody else's
machine.

    CRAWLKIT_LIVE=1 pytest -m live
"""

import os

import pytest

from crawlkit import probe, robots

pytestmark = pytest.mark.live

needs_opt_in = pytest.mark.skipif(
    os.environ.get("CRAWLKIT_LIVE") != "1",
    reason="set CRAWLKIT_LIVE=1 to allow this test to reach the public internet",
)

# Reserved by the IANA for documentation and examples, which is as close to a
# target that nobody minds being probed as the internet offers.
TARGET = "https://example.com/"


@needs_opt_in
def test_the_ladder_reports_a_live_status_for_a_real_host():
    assert probe.check_one(TARGET) in probe.LIVE_HTTP


@needs_opt_in
def test_a_real_robots_file_parses():
    """Not an assertion about that site's rules — just that a real file, with
    whatever quirks it has today, does not break the parser."""
    rules = robots.Robots.load(TARGET)
    assert rules.reachable in (True, False)
    if rules.reachable:
        assert isinstance(rules.sitemaps(), list)


@needs_opt_in
def test_a_name_that_does_not_resolve_returns_the_sentinel():
    assert probe.check_one("https://this-host-does-not-exist.invalid/") == probe.FAILURE
