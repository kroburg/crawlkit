"""Framing one dispatchable prompt per block.

Two details that matter more than they look:

* Each block carries a header naming the run and the item. The run id is not
  decoration — it is what lets a recovery tool identify which target a dead
  agent was working on, instead of regexing the interpolated id back out of
  the prompt body and hoping the phrasing never changed.
* A `--dry-run` that prints the work-list without the prompt bodies, so you can
  see what a fanout is about to dispatch before it dispatches it.
"""

import datetime
import hashlib

from crawlkit import contract

RULE_WIDTH = contract.get("fanout.emission_rule_width")
# Shared with the Node workflows, so an agent dispatched from either runtime
# writes the token recovery reads back.
MARKER = contract.get("fanout.marker")


def run_id(label, when=None):
    stamp = (when or datetime.datetime.now()).strftime("%Y%m%dT%H%M")
    digest = hashlib.sha1(f"{label}:{stamp}".encode()).hexdigest()[:6]
    return f"{label}-{stamp}-{digest}"


def block(prompt, item_id, run=None, group=None):
    """One framed, dispatchable prompt."""
    rule = "=" * RULE_WIDTH
    name = f"{group}/{item_id}" if group else item_id
    header = f"# {MARKER}: {name}" + (f"  run={run}" if run else "")
    # The marker line is repeated inside the prompt so it survives into the
    # agent's own transcript, where recovery can find it.
    tag = f"[{MARKER}: {name}]"
    return f"{rule}\n{header}\n{rule}\n{tag}\n{prompt}\n"


def emit(prompts, run=None, group=None, out=None):
    """prompts: iterable of (item_id, prompt_text). Returns the emitted text."""
    text = "\n".join(block(prompt, item_id, run, group) for item_id, prompt in prompts)
    if out:
        out.write(text)
    return text


def dry_run(worklist, fields=("id", "url"), out=None):
    lines = []
    for item in worklist:
        lines.append("  ".join(f"{str(item.get(field) or '-'):<40}" for field in fields).rstrip())
    text = "\n".join(lines) + f"\n{worklist.describe()}\n"
    if out:
        out.write(text)
    return text


def parse_marker(text):
    """Recover the item id from an emitted prompt or an agent transcript."""
    needle = f"[{MARKER}: "
    start = text.find(needle)
    if start < 0:
        return None
    end = text.find("]", start)
    if end < 0:
        return None
    return text[start + len(needle) : end].strip() or None
