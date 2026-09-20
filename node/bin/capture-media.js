#!/usr/bin/env node
'use strict'
// Save the images a page is allowed to load, at the best size it will serve.
//
//   capture-media.js <page-url> --id-pattern REGEX [--hires TEMPLATE]
//                    [--out DIR] [--headful]
//
//   --id-pattern  regex with one capture group identifying a media id in a URL,
//                 e.g. 'media/([A-Za-z0-9]{20,})'. The length floor is what
//                 separates real ids from ordinary path segments.
//   --hires       URL template with {id} and {w}, requested from inside the
//                 page so the request carries its Referer, e.g.
//                 'https://cdn.example/media/{id}?w={w}'
//
// Every buffer is validated twice — at capture and again at write — so a
// partial download never reaches disk.

const fs = require('fs')
const path = require('path')

const contract = require('../lib/contract.js')
const launch = require('../lib/launch.js')
const waits = require('../lib/waits.js')
const scroll = require('../lib/scroll.js')
const media = require('../lib/mediaCapture.js')
const { isValidJpeg, describe } = require('../lib/jpeg.js')
const { ProfileHeld } = require('../lib/profileLock.js')

const EXIT = contract.get('exit_codes')

function valueOf(argv, name, fallback = null) {
  const i = argv.indexOf(name)
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback
}

async function main() {
  const argv = process.argv.slice(2)
  const idPattern = valueOf(argv, '--id-pattern')
  const hires = valueOf(argv, '--hires')
  const outDir = path.resolve(valueOf(argv, '--out', 'media'))
  const consumed = new Set([idPattern, hires, valueOf(argv, '--out')])
  const url = argv.find((a) => !a.startsWith('--') && !consumed.has(a))

  if (!url || !idPattern) {
    console.error('usage: capture-media.js <page-url> --id-pattern REGEX [--hires TEMPLATE] [--out DIR]')
    return EXIT.error
  }
  const idRe = new RegExp(idPattern)

  let session
  try {
    session = await launch.open({ headful: argv.includes('--headful') })
  } catch (err) {
    if (err instanceof ProfileHeld) {
      console.error(String(err.message))
      return EXIT.error
    }
    throw err
  }

  try {
    const { page } = session
    const captured = media.collect(page, {
      idFrom: (u) => {
        const m = u.match(idRe)
        return m ? m[1] : null
      },
    })

    await page.goto(url, { waitUntil: 'networkidle2', timeout: contract.get('challenge.goto_timeout_ms') })
    await waits.titleNot(page)
    // Scroll first: the page's own lazy loads establish the gallery and any
    // per-image tokens, so the injection below only has to beat their sizes.
    await scroll.hydrate(page, 'images')

    if (hires) {
      const ids = [...captured.best.keys()]
      await media.requestHiRes(page, ids.map((id) => media.hiResUrl(hires, id)))
    }

    fs.mkdirSync(outDir, { recursive: true })
    let saved = 0
    const skipped = []
    for (const [id, buf] of captured.best.entries()) {
      if (!isValidJpeg(buf)) {
        skipped.push(`${id}: ${describe(buf)}`)
        continue
      }
      fs.writeFileSync(path.join(outDir, `${id}.jpg`), buf)
      saved++
    }
    for (const line of skipped) console.error(`  skipped ${line}`)
    console.log(JSON.stringify({ ok: true, saved, seen: captured.best.size, dir: outDir }))
    return EXIT.ok
  } finally {
    await session.release()
  }
}

main()
  .then((code) => process.exit(code))
  .catch((err) => {
    console.error(String((err && err.stack) || err))
    process.exit(EXIT.error)
  })
