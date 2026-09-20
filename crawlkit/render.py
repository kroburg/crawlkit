"""One-shot rendering for a page a plain fetch cannot read.

This is the rescue path, not the harvesting path: no persistent profile, one
browser, one page, exit. Use it when a URL that is genuinely live returns a
sub-2KB stub to `urllib` because a JS proof-of-work runs first, and use the
warm-profile Node harvester when you need a *session*.

What it returns is the serialized DOM after JS, not the network response body.
"""

from crawlkit import contract, resolverules, ua, waits
from crawlkit.exits import Exit

VIEWPORT = contract.get("browser.viewport")
LOCALE = contract.get("browser.locale")
GOTO_TIMEOUT_MS = contract.get("challenge.goto_timeout_ms")


class RenderError(RuntimeError):
    def __init__(self, message, code=Exit.ERROR):
        super().__init__(message)
        self.code = code


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RenderError(
            "playwright not installed — pip install -e '.[browser]' "
            "&& python -m playwright install chromium",
            Exit.ERROR,
        ) from exc
    return sync_playwright


def fetch(
    url,
    min_body=None,
    wait_selector=None,
    timeout_ms=None,
    resolve=None,
    locale=LOCALE,
    user_agent=None,
    require_growth=False,
):
    """Render `url` and return its HTML.

    `require_growth=True` turns the body-growth heuristic into a gate and exits
    CHALLENGE_NOT_CLEARED when the text never arrives — for callers that would
    rather fail loudly than archive a challenge stub.
    """
    sync_playwright = _playwright()
    # Playwright leaves navigator.webdriver true and ships a UA carrying the
    # Headless token: two free bot tells on an otherwise careful fetch. The
    # flag clears the first, the context-level user_agent the second.
    dns_args = resolverules.launch_args(resolve)
    args = list(contract.get("browser.launch_args")) + dns_args

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True, args=args)
        try:
            context = browser.new_context(
                user_agent=user_agent or ua.ua(),
                locale=locale,
                viewport=dict(VIEWPORT),
                # Only relaxed when DNS is pinned: the cert cannot match a path
                # the resolver was forced onto. Never relaxed otherwise.
                ignore_https_errors=bool(dns_args),
            )
            page = context.new_page()
            try:
                page.goto(url, timeout=timeout_ms or GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
            except Exception as exc:
                raise RenderError(f"navigation failed: {exc}", Exit.TIMEOUT) from exc

            if wait_selector:
                try:
                    waits.selector_present(page, wait_selector, timeout_ms)
                except Exception as exc:
                    raise RenderError(
                        f"selector {wait_selector!r} never appeared: {exc}", Exit.TIMEOUT
                    ) from exc
            else:
                waits.settle(page)
                grew = waits.body_text_at_least(page, min_body, timeout_ms)
                if require_growth and not grew:
                    raise RenderError(
                        f"body text never exceeded {min_body or waits.MIN_BODY} chars "
                        f"({waits.text_length(page)} rendered) — challenge not cleared",
                        Exit.CHALLENGE_NOT_CLEARED,
                    )
            return page.content()
        finally:
            browser.close()
