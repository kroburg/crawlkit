'use strict'
// The twists, driven through real Chrome against the local fixture.
//
// Each test names the naive approach it rules out, because that is the part
// worth keeping: the code is short, the reason it is shaped this way is not.

const { test, before, after } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFile } = require('child_process')

const fixture = require('./helpers/fixture.js')
const launch = require('../lib/launch.js')
const waits = require('../lib/waits.js')
const scroll = require('../lib/scroll.js')
const consent = require('../lib/consent.js')
const endpoints = require('../lib/endpoints.js')
const media = require('../lib/mediaCapture.js')
const { isValidJpeg } = require('../lib/jpeg.js')
const { callSameOrigin } = require('../lib/sameOrigin.js')
const raw = require('../lib/rawFirst.js')

const skip = fixture.hasChrome() ? false : 'branded Chrome not installed'

let server
before(async () => {
  server = await fixture.start()
})
after(() => server && server.stop())

function profile() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ck-prof-'))
}

async function session(opts = {}) {
  return launch.open({ profile: profile(), ...opts })
}

function run(script, args) {
  return new Promise((resolve) => {
    execFile(
      process.execPath,
      [path.join(__dirname, '..', 'bin', script), ...args],
      { cwd: path.join(__dirname, '..') },
      (err, stdout, stderr) => resolve({ code: err ? err.code : 0, stdout, stderr })
    )
  })
}

// -- the warm profile ----------------------------------------------------

test('a cookie earned in one process is still there in the next', { skip }, async () => {
  const dir = profile()
  const first = await launch.open({ profile: dir })
  await first.page.goto(`${server.base}/challenge/clears-after/3`)
  const earned = (await first.page.cookies()).find((c) => c.name === 'ck_session')
  await first.release()
  assert.ok(earned, 'fixture should have set a session cookie')

  // Same profile dir, brand new browser: this is what makes a warm session
  // cheap, and why the whole harvest must be sequential.
  const second = await launch.open({ profile: dir })
  await second.page.goto(`${server.base}/health`)
  const carried = (await second.page.cookies()).find((c) => c.name === 'ck_session')
  await second.release()
  assert.strictEqual(carried && carried.value, earned.value)
})

test('the launched browser does not advertise automation', { skip }, async () => {
  const s = await session()
  try {
    await s.page.goto(`${server.base}/health`)
    assert.strictEqual(await s.page.evaluate(() => navigator.webdriver), false)
    assert.ok(!/headless/i.test(await s.page.evaluate(() => navigator.userAgent)))
  } finally {
    await s.release()
  }
})

// -- clearing a wall -----------------------------------------------------

test('a warm session clears a counter wall across attempts', { skip }, async () => {
  const dir = profile()
  const s = await launch.open({ profile: dir })
  try {
    for (let i = 0; i < 4; i++) await s.page.goto(`${server.base}/challenge/clears-after/3`)
    assert.ok(await waits.bodyTextAtLeast(s.page, { minimum: 2000, attempts: 3, intervalMs: 200 }))
  } finally {
    await s.release()
  }
})

test('the title poll rides out the page reloading itself', { skip }, async () => {
  const s = await session()
  try {
    await s.page.goto(`${server.base}/challenge/autoreload`)
    assert.ok(await waits.titleNot(s.page, { attempts: 20, intervalMs: 500 }))
    assert.match(await s.page.content(), /autoreload-cleared/)
  } finally {
    await s.release()
  }
})

test('polling never reloads the wall', { skip }, async () => {
  const before = (await server.stats()).navigations['/challenge/never'] || 0
  const s = await session()
  try {
    await s.page.goto(`${server.base}/challenge/never`)
    assert.strictEqual(await waits.titleNot(s.page, { attempts: 3, intervalMs: 200 }), false)
  } finally {
    await s.release()
  }
  const after = (await server.stats()).navigations['/challenge/never'] || 0
  assert.strictEqual(after - before, 1, 'a reload would restart the proof-of-work')
})

// -- hydration -----------------------------------------------------------

test('scrolling reaches content a cached scrollHeight bound would miss', { skip }, async () => {
  const s = await session()
  try {
    await s.page.goto(`${server.base}/lazy`)
    const initial = await s.page.evaluate(() => document.body.scrollHeight)

    await scroll.hydrate(s.page, 'text', { delay_ms: 60, settle_ms: 400 })

    assert.ok(await s.page.$('#done'), 'the loop must extend as content appends')
    const grown = await s.page.evaluate(() => document.body.scrollHeight)
    assert.ok(grown > initial * 2, `page should have grown: ${initial} -> ${grown}`)
  } finally {
    await s.release()
  }
})

// -- same-origin API -----------------------------------------------------

test('an out-of-band request to the API is refused', { skip }, async () => {
  const res = await fetch(`${server.base}/api/items`)
  assert.strictEqual(res.status, 403)
})

