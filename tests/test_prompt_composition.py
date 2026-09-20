"""Composing a prompt from documents, and the two ways it goes quietly wrong.

Both failures here are silent: the prompt still renders, the fanout still
dispatches, and the damage only shows up in what N agents send back. That is
why they are errors rather than warnings.
"""

import pytest

from crawlkit.agents import prompt

DOC = """# Notes

Some prose.

<!-- BEGIN PROMPT -->
You are harvesting {{item}} from {{source}}.
<!-- END PROMPT -->

Trailing prose.
"""


def test_only_the_anchored_body_is_dispatched():
    body = prompt.slice_canonical(DOC)
    assert body == "You are harvesting {{item}} from {{source}}."
    assert "Trailing prose" not in body
    assert "Some prose" not in body


def test_missing_anchors_are_an_error_not_an_empty_prompt():
    with pytest.raises(prompt.PromptError):
        prompt.slice_canonical("# Doc\n\nNo anchors here.")


def test_a_duplicated_begin_anchor_is_rejected():
    """Two BEGIN anchors mean nobody can say which body ships."""
    with pytest.raises(prompt.PromptError):
        prompt.slice_canonical(DOC + DOC)


def test_anchors_in_the_wrong_order_are_rejected():
    with pytest.raises(prompt.PromptError):
        prompt.slice_canonical("<!-- END PROMPT -->\nbody\n<!-- BEGIN PROMPT -->")


# -- lifting a schema verbatim -------------------------------------------

SCHEMA_DOC = """# Data model

## Record schema

```yaml
id: str
title: str
```

## Notes on the schema

Prose only, no fence in this section.

## Another section

```yaml
unrelated: true
```
"""


def test_a_schema_is_lifted_verbatim():
    assert prompt.lift_block(SCHEMA_DOC, "Record schema") == "id: str\ntitle: str"


def test_a_heading_with_no_fence_does_not_borrow_one_from_a_later_section():
    """The bug this guards: an unbounded DOTALL search runs past the end of its
    own section and lifts the next fence it finds, so the prompt carries a
    schema from somewhere else entirely and every agent drifts the same way."""
    with pytest.raises(prompt.PromptError):
        prompt.lift_block(SCHEMA_DOC, "Notes on the schema")


def test_a_subsection_fence_still_belongs_to_its_parent():
    """Bounding at the next same-or-higher heading, not at any heading: a
    deeper subsection is part of the section it sits under."""
    doc = "## Outer\n\n### Inner\n\n```yaml\na: 1\n```\n\n## Next\n"
    assert prompt.lift_block(doc, "Outer") == "a: 1"


def test_an_absent_heading_is_an_error():
    with pytest.raises(prompt.PromptError):
        prompt.lift_block(SCHEMA_DOC, "No such heading")


# -- substitution ---------------------------------------------------------


def test_an_unknown_placeholder_in_the_document_is_a_typo_caught_before_dispatch():
    with pytest.raises(prompt.PromptError) as caught:
        prompt.validate_template("fetch {{qouta_url}}", {"quota_url"})
    assert "qouta_url" in str(caught.value)


def test_a_known_placeholder_with_no_value_is_an_emitter_bug():
    with pytest.raises(prompt.PromptError):
        prompt.fill("fetch {{url}}", {})


def test_a_none_value_is_rejected_rather_than_silently_emptied():
    """The module promises that a missing value is an error. Accepting None and
    rendering "" breaks that promise in the one case where it matters: the
    agent receives an instruction with a hole in it and improvises."""
    with pytest.raises(prompt.PromptError) as caught:
        prompt.fill("fetch {{url}}", {"url": None})
    assert "url" in str(caught.value)


def test_omitting_a_placeholder_deliberately_is_explicit():
    assert prompt.fill("fetch {{url}}{{extra}}", {"url": "u", "extra": prompt.OMIT}) == "fetch u"


def test_compose_refuses_to_emit_a_prompt_with_a_hole_in_it():
    with pytest.raises(prompt.PromptError):
        prompt.compose("a {{one}} b {{two}}", {"one": "1"}, known={"one", "two"})


def test_compose_renders_a_complete_prompt():
    out = prompt.compose("harvest {{item}} from {{source}}", {"item": "x", "source": "y"})
    assert out == "harvest x from y"
    assert "{{" not in out


def test_a_hash_comment_inside_a_fence_is_not_mistaken_for_a_heading():
    """The bug this guards is invisible in the source and fatal in the output.

    A YAML or shell block routinely opens with a `# ` comment, which matches
    the markdown heading pattern exactly. A naive scan therefore ends the
    section inside the very fence it is delimiting, and the schema the prompt
    was supposed to carry disappears.
    """
    doc = (
        "# Record schema\n\n"
        "## Record schema\n\n"
        "```yaml\n# one record per item\nid: str\n```\n\n"
        "## Notes\n"
    )
    assert prompt.lift_block(doc, "Record schema") == "# one record per item\nid: str"


def test_headings_inside_a_fence_are_not_headings():
    doc = "## Real\n\n```sh\n# not a heading\n```\n\n## Also real\n"
    assert [title for _, _, title in prompt.headings(doc)] == ["Real", "Also real"]
