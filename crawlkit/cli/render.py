"""ck-render — render a URL with a browser and print the HTML.

Exit codes are real integers, which takes deliberate effort — `sys.exit(str)`
prints to stderr and exits 1 no matter what a docstring promises:
  0 rendered   1 setup/unknown   2 navigation or selector timeout
  3 challenge never cleared (only with --require-growth)
"""

import argparse
import sys

from crawlkit import render
from crawlkit.exits import Exit, die


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--out", help="write here instead of stdout")
    ap.add_argument("--timeout", type=int, default=None, metavar="MS")
    ap.add_argument(
        "--min-body",
        type=int,
        default=None,
        help="keep waiting until rendered body text exceeds this many characters",
    )
    ap.add_argument("--wait", help="CSS selector to wait for instead of the body-growth heuristic")
    ap.add_argument(
        "--resolve",
        action="append",
        default=[],
        metavar="HOST:IP",
        help="pin DNS for HOST (repeatable; use when `dig @1.1.1.1 HOST` answers "
        "but the page will not load). Accepts [::1] for IPv6.",
    )
    ap.add_argument(
        "--require-growth",
        action="store_true",
        help=f"exit {int(Exit.CHALLENGE_NOT_CLEARED)} instead of saving a challenge stub",
    )
    args = ap.parse_args(argv)

    try:
        html = render.fetch(
            args.url,
            min_body=args.min_body,
            wait_selector=args.wait,
            timeout_ms=args.timeout,
            resolve=args.resolve or None,
            require_growth=args.require_growth,
        )
    except render.RenderError as exc:
        die(exc.code, str(exc))
    except ValueError as exc:  # bad --resolve entry
        die(Exit.ERROR, str(exc))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(html)
    else:
        sys.stdout.write(html)
    return int(Exit.OK)


if __name__ == "__main__":
    raise SystemExit(main())
