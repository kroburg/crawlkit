'use strict'
// Scroll until the page stops growing.
//
// The subtlety is one line: document.body.scrollHeight is re-read as the loop
// CONDITION, not captured once. Lazy content appends as you scroll, so the
// bound moves and the loop extends to cover it. Hoisting that read into a
// variable — the obvious tidy-up — silently truncates every harvest, and
// nothing in the output looks wrong.

const contract = require('./contract.js')

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const PRESETS = {
  text: contract.get('scroll.text'),
  images: contract.get('scroll.images'),
}

async function hydrate(page, preset = 'text', overrides = {}) {
  const cfg = { ...(PRESETS[preset] || PRESETS.text), ...overrides }
  await page.evaluate(
    async (stepPx, delayMs) => {
      for (let y = 0; y < document.body.scrollHeight; y += stepPx) {
        window.scrollTo(0, y)
        await new Promise((r) => setTimeout(r, delayMs))
      }
      window.scrollTo(0, 0)
    },
    cfg.step_px,
    cfg.delay_ms
  )
  await sleep(cfg.settle_ms)
}

module.exports = { hydrate, PRESETS }
