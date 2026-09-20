'use strict'
// Pure units: no browser, no server.

const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const os = require('os')
const path = require('path')

const jpeg = require('../lib/jpeg.js')
const raw = require('../lib/rawFirst.js')
const generic = require('../parsers/generic.js')
const endpoints = require('../lib/endpoints.js')

const SOI = Buffer.from([0xff, 0xd8])
const EOI = Buffer.from([0xff, 0xd9])
const body = (n) => Buffer.alloc(n, 0x41)

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ck-raw-'))
}

// -- jpeg validity -------------------------------------------------------

test('a complete jpeg passes', () => {
  assert.ok(jpeg.isValidJpeg(Buffer.concat([SOI, body(20000), EOI])))
})

test('a truncated jpeg fails on the tail even though the header is right', () => {
  const cut = Buffer.concat([SOI, body(20000)])
  assert.ok(!jpeg.isValidJpeg(cut))
  assert.strictEqual(jpeg.describe(cut), 'truncated (no EOI)')
})

test('a thumbnail-sized payload fails the byte floor', () => {
  assert.ok(!jpeg.isValidJpeg(Buffer.concat([SOI, body(50), EOI])))
})

test('a complete jpeg with trailing data after EOI is still valid', () => {
  // Real case: a camera file carrying ~10KB of plain-text
  // sensor log appended after the image stream. A strict last-two-bytes check
  // calls it corrupt and the harvest loses a good photo.
  const withTrailer = Buffer.concat([SOI, body(20000), EOI, Buffer.from('F/W Version: 0.32\nCAL: M:18\n')])
  assert.ok(jpeg.isValidJpeg(withTrailer))
  assert.match(jpeg.describe(withTrailer), /trailing after EOI/)
})

test('an EOI far from the end does not rescue a truncated file', () => {
  // The decoy is an EXIF thumbnail's own EOI near the START of the file; a
  // scan cut mid-image must still be rejected.
  const thumbnailEoiThenCut = Buffer.concat([SOI, body(400), EOI, body(200000)])
  assert.ok(!jpeg.isValidJpeg(thumbnailEoiThenCut))
  assert.strictEqual(jpeg.describe(thumbnailEoiThenCut), 'truncated (no EOI)')
})

test('a non-jpeg body is named as such', () => {
  assert.strictEqual(jpeg.describe(Buffer.from('<html>403</html>')), 'not a jpeg')
})

// -- raw-first -----------------------------------------------------------

test('raw survives a parser that throws', () => {
  const dir = tmpdir()
  assert.throws(() =>
    raw.harvest(dir, 'p', '<html>costly</html>', () => {
      throw new Error('parser bug')
    })
  )
  assert.strictEqual(raw.readRaw(dir, 'p'), '<html>costly</html>')
  assert.ok(!raw.sentinelOk(dir, 'p'))
})

test('reparse fixes the record with no browser and keeps provenance', () => {
  const dir = tmpdir()
  raw.harvest(dir, 'p', '<h1>Hi</h1>', () => ({ title: null }), { url: 'http://h/p' })
  const fixed = raw.reparse(dir, 'p', (html) => ({ title: html.match(/<h1>(.*?)<\/h1>/)[1] }))
  assert.strictEqual(fixed.title, 'Hi')
  assert.strictEqual(fixed.url, 'http://h/p')
})

test('an empty sentinel counts as unfinished', () => {
  const dir = tmpdir()
  fs.writeFileSync(raw.sentinelPath(dir, 'p'), '')
  assert.ok(!raw.sentinelOk(dir, 'p'))
})

// -- parser toolkit ------------------------------------------------------

test('title and ld+json are extracted, bad json blocks skipped', () => {
  const html = `<title>T &amp; T</title>
    <script type="application/ld+json">{"a":1}</script>
    <script type="application/ld+json">{oops}</script>`
  assert.strictEqual(generic.title(html), 'T & T')
  assert.deepStrictEqual(generic.ldJson(html), [{ a: 1 }])
})

test('text lines drop scripts and styles', () => {
  const lines = generic.textLines('<style>.a{}</style><p>one</p><script>var x=1</script><p>two</p>')
  assert.deepStrictEqual(lines, ['one', 'two'])
})

test('attrs collects every matching attribute', () => {
  assert.deepStrictEqual(generic.attrs('<img src="a.jpg"><img src="b.jpg">', 'img', 'src'), [
    'a.jpg',
    'b.jpg',
  ])
})

test('entities including numeric ones are decoded', () => {
  assert.strictEqual(generic.decodeEntities('caf&#233; &amp; &#x43f;'), 'café & п')
})

// -- endpoint filters ----------------------------------------------------

test('asset and analytics filters keep only the site own traffic', () => {
  assert.ok(endpoints.ASSET.test('https://h/logo.png?v=2'))
  assert.ok(endpoints.THIRD_PARTY.test('https://www.google-analytics.com/collect'))
  assert.ok(!endpoints.ASSET.test('https://h/api/items?format=png_list'))
})
