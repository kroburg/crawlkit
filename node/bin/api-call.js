#!/usr/bin/env node
'use strict'
// Call a site's own JSON API from inside a cleared page of that origin.
//
//   api-call.js <landing-url> <relative-path> [--out FILE] [--headful]
//
// The body is written verbatim BEFORE any parse is attempted, so a challenge
// page or an error body is still captured for inspection instead of vanishing
// into a JSON exception. The summary on stdout reports the shape so a caller
// can decide success without reading the file.

const fs = require('fs')
const path = require('path')

const contract = require('../lib/contract.js')
const launch = require('../lib/launch.js')
const { viaLandingPage } = require('../lib/sameOrigin.js')
const { ProfileHeld } = require('../lib/profileLock.js')

const EXIT = contract.get('exit_codes')

async function main() {
  const argv = process.argv.slice(2)
  const positional = argv.filter((a) => !a.startsWith('--') && a !== argv[argv.indexOf('--out') + 1])
  const [landing, relPath] = positional
  const outIndex = argv.indexOf('--out')
  const out = outIndex >= 0 ? argv[outIndex + 1] : null

  if (!landing || !relPath) {
    console.error('usage: api-call.js <landing-url> <relative-path> [--out FILE] [--headful]')
    return EXIT.error
  }

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
    const res = await viaLandingPage(session.page, landing, relPath)
    if (out) {
      fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true })
      fs.writeFileSync(out, res.body)
    } else {
      process.stdout.write(res.body)
    }

    let shape = 'unparsed'
    try {
      const parsed = JSON.parse(res.body)
      shape = Array.isArray(parsed) ? `array(${parsed.length})` : `object(${Object.keys(parsed).join(',')})`
    } catch {}
    console.error(JSON.stringify({ status: res.status, bytes: res.body.length, shape }))
    return res.status >= 200 && res.status < 400 ? EXIT.ok : EXIT.error
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
