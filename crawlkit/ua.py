"""The user-agent registry.

Chrome's "new headless" mode still advertises a `HeadlessChrome/...` token,
and stripping it is the cheapest and most universally-checked evasion there
is. Both runtimes spoof from this one registry; `assert_no_headless_token`
is called by the tests so a future edit cannot quietly reintroduce the tell.
"""

import re

from crawlkit import contract

_HEADLESS = re.compile(r"headless", re.IGNORECASE)

DEFAULT = "desktop_chrome"


def ua(name=DEFAULT):
    value = contract.get(f"user_agents.{name}")
    assert_no_headless_token(value)
    return value


def has_headless_token(value):
    return bool(_HEADLESS.search(value or ""))


def assert_no_headless_token(value):
    if has_headless_token(value):
        raise ValueError(f"user agent advertises headless: {value!r}")
    return value
