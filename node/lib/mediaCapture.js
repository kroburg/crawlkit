'use strict'
// Take the images the page is already allowed to fetch.
//
// Media hosts commonly serve only to requests carrying the page's Referer (and
// the clearance cookie), so downloading a URL scraped out of the HTML gets a
// 403. Two moves solve it without ever leaving the browser:
//
//   1. Intercept responses and keep the buffer the page itself received.
//   2. Ask for a bigger variant from INSIDE the page — `new Image().src = ...`
//      issues a fully credentialed request with the right Referer, and the
//      element is never attached to the DOM; the load is the whole point.
//
// Keeping the largest valid buffer per media id then yields the best available
// resolution with no knowledge of the CDN's sizing scheme: the page loads a
// thumbnail and a medium, we add a large, and max() sorts it out.

const contract = require('./contract.js')
const { isValidJpeg } = require('./jpeg.js')

const HIRES_WIDTH = contract.get('media.hires_width')
const PER_IMAGE_MS = contract.get('media.per_image_timeout_ms')
const DRAIN_MS = contract.get('media.drain_ms')
const AVATAR_MARKERS = contract.get('media.avatar_url_markers')

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/**
 * Attach a response collector.
 * @param idFrom  url -> media id, or null to ignore the response
 */
function collect(page, { idFrom, isAvatar = defaultIsAvatar, valid = isValidJpeg } = {}) {
  const best = new Map()
  page.on('response', async (res) => {
    const url = res.url()
    let id
    try {
      id = idFrom(url)
    } catch {
      return
    }
    if (!id || isAvatar(url)) return
    try {
      const buf = await res.buffer()
      // Strict monotone max: the page fetches several sizes of the same image.
      if (valid(buf) && (!best.has(id) || buf.length > best.get(id).length)) best.set(id, buf)
    } catch {
      // Body consumed, cache hit, or frame gone — all expected, and an
      // unhandled rejection in an async listener would kill the process.
    }
  })
  return {
    best,
    clear: () => best.clear(),
    get: (id) => best.get(id),
  }
}

function defaultIsAvatar(url) {
  return AVATAR_MARKERS.some((marker) => url.includes(marker))
}

/** Ask the page to load bigger variants, then wait for the buffers to land. */
async function requestHiRes(page, urls, { perImageMs = PER_IMAGE_MS, drainMs = DRAIN_MS } = {}) {
  if (!urls.length) return
  await page.evaluate(
    async (list, timeout) => {
      await Promise.all(
        list.map(
          (src) =>
            new Promise((resolve) => {
              const im = new Image()
              im.onload = im.onerror = () => resolve()
              im.src = src
              // Whichever settles first wins; a hung socket must not stall the
              // batch, and extra resolve() calls on a Promise are ignored.
              setTimeout(resolve, timeout)
            })
        )
      )
    },
    urls,
    perImageMs
  )
  // evaluate() resolving only means the image elements settled — the CDP
  // response events carrying the bytes arrive asynchronously on this side.
  await sleep(drainMs)
}

function hiResUrl(template, id, width = HIRES_WIDTH) {
  return template.replace('{id}', id).replace('{w}', String(width))
}

module.exports = { collect, requestHiRes, hiResUrl, defaultIsAvatar, HIRES_WIDTH }
