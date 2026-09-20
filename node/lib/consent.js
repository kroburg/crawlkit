'use strict'
// Dismiss a cookie banner by what it SAYS, not by what it is called.
//
// Consent vendors hash their class names and re-skin on a schedule, so a CSS
// selector rots. Button text does not. Anchored at the start of the trimmed
// label and matched case-insensitively, with the first match clicked and the
// search stopped — otherwise you eventually click "Reject all" somewhere below.
//
// Clicked in-page rather than through page.click() so it works on buttons that
// are off-screen or under an overlay: no scroll-into-view, no hit testing.
//
// The labels come from the shared locale table, so adding a language is a data
// change both runtimes see rather than an edit to this file.

const contract = require('./contract.js')

function labelsFor(locales) {
  const codes = locales && locales.length ? locales : ['en']
  const out = []
  for (const code of codes) {
    for (const label of contract.get(`locales.${code}.consent_labels`, [])) out.push(label)
  }
  return [...new Set(out)]
}

const ACCEPT = labelsFor(
  (process.env.CRAWLKIT_LOCALES || 'en').split(',').map((c) => c.trim()).filter(Boolean)
)

async function dismiss(page, { labels = ACCEPT, settleMs = 500 } = {}) {
  const clicked = await page.evaluate((candidates) => {
    const wanted = candidates.map((c) => c.toLowerCase())
    for (const el of document.querySelectorAll('button, a, [role="button"]')) {
      const text = (el.textContent || '').trim().toLowerCase()
      if (!text) continue
      if (wanted.some((w) => text.startsWith(w))) {
        el.click()
        return text.slice(0, 40)
      }
    }
    return null
  }, labels)
  if (clicked) await new Promise((r) => setTimeout(r, settleMs))
  return clicked
}

module.exports = { dismiss, labelsFor, ACCEPT }
