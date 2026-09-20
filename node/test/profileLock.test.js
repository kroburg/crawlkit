'use strict'
// The invariant that is usually only written down in a comment.

const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const os = require('os')
const path = require('path')

const { ProfileLock, ProfileHeld } = require('../lib/profileLock.js')

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ck-profile-'))
}

test('a second harvester on the same profile fails fast instead of corrupting it', () => {
  const dir = tmpdir()
  const first = ProfileLock.acquire(dir)
  assert.throws(() => ProfileLock.acquire(dir), ProfileHeld)
  first.release()
  ProfileLock.acquire(dir).release()
})

test('the error names the holder and says why sequencing matters', () => {
  const dir = tmpdir()
  const held = ProfileLock.acquire(dir)
  try {
    ProfileLock.acquire(dir)
    assert.fail('expected ProfileHeld')
  } catch (err) {
    assert.match(err.message, new RegExp(`pid ${process.pid}`))
    assert.match(err.message, /sequentially/)
  }
  held.release()
})

test('a lock left behind by a dead process is reclaimed, not a permanent wedge', () => {
  const dir = tmpdir()
  // A pid that cannot be running: a crashed run must not block the next one.
  fs.writeFileSync(
    ProfileLock.path(dir),
    JSON.stringify({ pid: 2 ** 22, at: new Date().toISOString() })
  )
  const lock = ProfileLock.acquire(dir)
  assert.ok(lock)
  lock.release()
})

test('a stale lock from this pid still yields after the staleness window', () => {
  const dir = tmpdir()
  const old = new Date(Date.now() - 60 * 60 * 1000).toISOString()
  fs.writeFileSync(ProfileLock.path(dir), JSON.stringify({ pid: process.pid, at: old }))
  const lock = ProfileLock.acquire(dir)
  assert.ok(lock)
  lock.release()
})

test('release is idempotent and removes the file', () => {
  const dir = tmpdir()
  const lock = ProfileLock.acquire(dir)
  lock.release()
  lock.release()
  assert.ok(!fs.existsSync(ProfileLock.path(dir)))
})
