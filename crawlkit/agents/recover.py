"""Salvaging a fanout that died before you collected it.

A wide fanout dies for boring reasons — a usage limit, a closed laptop, a
crashed orchestrator — and the work is not lost, just unread: each agent's
transcript is on disk. Recovery reads those transcripts and turns the finished
ones back into results.

Two rules shape this module.

**Identity comes from a marker the emitter wrote, not from the prose.** The
obvious approach is to regex the item id back out of the agent's first prompt,
which works exactly until somebody rewords the prompt — and then recovery
returns nothing, or worse, matches the wrong item. `emit` writes a
machine-readable token into every prompt; that is what is read here, with the
sidecar as a fallback for fanouts this toolkit did not dispatch.

**Recovery finds; ingest authorizes.** This module returns `ingest.Result`
objects and applies nothing. Otherwise "recover the dead agents" quietly
becomes a route around the whitelist that exists to stop stale replies
overwriting good records.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from crawlkit.agents import emit, ingest

DEFAULT_ROOT = Path.home() / ".claude" / "projects"


@dataclass(frozen=True)
class Transcript:
    path: Path
    agent_id: str
    meta: dict
    target: str | None
    identified_by: str | None  # marker | description | tool_use_id | None
    text: str | None
    complete: bool
    reason: str  # ok | incomplete | stopped-by-user | no-assistant | unreadable


def read_lines(path):
    """Parse a JSONL transcript line by line, tolerating damage.

    These files are appended while the agent runs, so the last line of an
    interrupted one is routinely a partial write. A single bad line must not
    cost the whole transcript.
    """
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def read_sidecar(jsonl_path):
    path = Path(str(jsonl_path).removesuffix(".jsonl") + ".meta.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def first_user_text(lines):
    for line in lines:
        message = line.get("message") or {}
        if line.get("type") == "user" and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return None


def identify(lines, meta):
    """(target, how). The marker first, because prose gets reworded."""
    prompt_text = first_user_text(lines)
    if prompt_text:
        marked = emit.parse_marker(prompt_text)
        if marked:
            return marked, "marker"
    # Fallbacks for fanouts dispatched by something else. A crash sidecar can
    # carry no description at all, which must not raise.
    if meta.get("description"):
        return meta["description"], "description"
    if meta.get("toolUseId"):
        return meta["toolUseId"], "tool_use_id"
    return None, None


def final_text(lines):
    """(text, complete, reason) from the last assistant turn.

    Completion is `stop_reason == "end_turn"` **and** a text block last. An
    agent whose final block is a tool call died mid-call: it has no answer, and
    treating its last words as a result imports a fragment as if it were one.
    """
    assistant = [line for line in lines if line.get("type") == "assistant"]
    if not assistant:
        return None, False, "no-assistant"

    message = assistant[-1].get("message") or {}
    content = message.get("content") or []
    blocks = [part for part in content if isinstance(part, dict)]
    if not blocks:
        return None, False, "incomplete"

    last = blocks[-1]
    if message.get("stop_reason") != "end_turn" or last.get("type") != "text":
        text = last.get("text") if last.get("type") == "text" else None
        return text, False, "incomplete"
    return last.get("text"), True, "ok"


def load(jsonl_path):
    path = Path(jsonl_path)
    lines = read_lines(path)
    meta = read_sidecar(path)
    if not lines:
        return Transcript(path, path.stem, meta, None, None, None, False, "unreadable")

    target, how = identify(lines, meta)
    text, complete, reason = final_text(lines)
    if meta.get("stoppedByUser") and not complete:
        reason = "stopped-by-user"
    agent_id = lines[0].get("agentId") or path.stem.removeprefix("agent-")
    return Transcript(path, agent_id, meta, target, how, text, complete, reason)


def sessions(root=DEFAULT_ROOT, project=None):
    root = Path(root)
    if not root.is_dir():
        return []
    projects = [root / project] if project else sorted(p for p in root.iterdir() if p.is_dir())
    found = []
    for entry in projects:
        if not entry.is_dir():
            continue
        found.extend(sorted(path for path in entry.glob("*/subagents") if path.is_dir()))
    return found


def transcripts(subagents_dir):
    return sorted(Path(subagents_dir).glob("agent-*.jsonl"))


def recover(root=DEFAULT_ROOT, *, project=None, session=None, agent_ids=None):
    """Every transcript under `root`, loaded. Applies nothing."""
    out = []
    for directory in sessions(root, project):
        if session and session not in str(directory):
            continue
        for path in transcripts(directory):
            loaded = load(path)
            if agent_ids and not any(loaded.agent_id.startswith(want) for want in agent_ids):
                continue
            out.append(loaded)
    return out


def to_results(found):
    """Finished transcripts as ingest.Result. Unfinished ones are dropped."""
    return [
        ingest.Result(
            agent_id=item.agent_id,
            text=item.text,
            source=str(item.path),
            item_id=item.target,
        )
        for item in found
        if item.complete and item.text and item.target
    ]


def summarize(found):
    counts = {}
    for item in found:
        counts[item.reason] = counts.get(item.reason, 0) + 1
    return {
        "transcripts": len(found),
        "recoverable": sum(1 for item in found if item.complete and item.target),
        "by_reason": counts,
        "identified_by": {
            how: sum(1 for item in found if item.identified_by == how)
            for how in ("marker", "description", "tool_use_id")
        },
    }
