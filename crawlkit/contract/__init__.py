"""Access to the shared constants.

`constants.json` is read by both runtimes. Nothing here interprets the values;
modules ask for what they need by dotted path so a typo fails loudly at import
time rather than silently yielding None deep inside a crawl.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("constants.json")

_MISSING = object()

LOCALE_CATEGORIES = ("challenge_markers", "soft_error_markers", "consent_labels")
DEFAULT_LOCALES = ("en",)


@lru_cache(maxsize=1)
def all():
    return json.loads(PATH.read_text(encoding="utf-8"))


def get(dotted, default=_MISSING):
    node = all()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            if default is _MISSING:
                raise KeyError(f"{dotted!r} not in {PATH}")
            return default
        node = node[part]
    return node


def vocabulary(name):
    """Accepted values for a closed vocabulary, comment keys removed."""
    return {k: v for k, v in get(f"vocabularies.{name}").items() if not k.startswith("_")}


def offered_values(name):
    """The subset a prompt may offer an agent.

    Kept as a filter over the accepted set rather than a second list, so the
    in-prompt enum is a subset of the validated enum by construction.
    """
    return {k: v for k, v in vocabulary(name).items() if v.get("offer_to_agent")}


def derived_values(name):
    return {k: v for k, v in vocabulary(name).items() if not v.get("offer_to_agent")}


def locales(selected=None):
    """Locale codes to match against, honouring CRAWLKIT_LOCALES.

    English only by default. Matching a block page means matching the language
    it is written in, so this is the knob a user of a non-English target turns
    — rather than editing a list inside a module.
    """
    if selected is None:
        env = os.environ.get("CRAWLKIT_LOCALES", "")
        selected = [code.strip() for code in env.split(",") if code.strip()] or DEFAULT_LOCALES
    known = {code for code in get("locales") if not code.startswith("_")}
    unknown = [code for code in selected if code not in known]
    if unknown:
        raise KeyError(f"unknown locale(s) {unknown}; known: {sorted(known)}")
    return tuple(selected)


def markers(category, selected=None):
    """Every marker for `category` across the selected locales, lowercased."""
    if category not in LOCALE_CATEGORIES:
        raise KeyError(f"unknown locale category {category!r}; known: {LOCALE_CATEGORIES}")
    out = []
    for code in locales(selected):
        out.extend(get(f"locales.{code}.{category}"))
    # Dedupe while preserving order: a phrase shared by two locales matches once.
    return tuple(dict.fromkeys(marker.lower() for marker in out))


LIVE_HTTP = frozenset(get("http.live_statuses"))
FAILURE = get("http.failure_sentinel")
STICKY_MARKER = get("sticky.marker")
