# 04 — plan a fanout

`ck-plan` turns a work-list and a versioned prompt document into dispatchable
prompt files. No model runs here — the whole point is that a fanout's inputs
are reproducible text on disk, checkable by a diff instead of discovered bad
three days later.

Run `run.sh`. `--dry-run` first prints the work-list with no prompt bodies —
what would be dispatched, not yet dispatched. The real emit then writes one
`.md` per item plus a `manifest.json`. Look at three things `run.sh` greps
out of `book-1.md`: the record schema, lifted **verbatim** from
`docs/prompts/schema.md` into the prompt (not retyped, not paraphrased); the
`// verification: <N> of <M>` census sentence, which carries the item's own
source URL as the real denominator agents must count against; and the
`[crawlkit-item: book-1]` marker, the same machine-readable token that
`ck-recover` (example 06) reads back out of a dead agent's transcript to
identify what it was working on.
