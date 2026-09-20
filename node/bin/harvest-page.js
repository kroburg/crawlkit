#!/usr/bin/env node
'use strict'
// Fetch one page through the warm profile and store it raw-first.
//
//   harvest-page.js <url> <id> [--dir DIR] [--parser MODULE]
//                              [--headful] [--reparse] [--no-wall]
//
// Exit codes come from the shared contract:
//   0 stored   1 error   2 navigation timeout   3 challenge never cleared
//
// --reparse runs BEFORE any browser is launched: it re-runs the parser over
// the cached HTML, so iterating on extraction costs nothing and cannot get you
// rate-limited.

const path = require('path')

const contract = require('../lib/contract.js')
const launch = require('../lib/launch.js')
const raw = require('../lib/rawFirst.js')
const scroll = require('../lib/scroll.js')
const waits = require('../lib/waits.js')
const { ProfileHeld } = require('../lib/profileLock.js')

const EXIT = contract.get('exit_codes')

function usage(message) {
  console.error(`${message}\nusage: harvest-page.js <url> <id> [--dir DIR] [--parser MODULE] [--headful] [--reparse] [--no-wall]`)
  process.exit(EXIT.error)
}

function parseArgs(argv) {
  const flags = new Set(argv.filter((a) => a.startsWith('--')))
  const positional = argv.filter((a) => !a.startsWith('--'))
  const valueOf = (name, fallback) => {
    const i = argv.indexOf(name)
    return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback
  }
  // A --flag's value is positional-looking; drop the two we accept.
  for (const name of ['--dir', '--parser']) {
    const i = argv.indexOf(name)
    if (i >= 0 && argv[i + 1]) {
      const idx = positional.indexOf(argv[i + 1])
      if (idx >= 0) positional.splice(idx, 1)
    }
  }
  for (const name of ['--attempts', '--interval']) {
    const i = argv.indexOf(name)
    if (i >= 0 && argv[i + 1]) {
      const idx = positional.indexOf(argv[i + 1])
      if (idx >= 0) positional.splice(idx, 1)
    }
  }
  return {
    url: positional[0],
    id: positional[1],
    dir: path.resolve(valueOf('--dir', 'raw')),
    parserPath: valueOf('--parser', null),
    headful: flags.has('--headful'),
    reparse: flags.has('--reparse'),
    noWall: flags.has('--no-wall'),
    // How long to wait out a wall. Lower them for a smoke run; the defaults
    // come from the contract and suit a real challenge.
    attempts: Number(valueOf('--attempts', 0)) || undefined,
    intervalMs: Number(valueOf('--interval', 0)) || undefined,
  }
}

function loadParser(parserPath) {
  if (!parserPath) return require('../parsers/generic.js').parse
  const mod = require(path.resolve(parserPath))
  const fn = typeof mod === 'function' ? mod : mod.parse
  if (typeof fn !== 'function') throw new Error(`${parserPath} exports no parse function`)
  return fn
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  if (!args.id) usage('need <url> <id>')

  let parse
  try {
    parse = loadParser(args.parserPath)
  } catch (err) {
    usage(String(err.message || err))
  }

  if (args.reparse) {
    const parsed = raw.reparse(args.dir, args.id, parse)
    console.log(JSON.stringify({ ok: true, reparsed: args.id, title: parsed.title || null }))
    return EXIT.ok
  }

  if (!args.url) usage('need <url> for a live fetch')

  let session
  try {
    session = await launch.open({ headful: args.headful })
  } catch (err) {
    if (err instanceof ProfileHeld) {
      console.error(String(err.message))
      return EXIT.error
    }
    throw err
  }

  try {
    const { page } = session
    try {
      await page.goto(args.url, {
        waitUntil: 'networkidle2',
        timeout: contract.get('challenge.goto_timeout_ms'),
      })
    } catch (err) {
      console.error(`navigation failed: ${err.message || err}`)
      return EXIT.timeout
    }

    if (!args.noWall) {
      const budget = { attempts: args.attempts, intervalMs: args.intervalMs }
      const cleared = (await waits.titleNot(page, budget)) || (await waits.bodyTextAtLeast(page, budget))
      if (!cleared) {
        console.error('CHALLENGE_NOT_CLEARED')
        return EXIT.challenge_not_cleared
      }
    }

    await scroll.hydrate(page, 'text')

    const html = await page.content()
    const parsed = raw.harvest(args.dir, args.id, html, parse, {
      url: args.url,
      fetched_at: new Date().toISOString(),
    })
    console.log(
      JSON.stringify({ ok: true, id: args.id, bytes: html.length, title: parsed.title || null })
    )
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
