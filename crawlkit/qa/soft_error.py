"""HTTP 200 with an error page in the body.

The most expensive silent failure in a harvest, because every layer above
reports success: the probe records 200, the driver marks the item done, the
sentinel is written, and the archive fills with identical 700-byte apologies
that nobody notices until a parser yields nothing months later.

Observed live on an ASP/IIS citation database: requesting an article without a
server-side session returns `200 OK`, 714 bytes, no `<title>`, and a centred
message meaning "error in page parameters, or insufficient rights, or the
session has expired". Nothing in the status line or the headers distinguishes
it from a real article.

Three independent signals, because any one alone has honest counter-examples:
a real page can be short, a real page can lack a title, and a real page can
contain the word "error".
"""

import re

from crawlkit import contract

TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
TAGS = re.compile(r"<[^>]+>")
SCRIPTS = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)


def visible_text(html):
    return re.sub(r"\s+", " ", TAGS.sub(" ", SCRIPTS.sub(" ", html or ""))).strip()


def title_of(html):
    found = TITLE.search(html or "")
    return found.group(1).strip() if found else None


def inspect(html, min_text=500, locales=None, marker_ceiling=None):
    """(suspect, reasons). Two or more signals is a soft error page.

    `marker_ceiling` is why an error phrase is not conclusive on its own at any
    length: a long article *about* expired sessions contains the same words as a
    short page that is one. Below the ceiling the phrase decides; above it, the
    phrase is one signal among several and needs corroboration.
    """
    ceiling = marker_ceiling if marker_ceiling is not None else min_text * 4
    text = visible_text(html)
    reasons = []

    if len(text) < min_text:
        reasons.append(f"only {len(text)} chars of visible text")
    if not title_of(html):
        reasons.append("no <title>")
    lowered = text.lower()
    hit = next((m for m in contract.markers("soft_error_markers", locales) if m in lowered), None)
    if hit:
        reasons.append(f"error phrase: {hit!r}")
    if re.search(r"<img[^>]+(error|warning)\.(png|gif|svg)", html or "", re.I):
        reasons.append("error icon")

    conclusive = bool(hit) and len(text) < ceiling
    suspect = conclusive or len(reasons) >= 2
    return suspect, reasons


def is_soft_error(html, min_text=500, locales=None):
    return inspect(html, min_text, locales)[0]
