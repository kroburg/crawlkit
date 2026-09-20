# 07 — QA a harvest

`ck-qa` asks whether a finished harvest is any good, entirely offline,
because every failure it looks for looks like success at fetch time: 200
status, no parser exception, a file with content in it.

Run `run.sh` and read all three checks against `records.json` (each exits
non-zero on purpose — that's the correct result here, not a bug in the
example). `ck-qa echo` catches `r2`'s `title`, which is really a
percent-encoded URL slug (`item-42%20details`) an extractor echoed back
instead of reading the page. `ck-qa census` shows `summary` filled in only 1
of 5 records — a selector that silently stopped matching produces exactly
this shape, with nothing upstream raising. `ck-qa agree` runs `records.json`
against `pass_b.json`, an independent second pass that disagrees on `r4`'s
`access` value; the disputed field is held back, and `out/auto_applicable.json`
holds only the values both passes actually agreed on.
