"""Extraction that reflects the request back instead of reading the response.

A broken selector, a template that fell through to its default, or a parser
handed the wrong DOM node all produce the same failure shape: the field a
human expects to be a title or a name instead holds the URL (or a piece of
it) that was fetched to produce that field. Nothing about the fetch failed —
status 200, a normal-sized body — so nothing upstream of this check notices.

Two signals are conclusive alone because nothing legitimate produces them: a
raw URL, or a percent-escape, has no business inside human-facing text. Every
other signal is weak and needs a second one alongside it, because each has an
honest counter-example on its own — see the percent-sign note below.
"""

import re
from typing import NamedTuple

URL_SCHEME = re.compile(r"https?://")
# A literal "%" is not evidence of anything: "Скидка 50%" and "5% last year"
# are ordinary text. A percent-*escape* (%2C, %20, ...) is never typed by a
# human and never produced by a template rendering a number — only by a URL
# or a raw request path leaking into the field.
PERCENT_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")

# A run this long with no whitespace at all is not a written phrase; short
# runs are excluded because slugs, codes and abbreviations are legitimately
# tight ("SKU-4471").
NO_WHITESPACE_FLOOR = 25
PATH_EXTENSIONS = (".html", ".htm", ".php", ".asp", ".aspx")
# Above this fraction of non-letter characters, the string reads as a code or
# path rather than prose. Below it, tolerates punctuation-heavy but genuine
# titles ("Q3 2024: Revenue Up 12%").
NON_LETTER_RATIO_CEILING = 0.6
# Any single weak signal alone has a legitimate counter-example (see the
# constants above); requiring two together is what keeps the detector from
# being disabled a week in after it condemns a normal title.
WEAK_SIGNAL_FLOOR = 2


class Echo(NamedTuple):
    record_id: object
    field: str
    value: object
    reasons: list[str]


def _non_letter_ratio(text):
    letters = sum(1 for ch in text if ch.isalpha())
    return 1 - (letters / len(text))


def looks_echoed(value, *, kind="title") -> tuple[bool, list[str]]:
    """(suspect, reasons) — same shape as crawlkit.qa.soft_error.inspect.

    `kind` only labels the reasons (e.g. "title", "seller_name") so a caller
    scanning several fields at once can tell them apart in a report.
    """
    if not isinstance(value, str) or not value:
        return False, []

    if URL_SCHEME.search(value):
        return True, [f"{kind} contains a URL"]
    if PERCENT_ESCAPE.search(value):
        return True, [f"{kind} contains a percent-escape"]

    weak = []
    if not re.search(r"\s", value) and len(value) > NO_WHITESPACE_FLOOR:
        weak.append(f"{kind} has no whitespace and is longer than {NO_WHITESPACE_FLOOR} chars")
    if value.lower().endswith(PATH_EXTENSIONS):
        weak.append(f"{kind} ends in a file extension")
    ratio = _non_letter_ratio(value)
    if ratio > NON_LETTER_RATIO_CEILING:
        weak.append(f"{kind} is {ratio:.0%} non-letter characters")

    return len(weak) >= WEAK_SIGNAL_FLOOR, weak


def scan_records(records, fields, *, key="id") -> list[Echo]:
    """One Echo per suspect (record, field) pair, in record then field order."""
    found = []
    for record in records:
        record_id = record.get(key)
        for field in fields:
            value = record.get(field)
            suspect, reasons = looks_echoed(value, kind=field)
            if suspect:
                found.append(Echo(record_id, field, value, reasons))
    return found
