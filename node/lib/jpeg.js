'use strict'
// Byte-level validity, and the half everyone forgets.
//
// Checking the SOI magic proves you received *a* JPEG. Proving you received
// *all* of it needs the EOI marker: a connection reset mid-image, or a
// partially buffered CDP payload, passes the header test and fails this one.
// Without it the file lands on disk looking fine and the damage only shows up
// as a gray band when a human finally opens it.
//
// But "last two bytes are FFD9" is too strict, and real data proves it: a
// camera JPEG can carry ~10,000 bytes of plain-text sensor log appended after
// the image stream, and a last-two-bytes check calls that file corrupt. So we
// look for the EOI *near* the end instead.
//
// Scanning for the marker is safe rather than lucky: inside entropy-coded scan
// data a 0xFF byte is always stuffed as FF 00, so a bare FF D9 cannot occur by
// accident. The only decoy is the EOI of an EXIF thumbnail, which sits near the
// START of the file — hence the requirement that the marker be within
// trailerAllowance bytes of the end, not merely present somewhere.

const contract = require('./contract.js')

const MIN_BYTES = contract.get('media.min_jpeg_bytes')
const TRAILER_ALLOWANCE = 65536

function eoiOffset(buf, trailerAllowance = TRAILER_ALLOWANCE) {
  const from = Math.max(0, buf.length - trailerAllowance)
  const at = buf.lastIndexOf(Buffer.from([0xff, 0xd9]), buf.length)
  return at >= from ? at : -1
}

function hasSoi(buf) {
  return Boolean(buf && buf.length > 3 && buf[0] === 0xff && buf[1] === 0xd8)
}

function isValidJpeg(buf, minBytes = MIN_BYTES, trailerAllowance = TRAILER_ALLOWANCE) {
  return Boolean(buf && buf.length > minBytes && hasSoi(buf) && eoiOffset(buf, trailerAllowance) > 0)
}

function describe(buf, minBytes = MIN_BYTES) {
  if (!buf || !buf.length) return 'empty'
  if (!hasSoi(buf)) return 'not a jpeg'
  const at = eoiOffset(buf)
  if (at < 0) return 'truncated (no EOI)'
  if (buf.length <= minBytes) return `too small (${buf.length}b)`
  const trailing = buf.length - at - 2
  return trailing > 0 ? `ok (${trailing}b trailing after EOI)` : 'ok'
}

module.exports = { isValidJpeg, describe, hasSoi, eoiOffset, MIN_BYTES, TRAILER_ALLOWANCE }
