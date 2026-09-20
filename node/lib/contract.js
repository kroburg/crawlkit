'use strict'
// Reads the SAME constants.json the Python package reads. Not a copy, not a
// mirror, not a generated file — the literal file, resolved relative to the
// checkout. tests/test_contract_parity.py deep-compares what the two runtimes
// see, so if this path ever breaks the suite fails instead of the two halves
// silently drifting apart — the failure mode being one runtime pinned to one
// Chrome version and the other to a different one, with nothing to notice.

const fs = require('fs')
const path = require('path')

const PATH = path.join(__dirname, '..', '..', 'crawlkit', 'contract', 'constants.json')

let cache = null

function all() {
  if (!cache) cache = JSON.parse(fs.readFileSync(PATH, 'utf8'))
  return cache
}

function get(dotted, fallback) {
  let node = all()
  for (const part of dotted.split('.')) {
    if (node === null || typeof node !== 'object' || !(part in node)) {
      if (arguments.length > 1) return fallback
      throw new Error(`${dotted} not in ${PATH}`)
    }
    node = node[part]
  }
  return node
}

function ua(name = 'desktop_chrome') {
  const value = get(`user_agents.${name}`)
  if (/headless/i.test(value)) throw new Error(`user agent advertises headless: ${value}`)
  return value
}

module.exports = { PATH, all, get, ua }
