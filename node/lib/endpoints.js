'use strict'
// Find the API a single-page app is really talking to.
//
// Run this once against a JS-heavy page and read off the internal endpoints;
// then call them directly with sameOrigin.js instead of parsing rendered HTML.
// Two negative filters do the work: one drops static assets, one drops
// third-party analytics — what remains is the site's own traffic. Sorted and
// deduplicated so two runs can be diffed.

const ASSET = /\.(png|jpe?g|webp|avif|gif|svg|ico|woff2?|ttf|css|mp4|webm)(\?|$)/i
const THIRD_PARTY = /google|gstatic|facebook|analytics|doubleclick|yandex\.ru\/metrika|hotjar|segment|sentry/i

function recordRequests(page, { keep, maxLength = 160 } = {}) {
  const seen = new Set()
  page.on('request', (req) => {
    const url = req.url()
    if (ASSET.test(url) || THIRD_PARTY.test(url)) return
    if (keep && !keep(url, req)) return
    seen.add(url.slice(0, maxLength))
  })
  return {
    urls: () => [...seen].sort(),
    clear: () => seen.clear(),
  }
}

/** Capture response bodies for endpoints matching `match` while the UI is driven. */
function recordApiBodies(page, { match = /\/api\//, maxBytes = 400000 } = {}) {
  const captured = []
  page.on('response', async (res) => {
    const url = res.url()
    if (!match.test(url) || ASSET.test(url)) return
    try {
      const body = await res.text()
      captured.push({ url, status: res.status(), body: body.slice(0, maxBytes) })
    } catch {
      // Body already consumed, served from cache, or the frame navigated away.
    }
  })
  return { bodies: () => captured }
}

module.exports = { recordRequests, recordApiBodies, ASSET, THIRD_PARTY }
