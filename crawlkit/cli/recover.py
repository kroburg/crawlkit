"""ck-recover — salvage a fanout that died before anyone collected it.

Report-only by default. With --out it writes each recovered answer plus an
index, and that index doubles as the --agent-ids argument for ck-ingest, so the
recovered work still goes through the same authorization as anything else.
"""

import argparse
import json
import sys
from pathlib import Path

from crawlkit.agents import recover
from crawlkit.cli import _common
from crawlkit.exits import Exit


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(recover.DEFAULT_ROOT), help="session tree to search")
    ap.add_argument("--project", help="limit to one project directory")
    ap.add_argument("--session", help="limit to sessions whose path contains this")
    ap.add_argument("--agent-ids", help="comma-separated id prefixes to limit the search")
    ap.add_argument("--out", help="write recovered answers and an index here")
    _common.add_report_arguments(ap)
    args = ap.parse_args(argv)

    ids = [part.strip() for part in (args.agent_ids or "").split(",") if part.strip()]
    found = recover.recover(args.root, project=args.project, session=args.session, agent_ids=ids)
    summary = recover.summarize(found)

    if not args.quiet:
        print(recover_table(found), file=sys.stderr)
    if args.json:
        _common.report(summary, as_json=True, stream=sys.stdout)

    if args.out:
        directory = Path(args.out)
        directory.mkdir(parents=True, exist_ok=True)
        index = {}
        for result in recover.to_results(found):
            (directory / f"{result.item_id}.txt").write_text(result.text, encoding="utf-8")
            index[result.agent_id] = {"item_id": result.item_id, "source": result.source}
        (directory / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8"
        )
        # index.json travels with the files so ck-ingest can map a recovered
        # filename (named for the item) back to the agent that produced it.
        print(
            f"{len(index)} recovered -> {directory}\n"
            f"ck-ingest {directory} --agent-ids "
            f"{','.join(sorted(index)) or '<none>'} --into records.json",
            file=sys.stderr,
        )

    return int(Exit.OK if summary["recoverable"] else Exit.ERROR)


def recover_table(found):
    lines = [f"{'agent':<20} {'target':<24} {'how':<12} reason"]
    for item in sorted(found, key=lambda entry: entry.agent_id):
        lines.append(
            f"{item.agent_id[:19]:<20} {str(item.target)[:23]:<24} "
            f"{str(item.identified_by or '-'):<12} {item.reason}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
