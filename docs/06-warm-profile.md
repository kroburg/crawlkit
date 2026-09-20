# 06 — A real profile, one process at a time

**Why drive a real browser with a persistent profile instead of sending
requests?**

Because some sites do not hand out their content to anything that has not
behaved like a visitor first. Not a login — a server-side session, or a
challenge whose clearance lives in a cookie. Once earned, that state is worth
keeping, and keeping it is what a profile directory is for: the first run pays
the cost, every later process starts already cleared.

Three smaller choices come with it. Real branded Chrome rather than a bundled
build, because the testing build advertises a different brand set. A flag that
clears `navigator.webdriver`, which is otherwise true and is the cheapest tell
there is. And a user-agent from the shared registry, because the stock headless
one announces itself in the string.

None of that is exotic; all of it is verified against the local fixture rather
than asserted.

## The lock is the important part

A shared profile means **strictly one process at a time**. Two browsers on one
user-data directory corrupt it or interleave their requests, and the failure
surfaces hours later on a different host with no evidence left. That is the
least debuggable failure in this repo.

"Harvest sequentially" as a comment does not survive reuse, so it is an
exclusive lock on the directory: the second process fails immediately and names
the one holding it. A lock from a crashed run is reclaimed rather than becoming
a permanent wedge.

## Taking what the page is already allowed to take

Two techniques follow from having a real session.

**Call the site's own API from inside the page.** A relative `fetch()` evaluated
in the document's context inherits the cookie, the `Origin`, `Referer` and
`Sec-Fetch-Site` headers, the real TLS fingerprint and the full client-hint set.
None of that is reproducible from outside, even with the cookie copied across —
which is why scraping rendered HTML is so often the harder path. Discover the
endpoints first by logging the page's own requests with assets and analytics
filtered out.

**Let the page fetch the media.** Media hosts commonly serve only to requests
carrying the page's referer, so downloading a URL scraped from the HTML returns
403. Intercept responses instead and keep the largest valid buffer per id; then
ask the page itself, from inside, to load a larger variant. Validity is checked
at capture and again at write, so a partial transfer never reaches disk.

## Hydration

Scroll until the page stops growing, re-reading `scrollHeight` **every
iteration** because it is the loop bound and lazy content moves it. Caching that
read is the tidy-up that silently truncates every harvest, and nothing in the
output looks wrong.

Pinned by: `node/test/browser.test.js`, `node/test/profileLock.test.js`
