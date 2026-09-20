# 05 — Reading the crawl surface a site offers

**Why not `urllib.robotparser`?**

Because on a very common file shape it gives the wrong answer, in the dangerous
direction.

Real files are routinely written as an opening `Allow: /` followed by a list of
`Disallow:` lines closing the expensive dynamic endpoints. The standard library
returns the **first** matching rule in file order, so that leading `Allow: /`
swallows every Disallow beneath it. A crawler using it walks straight into the
pages the site was protecting, while believing itself compliant. It also
supports no wildcards, so `Disallow: *.xls` matches nothing.

RFC 9309 requires the **most specific** match to win. That is what this
implements: longest pattern wins, ties go to Allow, `*` and `$` supported.

There is a regression test that asserts our answer and then asserts the standard
library disagrees on the same file — so if the standard library is ever fixed,
we find out.

## Ambiguity resolves toward not crawling

A rule value is supposed to start with `/`, and plenty do not. A bare
`foo.asp` anchored at the root would match nothing, silently granting access to
everything the site meant to close. So a pattern that starts with neither `/`
nor `*` is widened to match anywhere. When a rule is unclear, do not crawl.

An unreachable `robots.txt` denies everything. Silence is not permission.

## Read it for the map, not just the manners

The disallow list is usually a map of where the expensive queries live — search
endpoints, per-entity listings, citation expanders — while the static item pages
are left open and enumerated in a sitemap. The set you are asked not to touch is
very often the exact set that gets crawlers banned, so honouring it and staying
unblocked are the same decision.

The sitemap is also the cheapest discovery there is: no link graph to walk, no
query pages to hit, just the canonical list. `walk_sitemaps` caps how many child
sitemaps it will pull and reports the remainder, because a top-level index can
name a thousand children and tens of millions of URLs — the caller states how
much of that to fetch rather than finding out the hard way.

Pinned by: `tests/test_robots_and_circuit.py`
