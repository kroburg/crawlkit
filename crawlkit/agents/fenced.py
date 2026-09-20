"""Finding the payload in an agent's reply.

An agent asked for one fenced block will usually produce one. It will also,
often enough to matter, quote its input back first, show a worked example, or
open with a small illustrative fence before the real answer. So "take the first
fence" and "take the largest fence" are both wrong in ordinary cases — the
first loses to a preamble, the largest loses whenever the quoted input is
bigger than the answer.

Marker first, size second. If the caller can name something the payload must
contain, that decides it; only then does size break the tie.
"""

import json
import re
from dataclasses import dataclass

FENCE = re.compile(r"```([\w+-]*)[ \t]*\n(.*?)\n[ \t]*```", re.DOTALL)

SELF_REPORT = re.compile(
    r"verification:\s*(?P<n>\d+)\s+of\s+(?P<m>\d+)\b(?P<rest>[^\n]*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Block:
    language: str
    body: str
    start: int
    end: int


def blocks(text, language=None):
    found = [
        Block(match.group(1).lower(), match.group(2), match.start(), match.end())
        for match in FENCE.finditer(text or "")
    ]
    if language:
        wanted = language.lower()
        found = [block for block in found if block.language == wanted]
    return found


def select(text, *, marker=None, language=None):
    """The block most likely to be the payload, or None."""
    candidates = blocks(text, language)
    if not candidates:
        return None
    if marker:
        marked = [block for block in candidates if marker in block.body]
        if marked:
            return max(marked, key=lambda block: len(block.body))
    return max(candidates, key=lambda block: len(block.body))


def extract_json(text, *, marker=None):
    """(object, status) where status is ok | no-block | unparseable.

    Returning a status rather than raising, because at ingest time one
    unparseable reply among fifty is a counted rejection, not a stopped run.
    """
    block = select(text, marker=marker, language="json") or select(text, marker=marker)
    if block is None:
        return None, "no-block"
    try:
        return json.loads(block.body), "ok"
    except json.JSONDecodeError:
        return None, "unparseable"


def parse_self_report(text):
    """The N-of-M header the prompt demands, or None.

    Its whole purpose is to make the denominator visible, so it is parsed back
    out and recorded. A record set whose header says 8 of 53 is a different
    thing from one that simply contains 8 records, and only the header can tell
    you which you have.
    """
    found = SELF_REPORT.search(text or "")
    if not found:
        return None
    rest = found.group("rest")
    excluded = []
    marker = re.search(r"excluded:\s*(.*)", rest, re.IGNORECASE)
    if marker:
        listed = marker.group(1).strip().rstrip(".")
        if listed and listed.lower() not in ("none", '"none"'):
            excluded = [part.strip() for part in listed.split(",") if part.strip()]
    return {"n": int(found.group("n")), "m": int(found.group("m")), "excluded": excluded}


def strip_self_report(body):
    """(report, body-without-it) so the header does not reach a JSON parser."""
    report = parse_self_report(body)
    if report is None:
        return None, body
    cleaned = "\n".join(line for line in body.splitlines() if not SELF_REPORT.search(line)).strip()
    return report, cleaned
