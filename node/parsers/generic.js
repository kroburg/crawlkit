'use strict'
// A parser toolkit, not a parser. Everything here is domain-free: the field
// names in any real harvest belong in your own module, which you pass to
// harvest-page.js with --parser.
//
// Regex over the HTML string rather than a DOM: these run against cached bytes
// in reparse mode where no browser exists, and the shapes below (LD+JSON,
// <title>, a heading-delimited section) are stable enough that a parser
// dependency buys little.

function title(html) {
  const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)
  return m ? decodeEntities(m[1].trim()) : null
}

/** Every application/ld+json block, parsed; unparseable blocks are skipped. */
function ldJson(html) {
  const out = []
  const re = /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi
  let m
  while ((m = re.exec(html))) {
    try {
      out.push(JSON.parse(m[1].trim()))
    } catch {}
  }
  return out
}

/** Visible-ish text: scripts and styles dropped, entities decoded, collapsed. */
function textLines(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li|tr|h[1-6])>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .split('\n')
    .map((line) => decodeEntities(line).replace(/[ \t ]+/g, ' ').trim())
    .filter(Boolean)
}

/** The slice between two markers — the workhorse for heading-delimited pages. */
function sliceBetween(html, start, end) {
  const i = html.search(start instanceof RegExp ? start : new RegExp(escape(start), 'i'))
  if (i < 0) return null
  const rest = html.slice(i)
  const j = end ? rest.search(end instanceof RegExp ? end : new RegExp(escape(end), 'i')) : -1
  return j > 0 ? rest.slice(0, j) : rest
}

/** Attribute values for every matching tag, e.g. srcs = attrs(html, 'img', 'src'). */
function attrs(html, tag, name) {
  const out = []
  const re = new RegExp(`<${tag}\\b[^>]*>`, 'gi')
  let m
  while ((m = re.exec(html))) {
    const a = m[0].match(new RegExp(`${name}=["']([^"']+)["']`, 'i'))
    if (a) out.push(decodeEntities(a[1]))
  }
  return out
}

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', '#39': "'" }

function decodeEntities(text) {
  return String(text).replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (whole, code) => {
    const key = code.toLowerCase()
    if (ENTITIES[key] !== undefined) return ENTITIES[key]
    if (key.startsWith('#x')) return String.fromCodePoint(parseInt(key.slice(2), 16))
    if (key.startsWith('#')) return String.fromCodePoint(parseInt(key.slice(1), 10))
    return whole
  })
}

function escape(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Default parser: enough to prove a fetch worked, not enough to pretend it is yours. */
function parse(html) {
  const lines = textLines(html)
  return {
    title: title(html),
    text_chars: lines.join('\n').length,
    line_count: lines.length,
    ld_json: ldJson(html),
  }
}

module.exports = { parse, title, ldJson, textLines, sliceBetween, attrs, decodeEntities }