test('the same request issued inside a cleared page succeeds', { skip }, async () => {
  const s = await session()
  try {
    await s.page.goto(`${server.base}/challenge/clears-after/1`)
    await s.page.goto(`${server.base}/challenge/clears-after/1`)
    const out = await callSameOrigin(s.page, '/api/items')
    assert.strictEqual(out.status, 200)
    assert.strictEqual(JSON.parse(out.body).items.length, 5)
  } finally {
    await s.release()
  }
})

test('an absolute URL is rejected: it would leave the origin behind', { skip }, async () => {
  const s = await session()
  try {
    await s.page.goto(`${server.base}/health`)
    await assert.rejects(() => callSameOrigin(s.page, `${server.base}/api/items`), /relative path/)
  } finally {
    await s.release()
  }
})

test('a malformed body comes back verbatim instead of throwing', { skip }, async () => {
  const s = await session()
  try {
    await s.page.goto(`${server.base}/health`)
    const out = await callSameOrigin(s.page, '/api/items/malformed')
    assert.strictEqual(out.status, 200)
    assert.throws(() => JSON.parse(out.body))
    assert.ok(out.body.length > 0, 'the artifact survives for inspection')
  } finally {
    await s.release()
  }
})

// -- discovery and consent ----------------------------------------------

test('endpoint discovery filters assets and analytics but keeps the API', { skip }, async () => {
  const s = await session()
  try {
    const seen = endpoints.recordRequests(s.page)
    await s.page.goto(`${server.base}/consent`, { waitUntil: 'networkidle2' })
    const clicked = await consent.dismiss(s.page)
    assert.strictEqual(clicked, 'i agree')
    assert.ok(await s.page.$eval('#content', (el) => el.style.display === 'block'))

    const urls = seen.urls()
    assert.ok(urls.some((u) => u.includes('/api/after-consent')), urls.join('\n'))
    assert.ok(!urls.some((u) => u.includes('/static/logo.png')))
    assert.ok(!urls.some((u) => u.includes('analytics.js')))
    assert.deepStrictEqual(urls, [...urls].sort(), 'stable order for diffing')
  } finally {
    await s.release()
  }
})

// -- media capture -------------------------------------------------------

test('credentialed capture beats an out-of-band download and keeps the largest', { skip }, async () => {
  const ident = 'aaaaaaaaaaaaaaaaaaaaaa1'
  const direct = await fetch(`${server.base}/media/${ident}?w=1400`)
  assert.strictEqual(direct.status, 403, 'the CDN requires the page referer')

  const s = await session()
  try {
    const captured = media.collect(s.page, {
      idFrom: (u) => {
        const m = u.match(/media\/([A-Za-z0-9]{20,})/)
        return m ? m[1] : null
      },
    })
    await s.page.goto(`${server.base}/lazy-images`, { waitUntil: 'networkidle2' })
    await scroll.hydrate(s.page, 'images', { delay_ms: 60, settle_ms: 400 })

    const small = captured.get(ident)
    assert.ok(small && isValidJpeg(small), 'the page own load should be captured')

    await media.requestHiRes(s.page, [`${server.base}/media/${ident}?w=1400`], { drainMs: 1200 })
    const best = captured.get(ident)
    assert.ok(best.length > small.length, 'the injected hi-res variant must win')

    for (const [id] of captured.best) {
      assert.ok(!id.endsWith('avatar'), 'avatars are filtered by URL shape')
    }
  } finally {
    await s.release()
  }
})

// -- the CLI -------------------------------------------------------------

test('harvest-page stores raw-first and reparses with no browser', { skip }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ck-harv-'))
  const first = await run('harvest-page.js', [`${server.base}/lazy`, 'lazypage', '--dir', dir, '--no-wall'])
  assert.strictEqual(first.code, 0, first.stderr)
  assert.ok(raw.sentinelOk(dir, 'lazypage'))
  assert.ok(fs.existsSync(raw.rawPath(dir, 'lazypage')))
  assert.strictEqual(raw.readParsed(dir, 'lazypage').title, 'Lazy')

  const again = await run('harvest-page.js', ['x', 'lazypage', '--dir', dir, '--reparse'])
  assert.strictEqual(again.code, 0, again.stderr)
  assert.match(again.stdout, /"reparsed":"lazypage"/)
  assert.strictEqual(raw.readParsed(dir, 'lazypage').url, `${server.base}/lazy`)
})

test('harvest-page exits 3 when the wall never clears', { skip }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ck-harv-'))
  const out = await run('harvest-page.js', [
    `${server.base}/challenge/never`, 'walled', '--dir', dir, '--attempts', '2', '--interval', '200',
  ])
  assert.strictEqual(out.code, 3, out.stderr)
  assert.match(out.stderr, /CHALLENGE_NOT_CLEARED/)
  assert.ok(!raw.sentinelOk(dir, 'walled'), 'a stub must not be recorded as harvested')
})
