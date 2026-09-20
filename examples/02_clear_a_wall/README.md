# 02 — clear a wall

`ck-render --require-growth` turns a bot-wall's stub into a hard failure
instead of silently archiving it as content: it polls the rendered *text*
(never the noisy `innerHTML`) until it grows, or exits 3.

Run `run.sh` (it self-skips with one line if Playwright isn't installed).
The first call hits `/challenge/clears-after/0` and prints the cleared
page's `<h1>` — the wall drops on this session's very first hit. The second
call hits `/challenge/never`, which by design drops nothing ever, and the
script prints `exit code: 3` plus the "challenge not cleared" message. Note
the `/0`, not a higher number: `ck-render` opens a fresh browser context per
call, so it can never accumulate hits across a *session* the way a real
multi-visit browsing session (or the warm-profile Node harvester in example
08) would — that's the actual reason one wall clears immediately and the
other can't clear at all under this tool.
