'use strict'
// Makes "run the harvest sequentially" an enforced invariant instead of a
// comment somebody will eventually not read.
//
// Two Chromes on one user-data dir is the worst failure mode in this toolkit:
// the profile gets corrupted or the requests interleave, the wall flags the
// session, and you find out hours later on a different host with no evidence
// left. A documented requirement does not survive reuse; an O_EXCL lockfile
// does — the second process fails immediately, saying who holds it.

const fs = require('fs')
const path = require('path')

const STALE_MS = 30 * 60 * 1000

class ProfileHeld extends Error {}

function alive(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch (err) {
    return err.code === 'EPERM'
  }
}

class ProfileLock {
  constructor(file) {
    this.file = file
    this.released = false
  }

  static path(dir) {
    return path.join(dir, '.crawlkit-harvest.lock')
  }

  static read(file) {
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'))
    } catch {
      return null
    }
  }

  static acquire(dir) {
    const file = ProfileLock.path(dir)
    fs.mkdirSync(dir, { recursive: true })
    try {
      return ProfileLock._write(file)
    } catch (err) {
      if (err.code !== 'EEXIST') throw err
    }

    const held = ProfileLock.read(file)
    const stale =
      !held ||
      !alive(held.pid) ||
      Date.now() - Date.parse(held.at || 0) > STALE_MS
    if (!stale) {
      throw new ProfileHeld(
        `profile ${dir} is in use by pid ${held.pid} since ${held.at}. ` +
          'Harvest sequentially: parallel Chromes on one profile trip the wall.'
      )
    }
    // A crashed run leaves the file behind; reclaim it rather than wedging.
    fs.rmSync(file, { force: true })
    return ProfileLock._write(file)
  }

  static _write(file) {
    const handle = fs.openSync(file, 'wx')
    fs.writeFileSync(handle, JSON.stringify({ pid: process.pid, at: new Date().toISOString() }))
    fs.closeSync(handle)
    return new ProfileLock(file)
  }

  release() {
    if (this.released) return
    this.released = true
    fs.rmSync(this.file, { force: true })
  }
}

module.exports = { ProfileLock, ProfileHeld, STALE_MS }
