"""ck-probe — check every URL in a link-state file.

Sticky URLs are removed *before* host bucketing, so a confirmed-by-browser URL
costs no network, no thread, and does not consume its host's serial slot.
"""

import argparse
import sys

from crawlkit import linkstate, probe, schedule
from crawlkit.exits import Exit


def run(state, urls, check=probe.check_one, interval_s=None, max_hosts=None, report=None):
    """Returns [(url, status, probed)]."""
    say = report or (lambda line: print(line, file=sys.stderr))

    # One predicate decides this, shared with LinkState.resolve_status — the
    # partition happens here only so the survivors can be bucketed by host.
    sticky, to_probe = [], []
    for url in urls:
        if state.is_sticky(url):
            status = state.record(url)["http_status"]
            sticky.append((url, status, False))
            say(f"{status:>5}  {url}  (confirmed by rendering, not re-probed)")
        else:
            to_probe.append(url)

    probed = schedule.run(
        to_probe,
        check,
        interval_s=interval_s,
        max_hosts=max_hosts,
        on_result=lambda url, status: say(f"{status:>5}  {url}"),
    )
    results = sticky + [(url, status, True) for url, status in probed]
    for url, status, _ in results:
        state.set_http(url, status)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("state", help="path to the link-state JSON")
    ap.add_argument("--url", action="append", default=[], help="probe only these URLs (repeatable)")
    ap.add_argument("--interval", type=float, default=None, help="seconds between hits on one host")
    ap.add_argument("--max-hosts", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="probe but do not write the state file")
    args = ap.parse_args(argv)

    state = linkstate.LinkState(args.state)
    urls = args.url or sorted(state.data)
    if not urls:
        print(f"no URLs in {args.state}", file=sys.stderr)
        return int(Exit.OK)

    results = run(state, urls, interval_s=args.interval, max_hosts=args.max_hosts)
    if not args.dry_run:
        state.save()

    reachable = sum(1 for _, status, _ in results if status in probe.LIVE_HTTP)
    print(f"{reachable}/{len(results)} live", file=sys.stderr)
    return int(Exit.OK)


if __name__ == "__main__":
    raise SystemExit(main())
