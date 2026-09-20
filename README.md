# crawlkit

A toolkit for harvesting data from websites that were not built to be
harvested, and for knowing afterwards whether what you got is any good.

It is deliberately not a framework. It is a set of small composable pieces,
each of which exists because something went wrong once: a link file that rotted
without anyone noticing, a page that returned `200 OK` with an error in the
body, a fanout of agents that confidently returned a third of the data and
reported success. **[docs/incidents.md](docs/incidents.md) is the list.** Start
there — every rule below traces to a row in it, and if a row's cost doesn't
worry you, you don't need that part.

Every command's flags are in `--help`; this file does not repeat them.

## The situation this is for

You need data from a few thousand pages. Straight away:

- Some pages are behind a wall. Not a login — a challenge that a browser passes
  and `urllib` does not, or a server-side session you only get by visiting the
  front page first.
- Your list of URLs starts rotting the moment you write it down, and a naive
  checker will tell you a live page is dead often enough that you stop
  believing it.
- The pages that *are* fetched are not all fine. Some are error pages wearing a
  success code. Some are real but were saved before half the content loaded.
- If you fan the reading-out across LLM agents, they will sometimes return a
  representative sample instead of everything, and say nothing about it.

None of those failures announce themselves. Each one looks like success at the
layer above. That is the thing this toolkit is actually about.

## Three layers

**Probing and state** — pure standard library, so it runs anywhere a Python
interpreter runs. A probe ladder that escalates HEAD → relaxed-TLS → GET and
lets the last attempt win; scheduling that is parallel across hosts and strictly
serial within one, so politeness is structural rather than a shared counter; a
link-state file with disjoint writers, so a verdict earned expensively is never
overwritten by a cheap sweep.

**Fetching** — a one-shot renderer for a page that needs JavaScript, and a
warm-profile browser session for a site that needs to remember you. Two
runtimes, because the two jobs are genuinely different, reading one shared
constants file that a test proves they both see identically. Robots is honoured
by an RFC 9309 matcher rather than the standard library's, which reads a very
common file shape backwards. A circuit breaker stops the whole run on the first
refusal, and explicitly does not rotate identity and try again.

**Fanout and QA** — prompts composed by a script from a versioned document,
never improvised; agents that measure while the script judges; ingest that
authorizes by an explicit list of dispatched agents and counts every reason a
reply was rejected; a census gate that reports both what went missing and what
was invented; and detectors for the corruption that arrives looking like data.

## One screen

```bash
make install                      # venv, deps, a browser
make fixture &                    # a local site reproducing every wall offline
export CRAWLKIT_FIXTURE=http://127.0.0.1:8080

ck-probe examples/01_probe_a_rotting_list/state.json
ck-plan  --worklist examples/04_plan_a_fanout/items.json \
         --prompt docs/prompts/harvest.md --schema docs/prompts/schema.md --dry-run
bash examples/05_ingest_a_fanout/run.sh
```

Nothing above touches a third-party site. The fixture server is the test
target, and its endpoints are written to *fail* a plausible-but-wrong crawler
rather than merely pass a correct one — a challenge that reloads itself, a page
that grows while you scroll it, a media endpoint that refuses a request without
the page's referer.

## Gotchas worth knowing before you start

- **A `200` is not a success.** → [04-walls](docs/04-walls.md),
  [11-output-qa](docs/11-output-qa.md)
- **`urllib.robotparser` will tell you that you may crawl pages you may not.**
  → [05-robots](docs/05-robots.md)
- **Rotating IPs after a block burns addresses and teaches you nothing.**
  → [04-walls](docs/04-walls.md)
- **Two browsers on one profile directory is the least debuggable failure
  here.** → [06-warm-profile](docs/06-warm-profile.md)
- **An agent that knows which number passes will produce that number.**
  → [09-census-and-scalars](docs/09-census-and-scalars.md)
- **"Newest file wins" is how curated data gets silently overwritten.**
  → [10-ingest-and-recovery](docs/10-ingest-and-recovery.md)

## Chapters

| | |
|---|---|
| [01-contract](docs/01-contract.md) | Why one JSON file is read by two languages |
| [02-probing](docs/02-probing.md) | When is a link actually dead? |
| [03-link-state](docs/03-link-state.md) | How a browser-confirmed URL survives the next sweep |
| [04-walls](docs/04-walls.md) | Telling a challenge stub from a thin real page |
| [05-robots](docs/05-robots.md) | Reading the crawl surface a site offers |
| [06-warm-profile](docs/06-warm-profile.md) | Why a real profile, one process at a time |
| [07-storage-and-driving](docs/07-storage-and-driving.md) | What gets written first, and what makes a re-run cheap |
| [08-prompts-as-code](docs/08-prompts-as-code.md) | Why a script composes the prompt from a document |
| [09-census-and-scalars](docs/09-census-and-scalars.md) | Did the fanout return everything, and who decides? |
| [10-ingest-and-recovery](docs/10-ingest-and-recovery.md) | Getting output back in without destroying what is there |
| [11-output-qa](docs/11-output-qa.md) | The scrape succeeded — is the data any good? |

## Install and test

```bash
make install        # everything, including a browser for the renderer
make install-bare   # no extras, to prove the pure layer really is pure
make check          # lint + pytest + node --test + every example
```

Python 3.12+, Node 18+. The probing, state and fanout layers need nothing
installed; rendering needs Playwright, the warm-profile session needs a real
Chrome, and image QA needs Pillow. `pytest` prints which of those are present
and how to enable the rest, so a smaller run on a fresh clone explains itself.

## Scope

This honours `robots.txt`, stops on refusal, paces itself, and caches so it
never asks twice. It is for reading public pages carefully. It is not for
defeating access controls, and the one thing it deliberately will not do is
help you get around a block: when a site refuses, the run ends and you decide
what to do next.

MIT licensed. See [LICENSE](LICENSE).
