# 01 — probe a rotting list

`ck-probe` walks a link-state file and asks, for each URL, "is this still
there?" — cheaply, with a HEAD-first ladder that falls back to GET only when
HEAD is inconclusive, and never re-probes a URL a browser already confirmed.

Run `run.sh` and read the two `state.json` dumps it prints. In the "before"
copy, everything is unknown except one record pre-stamped
`verified_via: fetch_js` — a browser-grade confirmation. In the probe log,
watch `/head405` and `/head404` come back `200` (HEAD failed, GET rescued
them), `/dead` stay `404` (both methods agree it's gone), and the sticky
record get reported `(confirmed by rendering, not re-probed)` — it costs no
request at all. In the "after" copy, every record now carries `http_status`
and `last_checked`, and the sticky record is the only one that kept its
`verified_via` untouched.
