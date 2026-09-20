# 10 — Getting output back in

**How does agent output reach your data without destroying what is already
there?**

## Authorization is a list, never a listing

A harvester once collected every reply file in a directory, sorted by
modification time, and let the newest win per item. Unrelated agents from an
earlier run finished late, their files were newest, and hand-curated records
were silently overwritten. The run reported success.

So ingest authorizes against an explicit list of the agent ids you just
dispatched. It is a required argument, an empty list is an error, and **no
parameter anywhere in the module accepts a time, a path ordering, or a
newest-wins flag** — there is deliberately no spelling of the call that means
"take whatever is in the directory". Prefix matching is the one softness, because
ids get truncated when a human copies them.

The test reproduces the incident: the unauthorized reply is deliberately newer
and larger, and is still ignored.

## Five counted rejections

`unauthorized` · `no-block` · `unparseable` · `unknown-key` · `empty-result`

Counted rather than raised, because one bad reply in fifty is a statistic and
not a reason to stop the run. The subtle one is the last: a well-formed reply
containing zero records is a **failure**, not an empty dataset. Treating it as
data lets a dead agent blank a good file by succeeding at nothing.

Finding the payload is "marker first, size second". An agent will quote its
input back, or show a worked example, so the first fence is often wrong and the
largest is wrong whenever the quoted input is bigger than the answer.

Normalization runs **last**, and lets unknown values through. Folding known
spellings together is the job; coercing anything unrecognised would hide exactly
the drift the schema gate exists to catch.

## Recovery

A wide fanout dies for boring reasons and the work is not lost, just unread:
each agent's transcript is on disk.

Identity comes from a **marker the emitter wrote into the prompt**, not from
regexing the item id back out of the prose — that works right up until somebody
rewords the prompt, and then recovery silently finds nothing. The sidecar's
description is a fallback for fanouts this toolkit did not dispatch, and one
sidecar variant carries no description at all, which must not raise: recovery
runs precisely when things went wrong, so it cannot assume tidy inputs.

Completion is `stop_reason == "end_turn"` **and** a text block last. An agent
whose final block is a tool call died mid-call; its last words are a fragment,
and importing them looks like an answer while containing none. Transcripts are
parsed line by line, because a file appended live ends in a partial write often
enough to matter.

**Recovery finds; ingest authorizes.** This module returns results and applies
nothing, so "recover the dead agents" cannot become a route around the whitelist
that exists to stop stale replies landing.

Pinned by: `tests/test_ingest_authorization.py`, `tests/test_recover_transcripts.py`
