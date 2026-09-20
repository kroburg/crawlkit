"""ck-drive — run a fetch command over a list of ids, politely and resumably.

    ck-drive worklist.json --dir raw -- node/bin/harvest-page.js {url} {id}

Everything after `--` is the command template; {id} and {url} are substituted
per item. The work-list is a JSON array of {"id": ..., "url": ...} objects.
"""

import argparse
import json
import sys
from pathlib import Path

from crawlkit import drive
from crawlkit.exits import Exit


def load_items(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = []
    for entry in data:
        if isinstance(entry, str):
            items.append({"id": entry, "url": entry})
        else:
            items.append(entry)
    missing = [e for e in items if not e.get("id")]
    if missing:
        raise ValueError(f"{len(missing)} work-list entries have no id")
    return items


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    template = []
    if "--" in argv:
        split = argv.index("--")
        argv, template = argv[:split], argv[split + 1 :]

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("worklist", help="JSON array of {id, url}")
    ap.add_argument("--dir", default="raw", help="where the sentinel files live")
    ap.add_argument("--attempts", type=int, default=None)
    ap.add_argument("--backoff", type=float, default=None, metavar="SECONDS")
    ap.add_argument("--jitter", default=None, metavar="LO:HI", help="seconds between items")
    ap.add_argument("--timeout", type=float, default=None, metavar="SECONDS", help="per attempt")
    args = ap.parse_args(argv)

    if not template:
        ap.error("append -- followed by the fetch command, using {id} and {url}")

    items = load_items(args.worklist)
    jitter_range = None
    if args.jitter:
        lo, _, hi = args.jitter.partition(":")
        jitter_range = (float(lo), float(hi or lo))

    def build(entry):
        return [part.format(id=entry["id"], url=entry.get("url", "")) for part in template]

    def report(event, data):
        print(f"{event}: {json.dumps(data, ensure_ascii=False)}", file=sys.stderr)

    summary = drive.harvest_all(
        [(entry["id"], entry) for entry in items],
        lambda item: build(item[1]),
        args.dir,
        attempts=args.attempts,
        backoff_s=args.backoff,
        jitter_range=jitter_range,
        timeout_s=args.timeout,
        on_event=report,
    )
    print(
        f"done {len(summary['done'])}  skipped {len(summary['skipped'])}  failed {len(summary['failed'])}",
        file=sys.stderr,
    )
    if summary["failed"]:
        print("failed: " + ", ".join(summary["failed"]), file=sys.stderr)
    return int(Exit.OK if not summary["failed"] else Exit.ERROR)


if __name__ == "__main__":
    raise SystemExit(main())
