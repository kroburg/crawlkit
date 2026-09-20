# Harvest prompt

**Prompt version: 1 (2026-09-20).** Changing the canonical block below
invalidates agent output already in flight, the same way changing a wire format
invalidates buffered messages. So: bump this version, update the drift-guard
list, and re-dispatch anything running.

**This file is an input to `ck-plan`, not documentation.** Only the text
between the anchors is dispatched. Everything outside them — this preamble, the
drift guard, the provenance — is for whoever edits the file.

Placeholders are filled by the emitter and validated against a whitelist, so a
typo here (`{{sorce_url}}`) fails the run rather than reaching an agent as
literal text it has to guess around.

<!-- BEGIN PROMPT -->
You are harvesting one item for a catalogue: **{{item_id}}** ({{item_title}}).
Work on this one only.

Your entire output is ONE fenced ```json block, in your reply.
**DO NOT WRITE FILES.**
No preamble, no commentary, nothing outside the fence.

## Schema (verbatim — do not paraphrase, do not 'improve')

```yaml
{{schema_block}}
```

**Census, not sample.** Every record the source lists under {{source_url}}
belongs in your output. Not a representative subset — all of them. Returning a
handful costs fewer tokens and looks finished, which is exactly why it has to
be said.

Your first line inside the fence MUST be exactly this shape:

    // verification: <N> of <M> records from {{source_url}}, {{today}}. Excluded: <list or "none">.

N is what you are returning, M is what the source lists. If N < M, name the
exclusions individually — never leave them implicit. A reviewer reading
"8 of 53" sees the problem at a glance; silent omission is invisible.

**Ground every claim.** Fetch each source before citing it; the page must
actually contain the fact you attach to it. A landing page that merely links to
the fact FAILS: omit the field rather than cite a parent URL. NEVER cite from
prior knowledge — only what you fetched in this session.

**If a source is walled.** A sub-2KB body, a challenge interstitial, or an
empty JavaScript shell means you did NOT read the page. Do not pretend you did.
Omit the affected field and record `BLOCKED: <url>` in your exclusions. Do not
try to work around it yourself; the caller will render it with a browser and
re-dispatch. Reporting this is useful, not a confession of failure.

## Previously observed drift — do not repeat

| Wrong | Right | Why |
|---|---|---|
| `published: "2024"` | `published: "2024-03-01"` or `null` | a year is not a date; null is honest |
| `authors: "A. Smith, B. Jones"` | `authors: ["A. Smith", "B. Jones"]` | the schema says list |
| `summary:` your paraphrase | the source's own abstract, or `null` | a composed summary is indistinguishable afterwards |
| `source_url:` a search results page | the page carrying the fact | a search URL is not a citation |
| inventing `access:` | one of the values in the guide below | unlisted values are dropped at ingest |

- `title` — as published. Do not normalise capitalisation or expand
  abbreviations; the catalogue matches on it.
- `keywords` — the source's own terms. An empty list is a fine answer.
- `notes` — anything a reviewer would need to judge the record, including why
  you excluded something.

## Process

1. Fetch {{source_url}} and count the records it lists. That count is M.
2. For each record, fetch the page carrying its detail before writing a field.
3. Write one record per item, in the schema above.
4. Count what you are returning. That count is N.
5. Write the verification line first, then the records.
6. Reply with EXACTLY one fenced ```json block. No commentary outside it.
<!-- END PROMPT -->

## Drift guard

`tests/test_prompt_contract.py` asserts every phrase below appears in the
**emitted** prompt — which covers the slicer, the substitution and this
document together, so a guard that survives here but is dropped in composition
still fails. When a new drift class shows up, add a row to the anti-list above
*and* a phrase here.

- `Census, not sample`
- `DO NOT WRITE FILES`
- `verification: <N> of <M>`
- `Excluded:`
- `NEVER cite from prior knowledge`
- `BLOCKED:`
- `Work on this one only`
- `do not paraphrase`

## Provenance

Every rule above traces to a failure that reached real output:

- The census sentence exists because a fanout shipped 8 records out of 53. Its
  absence is not neutral — a sample is the default behaviour.
- The verification header exists because silent omission is the failure a
  reviewer cannot see.
- The blocked-source clause exists because an agent with no sanctioned way to
  report a wall invents content instead.
- The verbatim-schema rule exists because paraphrased schemas drift per agent.

The canonical prompt is downstream of these. Add a rule to its source first,
then port the phrasing here.
