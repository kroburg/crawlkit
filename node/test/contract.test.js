'use strict'
const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')

const contract = require('../lib/contract.js')

test('reads the python package file, not a vendored copy', () => {
  assert.ok(contract.PATH.includes('crawlkit'))
  assert.ok(fs.existsSync(contract.PATH))
})

test('dotted get throws on a typo but honours an explicit fallback', () => {
  assert.throws(() => contract.get('http.timeout_seconds'))
  assert.strictEqual(contract.get('http.timeout_seconds', 0), 0)
})

test('the shared user agent never advertises headless', () => {
  assert.ok(!/headless/i.test(contract.ua()))
})

test('exit codes match the documented integers', () => {
  assert.strictEqual(contract.get('exit_codes.challenge_not_cleared'), 3)
  assert.strictEqual(contract.get('exit_codes.ok'), 0)
})

test('scroll presets keep both tunings', () => {
  assert.strictEqual(contract.get('scroll.text.step_px'), 700)
  assert.strictEqual(contract.get('scroll.images.step_px'), 500)
})
