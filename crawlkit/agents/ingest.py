"""Getting agent output back in without destroying what is already there.

The incident this module is shaped around: a harvester collected every reply
file in a directory, sorted by modification time, and let the newest win per
item. Unrelated agents from an earlier run finished late, their files were
newest, and they silently overwrote records that had been curated by hand. The
run reported success. Nobody noticed until a review.

So authorization here is an explicit list of agent ids the caller just
dispatched. `agent_ids` is a required positional and an empty collection is an
error — there is deliberately **no spelling of this call that means "take
whatever is in the directory"**, and no parameter anywhere in this module
accepts a time, a path ordering, or a newest-wins flag.

Four rejections, all counted rather than raised, because one bad reply among
fifty is a statistic and not a reason to stop. The fourth is the subtle one: a
well-formed reply containing no records is a *failure*, not an empty result.
Treating it as data lets a dead agent blank a good file by succeeding at
nothing.
"""

from dataclasses import dataclass, field
from pathlib import Path

from crawlkit.agents import census_gate, fenced

BUCKETS = ("unauthorized", "no-block", "unparseable", "unknown-key", "empty-result")


@dataclass(frozen=True)
class Result:
    """One agent's reply, before anything has been believed about it."""

    agent_id: str
    text: str
    source: str = ""
    item_id: str = None


@dataclass
class IngestReport:
    applied: dict = field(default_factory=dict)
    rejected: dict = field(default_factory=lambda: {name: [] for name in BUCKETS})
    reports: dict = field(default_factory=dict)

    @property
    def counts(self):
        return {name: len(entries) for name, entries in self.rejected.items()}

    def ok(self):
        return not any(self.rejected.values())

    def reject(self, bucket, who, why):
        self.rejected[bucket].append((who, why))

    def render(self):
        lines = [f"applied: {len(self.applied)}"]
        for name, entries in self.rejected.items():
            if entries:
                lines.append(f"{name}: {len(entries)}")
                lines.extend(f"    {who}: {why}" for who, why in entries[:5])
        return "\n".join(lines)


def authorize(results, agent_ids):
    """(allowed, rejected). Membership by prefix, never by time.

    Prefix matching is a deliberate ergonomic loosening: ids are long and get
    truncated when a human copies them. It is the only softness here.
    """
    if not agent_ids:
        raise ValueError(
            "agent_ids is required and must be non-empty: ingest authorizes an "
            "explicit list of just-dispatched agents, never a directory listing"
        )
    allowed, rejected = [], []
    for result in results:
        if any(
            result.agent_id == wanted
            or result.agent_id.startswith(wanted)
            or wanted.startswith(result.agent_id)
            for wanted in agent_ids
        ):
            allowed.append(result)
        else:
            rejected.append((result, "not in the dispatched set"))
    return allowed, rejected


def is_empty_payload(payload):
    if payload is None:
        return True
    if isinstance(payload, (list, dict, str)) and not payload:
        return True
    if isinstance(payload, dict):
        records = payload.get("records")
        if isinstance(records, (list, dict)) and not records:
            return True
        return all(value in (None, "", [], {}) for value in payload.values())
    return False


def normalize(record, maps):
    """Apply value maps. None drops the field; an unknown value passes through.

    Passing unknown values through is the point. A permissive map that coerced
    anything unrecognised would hide exactly the drift the schema gate exists
    to catch — the job here is to fold known spellings together, not to make
    everything look valid.
    """
    if not maps:
        return dict(record), []
    out, changed = {}, []
    for field_name, value in record.items():
        mapping = maps.get(field_name)
        if not mapping or value not in mapping:
            out[field_name] = value
            continue
        replacement = mapping[value]
        if replacement is None:
            changed.append(f"{field_name}: dropped {value!r}")
            continue
        out[field_name] = replacement
        changed.append(f"{field_name}: {value!r} -> {replacement!r}")
    return out, changed


def ingest(results, agent_ids, *, marker=None, schema_keys=None, maps=None, keymap=None):
    """Turn replies into records, counting every reason one did not make it."""
    report = IngestReport()
    allowed, unauthorized = authorize(results, agent_ids)
    for result, why in unauthorized:
        report.reject("unauthorized", result.agent_id, why)

    for result in allowed:
        payload, status = fenced.extract_json(result.text, marker=marker)
        if status != "ok":
            report.reject(status, result.agent_id, f"no usable payload in {result.source or '?'}")
            continue

        item_id = result.item_id or (payload.get("item_id") if isinstance(payload, dict) else None)
        if keymap is not None and item_id is not None:
            if item_id not in keymap:
                report.reject("unknown-key", result.agent_id, f"{item_id!r} has no known target")
                continue
            item_id = keymap[item_id]
        if item_id is None:
            report.reject("unknown-key", result.agent_id, "reply names no item")
            continue

        if is_empty_payload(payload):
            report.reject("empty-result", result.agent_id, f"{item_id}: well-formed but empty")
            continue

        if schema_keys is not None and isinstance(payload, dict):
            unknown = set(payload) - set(schema_keys)
            if unknown:
                report.reject("unknown-key", result.agent_id, f"{item_id}: {sorted(unknown)}")
                continue

        record, _ = normalize(payload, maps) if isinstance(payload, dict) else (payload, [])
        report.applied[item_id] = record
        found = fenced.parse_self_report(result.text)
        if found:
            report.reports[item_id] = found

    return report


def apply(report, target_path, *, worklist=None, dry_run=False):
    """Write applied records, passing them through the census gate first."""
    import json

    records = report.applied
    census = None
    if worklist is not None:
        census = census_gate.compare(worklist, records)
        records = census_gate.strict_join(worklist, records)

    if not dry_run:
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {"written": len(records), "census": census, "dry_run": dry_run}


def read_results(directory, suffix=".json", index=None):
    """Reply files as Results.

    By default the agent id is the filename stem, which is how a fanout writes
    them. A recovery run names its files after the *item*, not the agent, so it
    also writes an `index.json` mapping one to the other; when that file is
    present it decides both ids. Without it the chain would look like it worked
    and then fail authorization, which is the confusing kind of broken.
    """
    root = Path(directory)
    import json as _json

    mapping = {}
    index_path = Path(index) if index else root / "index.json"
    if index_path.is_file():
        try:
            raw = _json.loads(index_path.read_text(encoding="utf-8"))
            mapping = {
                entry.get("item_id"): agent_id
                for agent_id, entry in raw.items()
                if isinstance(entry, dict)
            }
        except (_json.JSONDecodeError, AttributeError):
            mapping = {}

    out = []
    for path in sorted(root.glob(f"*{suffix}")):
        if path.name == "index.json":
            continue
        agent_id = mapping.get(path.stem, path.stem)
        out.append(
            Result(
                agent_id=agent_id,
                text=path.read_text(encoding="utf-8"),
                source=str(path),
                item_id=path.stem if path.stem in mapping else None,
            )
        )
    return out
