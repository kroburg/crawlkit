# 02 — When is a link actually dead?

**How do you tell a dead URL from one that merely dislikes your request?**

Badly, if you use HEAD alone. Plenty of servers answer HEAD with 405, or with a
404 they would never give a GET. A checker that believes them reports live pages
as dead, and the URLs get deleted in review — which is how a link database loses
good sources while its report says everything is fine.

## The ladder

1. **HEAD, strict TLS.** Cheap. If the status is in `live_statuses`, stop.
2. **On a TLS error only, retry with verification relaxed.** Sites that ship an
   incomplete certificate chain work in browsers, which fetch the missing
   intermediate themselves, and fail in Python's standard library. Classifying
   the error takes three attempts because `urllib` buries the cause: a direct
   `ssl.SSLError`, a `URLError.reason` wrapping one, and finally a lowercase
   string sniff.
3. **Otherwise, GET** — including after a `-1`.

The rule that surprises people: **the last attempt wins, even when it is worse
than the first.** A GET is what a human with a browser will experience, so it is
the verdict worth recording. Reporting the more flattering HEAD result is how a
checker ends up disagreeing with the person looking at the same page.

`HTTPError` is caught before the general handler, because an `HTTPError` *is* a
response — catching it later relabels every 404 as a connection failure. A
genuine failure gets `-1`, distinct from any HTTP status. PDFs get a longer
timeout, because they are slow to first byte and a short cap turns a live file
into a false negative.

## Politeness without a rate limiter

Bucket the URLs by host, hand each whole bucket to one worker, and sleep between
hits inside a bucket. Two requests then cannot land on the same server at once —
not because a limiter forbids it, but because only one thread could issue them.
No locks, no shared counter, nothing to get wrong under concurrency. Hosts run
in parallel, so wall time tracks the slowest host rather than the sum.

## Encoding

Host and path need different encodings — punycode for one, percent-escapes for
the other — and applying either to the wrong component yields a URL that
resolves nowhere. Keeping `%` in every safe set makes the function idempotent,
so encoding an already-encoded URL is a no-op rather than turning `%D0` into
`%25D0`. An IDNA failure degrades to the raw host and lets the probe fail
honestly, instead of dropping the URL.

## Known false positives

405 on HEAD · 404 on HEAD with 200 on GET · timeouts on PDFs · transient TLS
chain failures. Each has a test, and so does the negative control: a real 404
must still be reported as 404, or the fallback is just laundering breakage.

Pinned by: `tests/test_probe_ladder.py`, `tests/test_schedule.py`
