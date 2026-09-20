"""Raw bytes to disk before anything tries to understand them.

A fetch that got through a bot wall is the expensive artifact; a parser is
cheap and will be wrong at least once. So the raw response is written first,
unconditionally, and only then parsed. Two things follow, and both are the
reason this discipline is worth a module:

  * a parser crash costs nothing — `reparse` re-runs it over the cached bytes
    with no browser and no network at all;
  * the *parsed* file, not the raw one, is the completion sentinel, so a
    driver's skip-if-present check cannot mistake a half-finished item for a
    finished one.

Both runtimes use this layout, so either can reparse what the other fetched.
"""

import json
from pathlib import Path


def raw_path(directory, ident, suffix=".html"):
    return Path(directory) / f"{ident}{suffix}"


def sentinel_path(directory, ident):
    return Path(directory) / f"{ident}.json"


def sentinel_ok(directory, ident):
    """Non-empty, not merely present: a zero-byte file is an interrupted run."""
    path = sentinel_path(directory, ident)
    return path.exists() and path.stat().st_size > 0


def write_raw(directory, ident, raw, suffix=".html"):
    Path(directory).mkdir(parents=True, exist_ok=True)
    path = raw_path(directory, ident, suffix)
    if isinstance(raw, bytes):
        path.write_bytes(raw)
    else:
        path.write_text(raw, encoding="utf-8")
    return path


def write_parsed(directory, ident, parsed):
    path = sentinel_path(directory, ident)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def read_raw(directory, ident, suffix=".html"):
    return raw_path(directory, ident, suffix).read_text(encoding="utf-8")


def read_parsed(directory, ident):
    return json.loads(sentinel_path(directory, ident).read_text(encoding="utf-8"))


def harvest(directory, ident, raw, parse, meta=None, suffix=".html"):
    """Write raw, then parse, then write parsed. Raw survives a parser crash."""
    write_raw(directory, ident, raw, suffix)
    parsed = dict(parse(raw) or {})
    parsed.setdefault("id", ident)
    if meta:
        parsed.update(meta)
    write_parsed(directory, ident, parsed)
    return parsed


def reparse(directory, ident, parse, suffix=".html"):
    """Re-run a parser over cached bytes. No browser, no network, no wall."""
    raw = read_raw(directory, ident, suffix)
    previous = read_parsed(directory, ident) if sentinel_path(directory, ident).exists() else {}
    parsed = dict(parse(raw) or {})
    parsed.setdefault("id", ident)
    # Carry forward provenance the parser does not produce (notably the URL,
    # so a reparse can be invoked with only an id).
    for key in ("url", "fetched_at"):
        if key in previous and key not in parsed:
            parsed[key] = previous[key]
    write_parsed(directory, ident, parsed)
    return parsed


def pending(directory, idents):
    return [ident for ident in idents if not sentinel_ok(directory, ident)]
