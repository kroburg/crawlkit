"""The renderer against the fixture's walls.

The interesting assertions are the negative ones: each names a plausible
implementation and shows the fixture defeating it.
"""

import pytest

from crawlkit import instrument, render, waits
from crawlkit.exits import Exit

playwright = pytest.importorskip("playwright.sync_api", reason="needs playwright")
pytestmark = pytest.mark.playwright


@pytest.fixture
def page():
    """Function-scoped on purpose: the sync API cannot nest, and the tests that
    call render.fetch() start their own driver."""
    from crawlkit import contract, ua

    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch(
            headless=True, args=list(contract.get("browser.launch_args"))
        )
        context = browser.new_context(user_agent=ua.ua())
        yield context.new_page()
        browser.close()


def test_a_plain_read_of_the_challenge_sees_only_the_stub(page, fixture_http):
    """The baseline failure this whole layer exists to fix."""
    page.goto(f"{fixture_http}/challenge/clears-after/3")
    assert "Just a moment" in page.content()
    assert waits.text_length(page) < 100


def test_repeated_navigation_clears_a_counter_based_wall(page, fixture_http):
    """The warm-session case: one context, several attempts, cookie carried."""
    for _ in range(4):
        page.goto(f"{fixture_http}/challenge/clears-after/3")
    assert waits.body_text_at_least(page, 2000, timeout_ms=5000)
    assert "Just a moment" not in page.content()


def test_body_growth_predicate_survives_the_page_reloading_itself(fixture_http):
    """A one-shot read cannot pass this: the document is swapped underneath."""
    html = render.fetch(f"{fixture_http}/challenge/autoreload", min_body=2000, require_growth=True)
    assert "autoreload-cleared" in html


def test_measuring_innerhtml_instead_of_innertext_would_be_fooled(page, fixture_http):
    page.goto(f"{fixture_http}/challenge/never")
    markup = page.evaluate("document.body.innerHTML.length")
    text = page.evaluate("document.body.innerText.length")
    assert markup > 20000, "the stub is bulky"
    assert text < 100, "but carries almost no rendered text"


def test_a_wall_that_never_clears_is_reported_not_archived(fixture_http):
    with pytest.raises(render.RenderError) as caught:
        render.fetch(
            f"{fixture_http}/challenge/never", min_body=2000, timeout_ms=3000, require_growth=True
        )
    assert caught.value.code == Exit.CHALLENGE_NOT_CLEARED


def test_polling_a_wall_never_reloads_it(fixture_http):
    """A reload restarts the proof-of-work and can escalate to a hard block,
    so the wait must be a poll over one navigation — asserted server-side."""
    before = _navigations(fixture_http, "/challenge/never")
    with pytest.raises(render.RenderError):
        render.fetch(
            f"{fixture_http}/challenge/never", min_body=2000, timeout_ms=3000, require_growth=True
        )
    assert _navigations(fixture_http, "/challenge/never") - before == 1


def _navigations(base, path):
    import json
    import urllib.request

    with urllib.request.urlopen(f"{base}/stats", timeout=5) as resp:
        return json.loads(resp.read())["navigations"].get(path, 0)


def test_without_require_growth_the_stub_is_returned_rather_than_raising(fixture_http):
    """Timeouts are opportunistic by default: a short page is not an error."""
    html = render.fetch(f"{fixture_http}/challenge/never", min_body=2000, timeout_ms=2000)
    assert "Just a moment" in html


def test_short_but_finished_pages_are_not_treated_as_failures(fixture_http):
    html = render.fetch(f"{fixture_http}/health", min_body=100000, timeout_ms=2000)
    assert "ok" in html


def test_title_predicate_clears_on_a_self_reloading_wall(page, fixture_http):
    """Both predicates ride out the document swap; neither issues a reload."""
    page.goto(f"{fixture_http}/challenge/autoreload")
    assert waits.title_not(page, timeout_ms=15000)
    assert "autoreload-cleared" in page.content()


def test_named_selector_is_a_gate_not_a_hint(fixture_http):
    with pytest.raises(render.RenderError) as caught:
        render.fetch(f"{fixture_http}/health", wait_selector="#never-exists", timeout_ms=1500)
    assert caught.value.code == Exit.TIMEOUT


def test_named_selector_succeeds_when_present(fixture_http):
    html = render.fetch(f"{fixture_http}/lazy", wait_selector="#top", timeout_ms=5000)
    assert "start" in html


def test_dns_pinning_reaches_a_host_the_resolver_cannot(fixture_port):
    """pinned.invalid resolves nowhere; only --host-resolver-rules gets there."""
    html = render.fetch(
        f"http://pinned.invalid:{fixture_port}/pinned",
        min_body=1,
        timeout_ms=8000,
        resolve=["pinned.invalid:127.0.0.1"],
    )
    assert "resolved to pinned.invalid" in html


def test_rendered_page_does_not_advertise_automation(page, fixture_http):
    """Two free tells Playwright leaves on by default, both closed here."""
    page.goto(f"{fixture_http}/health")
    assert page.evaluate("navigator.webdriver") in (False, None)
    assert "Headless" not in page.evaluate("navigator.userAgent")


def test_csp_violations_are_only_visible_when_the_listener_is_installed_first(page, fixture_http):
    recorder = instrument.Recorder().attach(page)
    page.goto(f"{fixture_http}/csp")
    page.wait_for_timeout(300)
    assert any(v["directive"].startswith("script-src") for v in recorder.violations(page))

    late = page.context.new_page()
    late.goto(f"{fixture_http}/csp")
    late.wait_for_timeout(300)
    assert late.evaluate("(window.__ck && window.__ck.csp) || []") == []
