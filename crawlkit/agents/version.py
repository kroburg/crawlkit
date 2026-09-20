"""Prompt documents carry a version and an amendment protocol.

A prompt is an interface. Changing it invalidates in-flight agent output the
same way changing a wire format invalidates buffered messages, so the document
states its version, and the test suite asserts that the document still carries
the sections describing how to change it. Without that, the prompt drifts by
accretion and nobody can say which fanout ran against which contract.
"""

import re

VERSION_LINE = re.compile(r"\*\*Prompt version:\s*(\d+)\s*\(([^)]+)\)\.?\*\*")

REQUIRED_SECTIONS = ("## Drift guard", "## Provenance")


class VersionError(ValueError):
    pass


def version_of(text, source="<prompt doc>"):
    found = VERSION_LINE.search(text)
    if not found:
        raise VersionError(
            f"{source}: no version line. Expected '**Prompt version: N (YYYY-MM-DD).**'"
        )
    return int(found.group(1)), found.group(2).strip()


def check_protocol(text, source="<prompt doc>", required=REQUIRED_SECTIONS):
    missing = [heading for heading in required if heading not in text]
    if missing:
        raise VersionError(f"{source}: missing {missing}; a prompt doc documents how to amend it")
    return True


def guard_phrases_present(emitted, phrases):
    """Which drift guards are missing from the EMITTED prompt.

    Asserted against the emitted text rather than the document, so one check
    covers the slicer, the substitution and the document together: a guard that
    survives in the source and is dropped during composition is still gone.

    Whitespace is collapsed on both sides first. A guard is a claim about what
    the prompt says, not about where its line breaks fall — matching literally
    means rewrapping a paragraph silently deletes a guarantee.
    """
    haystack = _collapse(emitted)
    return [phrase for phrase in phrases if _collapse(phrase) not in haystack]


def _collapse(text):
    return re.sub(r"\s+", " ", text or "").strip()
