# Record schema

**This file is an input to `ck-plan`, not documentation.** The fenced block
below is lifted verbatim into every harvest prompt. Editing it changes what a
fanout is asked to produce, so treat it as you would a wire format: bump the
prompt version in `harvest.md`, and re-dispatch anything in flight.

Verbatim matters. A schema paraphrased into a prompt is a second description of
one idea, and the two drift — each agent then interprets its own version and
the fanout returns records that disagree about their own shape.

## Record schema

```yaml
# One record per item. Omit a field you could not confirm; never invent one.
id: str                 # the item id exactly as given to you
title: str              # as published, not your summary of it
source_url: str         # the page you actually read, not a parent or a search
published: str | null   # ISO date, or null when the source does not say
authors: [str]          # empty list when the source names none
summary: str | null     # the source's own abstract, never one you compose
keywords: [str]
access: str             # one of the values listed in the prompt's verdict guide
notes: str              # anything a reviewer would need to judge the record
```

## Field notes

- `source_url` is the page carrying the fact. A landing page that merely links
  to it fails the test — omit the field instead.
- `published` stays null rather than guessing from a copyright footer.
- `summary` is the source's words. A composed summary looks identical to a real
  one and there is no way to tell them apart afterwards.
