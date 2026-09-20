'use strict'
// The Node half of the wait predicates. Same two mechanisms, same numbers, one
// contract file — see crawlkit/waits.py for why body text is the portable one.

const contract = require('./contract.js')

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/**
 * Poll document.title until a named interstitial disappears.
 * Never reloads: a reload restarts the challenge's proof-of-work.
 */
async function titleNot(page, { pattern, attempts, intervalMs } = {}) {
  const needle = (pattern || contract.get('challenge.title_pattern')).toLowerCase()
  const tries = attempts || contract.get('challenge.poll_attempts')
  const gap = intervalMs || contract.get('challenge.poll_interval_ms')
  for (let i = 0; i < tries; i++) {
    let title = ''
    try {
      title = (await page.title()) || ''
    } catch {
      // A navigation mid-poll (the challenge reloading itself) invalidates the
      // handle for an instant; that is expected, keep polling.
    }
    if (!title.toLowerCase().includes(needle)) return true
    await sleep(gap)
  }
  return false
}

/** Poll rendered text length. Survives the document being swapped underneath. */
async function bodyTextAtLeast(page, { minimum, attempts, intervalMs } = {}) {
  const floor = minimum === undefined ? contract.get('challenge.min_body') : minimum
  const tries = attempts || contract.get('challenge.poll_attempts')
  const gap = intervalMs || contract.get('challenge.poll_interval_ms')
  for (let i = 0; i < tries; i++) {
    if ((await textLength(page)) > floor) return true
    await sleep(gap)
  }
  return false
}

async function textLength(page) {
  try {
    return await page.evaluate(() => (document.body ? document.body.innerText.length : 0))
  } catch {
    return 0
  }
}

module.exports = { titleNot, bodyTextAtLeast, textLength, sleep }
