# 05 — ingest a fanout

`ck-ingest` is the layer that decides which agent replies get to become
records. `results/` holds five committed, hand-written replies; `run.sh`
feeds them through a single `ck-ingest` call with no network and no model.

Read the rejection report `run.sh` prints, one line per mechanism:
`agent-intruder` isn't in `--agent-ids` and is rejected outright
(`unauthorized`) — authorization is a whitelist, never a directory listing.
`agent-aa11` quotes its own dispatched task back before answering, and that
quoted block is *bigger* than its real answer; with no `--marker` to break
the tie, the larger (wrong) block wins selection and has no `item_id`
(`unknown-key`) — this is `crawlkit/agents/fenced.py`'s "quoted input larger
than the answer" trap, live. `agent-bb22` replies well-formed JSON with zero
records (`empty-result`) — a dead agent succeeding at nothing must not blank
a real one. `agent-cc33` answers for `ghost-item`, which is not in
`items.json`; ingest itself doesn't know the work-list, so this one gets
written, then the census gate in `ck-ingest --worklist` catches it as
`1 invented` and drops it before the file is saved. Only `agent-dd44`
survives every gate, and `out/records.json` ends up with exactly that one
record.
