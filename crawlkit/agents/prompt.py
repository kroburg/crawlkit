"""Building an agent's prompt from documents, deterministically.

The rule this module exists to enforce: **one canonical prompt, composed by a
script, never improvised per run.** An improvised prompt is re-invented on
every fanout, and each iteration ships a new class of malformed
output — sampling instead of enumerating, fabricated fields, values that broke
the schema. Once the text lives in a document with anchors, has a version, and
is asserted by tests, a fanout is reproducible and a regression is visible.

Two substantive choices:

* The prompt body is sliced out of a markdown doc between HTML-comment anchors,
  so the document still renders and reviews like prose.
* A schema is lifted **verbatim** from wherever it is defined, never retyped
  into the prompt. A paraphrased schema is the single most reliable way to get
  every agent to drift in a slightly different direction.
"""

import re

BEGIN = "<!-- BEGIN PROMPT -->"
END = "<!-- END PROMPT -->"

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")

# Render a placeholder as nothing, on purpose. Distinct from None, which is
# an emitter that lost track of a value it promised to supply.
OMIT = type("Omit", (), {"__repr__": lambda self: "OMIT"})()


class PromptError(ValueError):
    pass


def slice_canonical(text, begin=BEGIN, end=END, source="<prompt>"):
    """The text between the anchors, which is the only part ever dispatched."""
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < 0:
        raise PromptError(f"{source}: missing {begin!r} / {end!r} anchors")
    if text.find(begin, start + 1) >= 0:
        raise PromptError(f"{source}: {begin!r} appears more than once")
    if stop <= start:
        raise PromptError(f"{source}: end anchor precedes begin anchor")
    return text[start + len(begin) : stop].strip("\n")


def headings(text):
    """(offset, level, title) for every heading, ignoring fenced code blocks.

    Fence-awareness is not fussiness. A YAML or shell block routinely contains
    a line beginning `# `, which is indistinguishable from a markdown heading
    by pattern alone — so a naive scan finds a "heading" inside the very block
    it is trying to delimit, and the section ends before its own content.
    """
    out = []
    offset = 0
    fenced = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            fenced = not fenced
        elif not fenced:
            found = re.match(r"(#+)\s+(\S.*?)\s*$", line)
            if found:
                out.append((offset, len(found.group(1)), found.group(2)))
        offset += len(line)
    return out


def lift_block(text, heading, language="ya?ml", source="<doc>"):
    """The first fenced block under a heading, verbatim.

    Verbatim is the whole point: the schema in the prompt and the schema the
    ingester validates against must be the same characters, not two
    descriptions of one idea.

    The section ends at the next heading of the same or higher level. Without
    that bound the search runs past its own section and lifts whatever fence it
    meets next, so the prompt ships a schema belonging to something else — and
    since a prompt with the wrong schema still looks like a prompt, every agent
    in the fanout drifts the same way with nothing to notice.
    """
    found = [entry for entry in headings(text) if entry[2] == heading]
    if not found:
        raise PromptError(f"{source}: no heading {heading!r}")

    start, level, _ = found[0]
    after = [entry for entry in headings(text) if entry[0] > start and entry[1] <= level]
    section = text[start : after[0][0]] if after else text[start:]

    fence = re.search(rf"```{language}\s*\n(.*?)\n```", section, re.DOTALL)
    if not fence:
        raise PromptError(
            f"{source}: heading {heading!r} has no fenced {language} block of its own"
        )
    return fence.group(1).rstrip()


def placeholders(template):
    return set(PLACEHOLDER.findall(template))


def validate_template(template, known, source="<prompt>"):
    """Typo guard: a placeholder the emitter cannot fill is a hard error.

    Caught before a single prompt is emitted, because the alternative is
    dispatching a fleet of agents that each received the literal text
    '{{qouta_url}}' and quietly improvised around it.
    """
    unknown = placeholders(template) - set(known)
    if unknown:
        raise PromptError(
            f"{source}: unknown placeholders {sorted(unknown)}; "
            f"add them to the known set or fix the typo"
        )
    return True


def fill(template, values, source="<prompt>"):
    """Substitute. A known placeholder with no value is an emitter bug."""

    def replace(match):
        key = match.group(1)
        if key not in values:
            raise PromptError(
                f"{source}: no value supplied for {{{{{key}}}}} — emitter out of sync"
            )
        value = values[key]
        if value is OMIT:
            return ""
        if value is None:
            raise PromptError(
                f"{source}: {{{{{key}}}}} is None — pass prompt.OMIT to render nothing "
                f"deliberately, or supply the value"
            )
        return str(value)

    return PLACEHOLDER.sub(replace, template)


def compose(template, values, known=None, source="<prompt>"):
    validate_template(template, known if known is not None else values.keys(), source)
    filled = fill(template, values, source)
    if "{{" in filled or "}}" in filled:
        raise PromptError(f"{source}: unfilled placeholder survived substitution")
    return filled
