"""Exit codes must actually reach the shell.

The regression: a docstring promising `2  timeout / navigation error` and
`3  browser not installed` while every failure path calls `sys.exit("message")`,
which exits 1. The contract is then fiction, and a retry driver keyed on it
treats a permanent failure as retryable.
"""

import subprocess
import sys
import textwrap

import pytest

from crawlkit.exits import Exit, die


def test_die_writes_to_stderr_and_exits_the_integer(capsys):
    with pytest.raises(SystemExit) as caught:
        die(Exit.CHALLENGE_NOT_CLEARED, "CHALLENGE_NOT_CLEARED")
    assert caught.value.code == 3
    assert capsys.readouterr().err.strip() == "CHALLENGE_NOT_CLEARED"


def test_die_accepts_a_bare_int():
    with pytest.raises(SystemExit) as caught:
        die(2, "timed out")
    assert caught.value.code == 2


@pytest.mark.parametrize("code", [int(e) for e in Exit if e is not Exit.OK])
def test_code_survives_a_real_process_boundary(code):
    """SystemExit(str) exits 1 no matter what the docstring says — prove we don't."""
    script = textwrap.dedent(
        f"""
        from crawlkit.exits import die
        die({code}, "boom")
        """
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == code
    assert done.stderr.strip() == "boom"
