"""ck-ingest — take a fanout's replies back in, safely.

Requires the list of agent ids you just dispatched. That is not a convenience
argument: authorizing by directory listing is how a stale reply from an earlier
run overwrites a curated record, and there is no flag here that restores that
behaviour.

Exits non-zero if any reply was rejected, so a fanout that half-worked cannot
be mistaken for one that worked.
"""

import argparse
import json
import sys
from pathlib import Path

from crawlkit.agents import ingest, worklist
from crawlkit.cli import _common
from crawlkit.exits import Exit


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results", help="directory of agent reply files")
    ap.add_argument(
        "--agent-ids",
        required=True,
        help="comma-separated ids of the agents you dispatched (prefixes are fine). "
        "Required: ingest never trusts a directory listing.",
    )
    ap.add_argument("--into", required=True, help="write the accepted records here")
    ap.add_argument("--worklist", help="JSON array of {id}: enables the census gate")
    ap.add_argument("--maps", help="JSON {field: {old: new|null}} applied last")
    ap.add_argument("--marker", help="text the payload block must contain")
    ap.add_argument("--suffix", default=".json", help="reply file extension")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    _common.add_report_arguments(ap)
    args = ap.parse_args(argv)

    ids = [part.strip() for part in args.agent_ids.split(",") if part.strip()]
    if not ids:
        ap.error("--agent-ids is empty; name the agents you dispatched")

    results = ingest.read_results(args.results, suffix=args.suffix)
    if not results:
        print(f"no reply files in {args.results}", file=sys.stderr)
        return int(Exit.ERROR)

    report = ingest.ingest(results, ids, marker=args.marker, maps=load_json(args.maps))

    items = worklist.Worklist.load(args.worklist) if args.worklist else None
    outcome = ingest.apply(report, args.into, worklist=items, dry_run=args.dry_run)

    if not args.quiet:
        print(report.render(), file=sys.stderr)
        if outcome["census"]:
            print(outcome["census"].render(), file=sys.stderr)

    if args.json:
        _common.report(
            {
                "applied": len(report.applied),
                "written": outcome["written"],
                "rejected": report.counts,
                "census": outcome["census"].as_dict() if outcome["census"] else None,
            },
            as_json=True,
            stream=sys.stdout,
        )

    census_clean = outcome["census"].ok() if outcome["census"] else True
    return int(Exit.OK if report.ok() and census_clean else Exit.ERROR)


if __name__ == "__main__":
    raise SystemExit(main())
