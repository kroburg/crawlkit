# 06 — recover a dead fanout

`ck-recover` salvages a fanout that died before anyone collected it, by
reading agent transcripts straight off disk. This example points it at the
committed fixture transcripts in `tests/data/transcripts` (not copied here)
rather than a real `~/.claude/projects` tree.

Run `run.sh` and read the recovery table: `a1111111` is complete and
identified by the `[crawlkit-item: ...]` marker its prompt carried — the
completion oracle (`stop_reason == end_turn` *and* a text block last) says
it finished. `b2222222` died mid tool-call (`incomplete`) and `c3333333` was
stopped by the user with no marker anywhere in its prompt — neither is
recoverable, marker or not. Only the one genuinely finished reply gets
written to `out/recovered/`, named by the *item* it answers. `run.sh` then
feeds that filename straight to `ck-ingest --agent-ids`, because
recovery finding a reply is not the same as ingest trusting it — the same
whitelist authorization from example 05 still applies, recovery just
supplies its input instead of a directory of live replies.
