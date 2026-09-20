"""Deciding when a page has actually arrived.

Two predicates for one problem, and the difference between them is the most
useful thing in this module.

`title_not` watches for a named interstitial to disappear. Precise, and useless
against a wall you have not met before.

`body_text_at_least` watches the rendered *text* grow past a floor. It is the
portable one, for three reasons: it needs no per-vendor string; a challenge stub
carries kilobytes of obfuscated script and almost no text, so measuring
innerText discriminates where innerHTML does not; and because the predicate is
re-evaluated in each new document, it survives the challenge reloading itself
out from under you — which is exactly where a single read-then-check fails.

Every wait here is opportunistic: a timeout means "stop waiting", not "fail".
The exception is an explicitly named selector, where absence is real evidence
that the render did not produce what the caller asked for.
"""

from crawlkit import contract

TITLE_PATTERN = contract.get("challenge.title_pattern")
MIN_BODY = contract.get("challenge.min_body")
POLL_ATTEMPTS = contract.get("challenge.poll_attempts")
POLL_INTERVAL_MS = contract.get("challenge.poll_interval_ms")
NETWORKIDLE_MS = contract.get("challenge.networkidle_timeout_ms")


def challenge_budget_ms(attempts=None, interval_ms=None):
    return (attempts or POLL_ATTEMPTS) * (interval_ms or POLL_INTERVAL_MS)


def settle(page, timeout_ms=None):
    """Ordinary hydration. Returns quickly when the page is already done."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms or NETWORKIDLE_MS)
        return True
    except Exception:
        return False


def body_text_at_least(page, minimum=None, timeout_ms=None):
    """Poll rendered text length. Survives the challenge's own auto-reload."""
    floor = MIN_BODY if minimum is None else minimum
    try:
        page.wait_for_function(
            f"document.body && document.body.innerText.length > {int(floor)}",
            timeout=timeout_ms or challenge_budget_ms(),
        )
        return True
    except Exception:
        return False


def title_not(page, pattern=None, timeout_ms=None):
    """Wait out a named interstitial. Never reloads: a reload restarts the
    proof-of-work and can escalate a soft challenge into a hard block."""
    needle = (pattern or TITLE_PATTERN).lower()
    try:
        page.wait_for_function(
            "needle => !document.title.toLowerCase().includes(needle)",
            arg=needle,
            timeout=timeout_ms or challenge_budget_ms(),
        )
        return True
    except Exception:
        return False


def selector_present(page, selector, timeout_ms=None):
    """The one gate, not an accelerator: absence is a real failure."""
    page.wait_for_selector(selector, timeout=timeout_ms or challenge_budget_ms())
    return True


def text_length(page):
    try:
        return page.evaluate("document.body ? document.body.innerText.length : 0")
    except Exception:
        return 0
