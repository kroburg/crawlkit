#!/usr/bin/env python3
"""One fetch, called per item by ck-drive. Stores raw-first via crawlkit.rawstore.

crawlkit.drive knows nothing about how an item is actually fetched — it runs
whatever command comes after `--` and treats a non-empty sentinel file as
"done". This script IS that command for the example: a plain urllib GET, so
the example needs nothing beyond the standard library and the fixture server.
"""

import argparse
import urllib.request

from crawlkit import rawstore


def parse(raw):
    return {"bytes": len(raw)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("url")
    ap.add_argument("--dir", default="raw")
    args = ap.parse_args()

    with urllib.request.urlopen(args.url, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    rawstore.harvest(args.dir, args.id, raw, parse, meta={"url": args.url})


if __name__ == "__main__":
    main()
