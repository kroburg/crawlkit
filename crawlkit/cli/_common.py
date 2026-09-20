"""Argparse conventions shared by the ck-* commands.

These live here rather than in the agents package because a library module
should not know what a command line is. The emitter's job is to produce text;
deciding that the flag is spelled `--dry-run` is this layer's business.
"""

import json
import sys


def add_selection_arguments(parser, item_flag="--only"):
    parser.add_argument("--dry-run", action="store_true", help="show what would happen, do nothing")
    parser.add_argument(item_flag, help="act on one item only (to re-dispatch a single failure)")
    parser.add_argument("--reverify", action="store_true", help="include items already done")
    return parser


def add_report_arguments(parser):
    parser.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    parser.add_argument("--quiet", action="store_true", help="suppress the per-item log")
    return parser


def report(payload, as_json=False, stream=None):
    """One reporting convention for every command."""
    out = stream or sys.stderr
    if as_json:
        json.dump(payload, out, ensure_ascii=False, indent=2, sort_keys=True)
        out.write("\n")
        return
    for key, value in payload.items():
        print(f"{key}: {value}", file=out)


def die(parser, message):
    parser.error(message)
