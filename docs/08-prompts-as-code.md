# 08 — Prompts composed by a script

**Why is the prompt built from a document by a program, instead of written
where it is used?**

Because an improvised prompt is re-invented on every fanout, and each iteration
ships a new class of malformed output. Once the text lives in a versioned
document, is composed deterministically, and is asserted by tests, a fanout is
reproducible and a regression shows up as a diff rather than as a bad harvest
three days later.

Nothing in this layer talks to a model. The output is text on disk.

## Composition

The dispatched body is sliced out of a markdown document between HTML-comment
anchors, so the document still reads and reviews as prose. A schema is lifted
**verbatim** from wherever it is defined — never retyped into the prompt,
because a paraphrase is a second description of one idea and the two drift, so
each agent then interprets its own version.

Placeholders are substituted against a whitelist with two hard exits: an unknown
`{{placeholder}}` in the document is a typo and fails before a single prompt is
emitted; a whitelisted key with no value is an emitter bug. A supplied `None`
raises rather than rendering empty — the case that matters is the one where the
agent receives an instruction with a hole in it and improvises around it. Render
nothing on purpose with an explicit sentinel.

Two bugs found while testing this, both invisible in the source: the
section-bounded search for a schema ran past its own section and lifted a fence
from a later one, and heading detection treated a `# ` comment inside a YAML
block as a heading, ending the section inside the fence it was delimiting.

## Anatomy

The sections are functions, assembled in a declared order. Each exists because
its absence produced a specific failure:

- **role** — scope to one item; an unscoped prompt invites an agent to widen
- **output contract** — stated early and echoed at the end, where the echo is
  *derived from* the opening declaration so the two cannot disagree
- **schema, verbatim**
- **census rule** — "every one of the 53, not a representative subset"
- **self-report header** — a machine-readable `N of M` first line, because
  silent omission is the failure a reviewer cannot see
- **source grounding** — nothing cited that was not fetched in this session
- **blocked-source escape** — a sanctioned way to say "I could not read this",
  with a marker and a statement of what the caller will do next. An agent with
  no such route invents content instead
- **anti-list** — a wrong/right/incident table of drift that actually arrived.
  Naming the incident is what stops a row reading as pedantry
- **per-field rules** — each with an explicit omit-don't-invent branch
- **numbered process** — so the measurement happens before the report

The verdict guide is generated from the shared vocabulary rather than typed, so
the values offered to an agent cannot drift from the values the ingester
accepts.

## Versioning

A prompt is an interface: changing it invalidates in-flight output the way
changing a wire format invalidates buffered messages. The document carries a
version and an amendment protocol, `ck-plan` refuses to emit against a document
lacking them, and every run writes a manifest with the version and the
document's hash — so six weeks later "which contract did this fanout run
against?" has an answer.

Drift guards are asserted against the **emitted** prompt, not the document, so
one check covers the slicer, the substitution and the document together.
Whitespace is collapsed first: a guard is a claim about what the prompt says,
not about where its line breaks fall, and matching literally means reflowing a
paragraph deletes a guarantee.

Pinned by: `tests/test_prompt_composition.py`, `tests/test_sections.py`,
`tests/test_prompt_contract.py`
