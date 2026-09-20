"""Byte-level JPEG validity — the Python twin of node/lib/jpeg.js.

Kept in sync deliberately: the Node harvester decides what to write and this
decides what to keep, and if they disagree a file is saved by one and rejected
by the other. Pure stdlib, so it runs wherever the probe layer runs.

The end-of-image marker is looked for NEAR the end rather than exactly at it.
Strictly requiring the last two bytes to be FFD9 rejects real photographs: a
camera file can append ten kilobytes of plain-text sensor log
after the image stream. Scanning is safe rather than lucky — inside entropy
coded data a 0xFF is always stuffed as FF 00, so a bare FF D9 cannot occur by
accident — and the one decoy, an EXIF thumbnail's own EOI, sits near the start,
which is why the marker must fall inside the trailing allowance.
"""

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
MIN_BYTES = 10000
TRAILER_ALLOWANCE = 65536


def has_soi(data):
    return bool(data) and len(data) > 3 and data[:2] == SOI


def eoi_offset(data, trailer_allowance=TRAILER_ALLOWANCE):
    """Offset of the trailing EOI marker, or -1 if the file is cut short."""
    if not data:
        return -1
    at = data.rfind(EOI)
    return at if at >= 0 and at >= len(data) - trailer_allowance else -1


def is_valid(data, min_bytes=MIN_BYTES, trailer_allowance=TRAILER_ALLOWANCE):
    return bool(
        data and len(data) > min_bytes and has_soi(data) and eoi_offset(data, trailer_allowance) > 0
    )


def describe(data, min_bytes=MIN_BYTES):
    if not data:
        return "empty"
    if not has_soi(data):
        return "not a jpeg"
    at = eoi_offset(data)
    if at < 0:
        return "truncated (no EOI)"
    if len(data) <= min_bytes:
        return f"too small ({len(data)}b)"
    trailing = len(data) - at - 2
    return f"ok ({trailing}b trailing after EOI)" if trailing else "ok"


def strictly_terminated(data):
    """The old rule, kept only so a test can show what it costs."""
    return bool(data) and data[:2] == SOI and data[-2:] == EOI
