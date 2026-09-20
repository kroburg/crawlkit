#!/usr/bin/env node
'use strict'
// What is this page actually talking to?
//
//   discover-endpoints.js <url> [--interact MODULE] [--bodies] [--headful]
//
// Prints the site's own request URLs, assets and third-party analytics filtered
// out. --interact loads a module exporting `async (page) => {}` to drive the UI
// (pan a map, open a tab, page a list) so the app widens its own queries and
// reveals more endpoints; --bodies also captures the JSON that came back.
//
// Use the output to pick a target for api-call.js. This is the step that turns
// "scrape the rendered HTML" into "call the API the page calls".

const path = require('path')

const contract = require('../lib/contract.js')
const launch = require('../lib/launch.js')
const waits = require('../lib/waits.js')
const consent = require('../lib/consent.js')
const endpoints = require('../lib/endpoints.js')
const { ProfileHeld } = require('../lib/profileLock.js')

const EXIT = contract.get('exit_codes')

async function main() {
  const argv = process.argv.slice(2)
  const interactIndex = argv.indexOf('--interact')
  const interactPath = interactIndex >= 0 ? argv[interactIndex + 1] : null
  const url = argv.find((a) => !a.startsWith('--') && a !== interactPath)

  if (!url) {
    console.error('usage: discover-endpoints.js <url> [--interact MODULE] [--bodies] [--headful]')
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
    const { page } = session
    // Recorders attach BEFORE navigation or the first burst is lost.
    const requests = endpoints.recordRequests(page)
    const bodies = argv.includes('--bodies') ? endpoints.recordApiBodies(page) : null

    await page.goto(url, { waitUntil: 'networkidle2', timeout: contract.get('challenge.goto_timeout_ms') })
    await waits.titleNot(page)

    // The banner only exists once the real page is served, and it blocks the
    // UI the interaction below needs.
    const dismissed = await consent.dismiss(page)
    if (dismissed) console.error(`consent: clicked ${JSON.stringify(dismissed)}`)

    if (interactPath) {
      const drive = require(path.resolve(interactPath))
      await (typeof drive === 'function' ? drive : drive.interact)(page)
    }
    await waits.sleep(2000)

    for (const found of requests.urls()) console.log(found)
    if (bodies) console.error(JSON.stringify(bodies.bodies().map((b) => ({ url: b.url, status: b.status, bytes: b.body.length })), null, 2))
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
