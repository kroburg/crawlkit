"""Process exit codes, shared with the Node side via the contract.

Documenting a failure code is not producing one. `sys.exit("some message")`
prints to stderr and exits 1, so a renderer can promise three distinct codes
and deliver one. A driver script therefore could not tell a bot-wall that
never cleared from a crashed browser, which is exactly the distinction that
decides whether retrying is worth anything.
"""

import sys
from enum import IntEnum

from crawlkit import contract


class Exit(IntEnum):
    OK = contract.get("exit_codes.ok")
    ERROR = contract.get("exit_codes.error")
    TIMEOUT = contract.get("exit_codes.timeout")
    CHALLENGE_NOT_CLEARED = contract.get("exit_codes.challenge_not_cleared")


def die(code, message, stream=None):
    """Write `message` to stderr and exit with an integer code.

    `code` accepts an Exit or a bare int so callers need not import the enum.
    """
    print(message, file=stream or sys.stderr)
    raise SystemExit(int(code))
