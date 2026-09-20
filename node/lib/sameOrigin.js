'use strict'
// Call a site's own JSON API from inside a page that already got through.
//
// This is the cheapest general bypass in the toolkit. A relative fetch()
// executed in the document's context inherits, for free and correctly:
// the clearance cookie, Origin / Referer / Sec-Fetch-Site: same-origin, the
// real TLS and JA3 fingerprint, and the full sec-ch-ua client-hint set. None
// of that is reproducible from curl or node-fetch even with the cookie copied
// across, which is why scraping the HTML is so often the harder path.
//
// The landing page is a carrier only — its DOM is never touched.

const { titleNot } = require('./waits.js')
const contract = require('./contract.js')

/**
 * @param {string} relPath e.g. "/api/items?x=1" — MUST be relative, so the
 *   browser resolves it against the cleared origin.
 */
async function callSameOrigin(page, relPath, { accept = 'application/json' } = {}) {
  if (/^[a-z]+:\/\//i.test(relPath)) {
    throw new Error(`pass a relative path, not an absolute URL: ${relPath}`)
  }
  return page.evaluate(
    async (p, acceptHeader) => {
      const res = await fetch(p, { headers: { Accept: acceptHeader } })
      return { status: res.status, body: await res.text() }
    },
    relPath,
    accept
  )
}

/** Land on a page of the target origin, clear any wall, then call the API. */
async function viaLandingPage(page, landingUrl, relPath, options = {}) {
  await page.goto(landingUrl, {
    waitUntil: 'domcontentloaded', // only the origin matters, not its subresources
    timeout: contract.get('challenge.goto_timeout_ms'),
  })
  await titleNot(page, options)
  return callSameOrigin(page, relPath, options)
}

module.exports = { callSameOrigin, viaLandingPage }
