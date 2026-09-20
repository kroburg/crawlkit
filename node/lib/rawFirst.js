'use strict'
// Node half of the raw-first contract. Same layout as crawlkit/rawstore.py, so
// either runtime can reparse what the other fetched — tested in both
// directions by tests/test_rawstore_cross.py.

const fs = require('fs')
const path = require('path')

const rawPath = (dir, id, suffix = '.html') => path.join(dir, `${id}${suffix}`)
const sentinelPath = (dir, id) => path.join(dir, `${id}.json`)

function sentinelOk(dir, id) {
  // Non-empty, not merely present: a zero-byte file is an interrupted run.
  try {
    return fs.statSync(sentinelPath(dir, id)).size > 0
  } catch {
    return false
  }
}

function writeRaw(dir, id, raw, suffix = '.html') {
  fs.mkdirSync(dir, { recursive: true })
  const p = rawPath(dir, id, suffix)
  fs.writeFileSync(p, raw)
  return p
}

function writeParsed(dir, id, parsed) {
  fs.mkdirSync(dir, { recursive: true })
  const p = sentinelPath(dir, id)
  fs.writeFileSync(p, JSON.stringify(sortKeys(parsed), null, 2) + '\n')
  return p
}

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((k) => [k, sortKeys(value[k])])
    )
  }
  return value
}

function readRaw(dir, id, suffix = '.html') {
  return fs.readFileSync(rawPath(dir, id, suffix), 'utf8')
}

function readParsed(dir, id) {
  return JSON.parse(fs.readFileSync(sentinelPath(dir, id), 'utf8'))
}

/** Raw to disk FIRST, then parse. A parser crash costs no refetch. */
function harvest(dir, id, raw, parse, meta = {}) {
  writeRaw(dir, id, raw)
  const parsed = { id, ...(parse(raw) || {}), ...meta }
  writeParsed(dir, id, parsed)
  return parsed
}

/** Re-run a parser over cached bytes: no browser, no network, no wall. */
function reparse(dir, id, parse) {
  const raw = readRaw(dir, id)
  let previous = {}
  try {
    previous = readParsed(dir, id)
  } catch {}
  const parsed = { id, ...(parse(raw) || {}) }
  for (const key of ['url', 'fetched_at']) {
    if (previous[key] !== undefined && parsed[key] === undefined) parsed[key] = previous[key]
  }
  writeParsed(dir, id, parsed)
  return parsed
}

module.exports = { rawPath, sentinelPath, sentinelOk, writeRaw, writeParsed, readRaw, readParsed, harvest, reparse }
