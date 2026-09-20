"""ck-qa — ask whether a finished harvest is any good.

Four questions, one subcommand each. All of them run offline against records
already on disk, because every failure they detect looks like success at fetch
time: the request returned 200, the parser did not raise, the file has content.

    echo     did the extractor hand back its own input?
    census   which fields did this harvest fail to fill?
    agree    which values did two independent passes actually agree on?
    soft     is this page an error page wearing a 200?
"""

import argparse
import json
import sys
from pathlib import Path

from crawlkit.exits import Exit
from crawlkit.qa import agreement, census, echo, soft_error


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def as_records(data):
    return list(data.values()) if isinstance(data, dict) else list(data)


def cmd_echo(args):
    records = as_records(load(args.records))
    fields = [part.strip() for part in args.fields.split(",") if part.strip()]
    found = echo.scan_records(records, fields, key=args.key)
    for item in found:
        print(f"{item.record_id}.{item.field}: {item.value[:70]!r} — {', '.join(item.reasons)}")
    print(f"{len(found)} echoed values in {len(records)} records", file=sys.stderr)
    return Exit.ERROR if found else Exit.OK


def cmd_census(args):
    records = as_records(load(args.records))
    report = census.census(records, key=args.key)
    print(report.render())
    thin = report.thin(args.floor)
    if thin:
        print(f"below {args.floor:.0%}: {', '.join(thin)}", file=sys.stderr)

    if args.against:
        before = census.census(as_records(load(args.against)), key=args.key)
        deltas = census.compare(before, report)
        regressions = {name: delta for name, delta in deltas.items() if delta < 0}
        if regressions:
            # A parser change that stops finding a field raises nothing and
            # produces a plausible-looking file. This is where it surfaces.
            for name, delta in sorted(regressions.items()):
                print(f"REGRESSION {name}: {delta:+.1%}", file=sys.stderr)
            return Exit.ERROR
    return Exit.ERROR if thin else Exit.OK


def cmd_agree(args):
    fields = [part.strip() for part in args.fields.split(",") if part.strip()]
    result = agreement.compare(
        as_records(load(args.pass_a)), as_records(load(args.pass_b)), fields, key=args.key
    )
    print(result.render())
    if args.into:
        Path(args.into).write_text(
            json.dumps(agreement.auto_applicable(result), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return Exit.ERROR if result.disputed else Exit.OK


def cmd_soft(args):
    bad = []
    for path in sorted(Path(args.pages).glob(args.glob)):
        suspect, reasons = soft_error.inspect(path.read_text(encoding="utf-8", errors="replace"))
        if suspect:
            bad.append((path.name, reasons))
            print(f"{path.name}: {', '.join(reasons)}")
    print(f"{len(bad)} soft errors", file=sys.stderr)
    return Exit.ERROR if bad else Exit.OK


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", default="id", help="record identity field")
    sub = ap.add_subparsers(dest="command", required=True)

    one = sub.add_parser("echo", help="fields that echo the extractor's input")
    one.add_argument("records")
    one.add_argument("--fields", default="title", help="comma-separated")
    one.set_defaults(run=cmd_echo)

    two = sub.add_parser("census", help="field fill rates, and regressions against a baseline")
    two.add_argument("records")
    two.add_argument("--against", help="an earlier records file to compare with")
    two.add_argument("--floor", type=float, default=0.5)
    two.set_defaults(run=cmd_census)

    three = sub.add_parser("agree", help="what two independent passes agree on")
    three.add_argument("pass_a")
    three.add_argument("pass_b")
    three.add_argument("--fields", required=True, help="comma-separated")
    three.add_argument("--into", help="write the auto-applicable values here")
    three.set_defaults(run=cmd_agree)

    four = sub.add_parser("soft", help="pages that are an error wearing a 200")
    four.add_argument("pages", help="directory of saved pages")
    four.add_argument("--glob", default="*.html")
    four.set_defaults(run=cmd_soft)

    args = ap.parse_args(argv)
    return int(args.run(args))


if __name__ == "__main__":
    raise SystemExit(main())
