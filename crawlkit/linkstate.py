"""Per-URL state, and the override that keeps a browser verdict alive.

Two rules carry this module.

**Disjoint field ownership.** The prober writes `http_status`/`last_checked`
and nothing else; the semantic verifier writes `verdicts[kind]` and nothing
else. Neither stage can undo the other's work, so they can run in any order
and any number of times.

**The sticky override.** A URL that only a real browser can reach would be
scored broken forever by a HEAD/GET checker. A browser-grade confirmation
stamps `verified_via`, and the prober then skips the network for that URL
entirely. The guard is a conjunction — marker AND a recorded status that is
actually live — so a stale marker over a dead status still gets re-probed
rather than freezing a lie in place.

The file is written sorted and indented so it diffs cleanly in review; the
schema is closed-world, and the test asserts no unknown key at either level,
which is what stops a typo'd field from becoming load-bearing.
"""

import json
from datetime import date
from pathlib import Path

from crawlkit import contract
from crawlkit.agents import verdicts

MARKER = contract.STICKY_MARKER
LIVE_HTTP = contract.LIVE_HTTP

TOP_KEYS = {"http_status", "last_checked", "verdicts", "verified_via"}
VERDICT_KEYS = {"content_status", "semantic_verified_at", "notes"}


def today():
    return date.today().isoformat()


class LinkState:
    def __init__(self, path, data=None):
        self.path = Path(path)
        self.data = data if data is not None else self._load()

    def _load(self):
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    # -- reads -----------------------------------------------------------

    def record(self, url):
        return self.data.get(url) or {}

    def is_sticky(self, url):
        rec = self.record(url)
        return rec.get("verified_via") == MARKER and rec.get("http_status") in LIVE_HTTP

    def resolve_status(self, url, check):
        """(status, probed). probed=False means the network was not touched.

        The single place the override is decided. Keeping a tested helper
        *and* an inline copy in main() is the easy mistake: the tests then
        guard a function the program never calls.
        """
        if self.is_sticky(url):
            return self.record(url)["http_status"], False
        return check(url), True

    # -- writes (disjoint by owner) ---------------------------------------

    def set_http(self, url, status, when=None):
        rec = self.data.setdefault(url, {})
        rec["http_status"] = status
        rec["last_checked"] = when or today()
        return rec

    def set_verdict(self, url, kind, content_status, notes="", when=None):
        rec = self.data.setdefault(url, {})
        verdicts = rec.setdefault("verdicts", {})
        verdicts[kind] = {
            "content_status": content_status,
            "semantic_verified_at": when or today(),
            "notes": notes or "",
        }
        return rec

    def mark_verified_via(self, url, kind, status=200, notes="", when=None, marker=MARKER):
        """Stamp a browser-grade confirmation: sticky transport + one verdict."""
        stamp = when or today()
        rec = self.set_http(url, status, stamp)
        rec["verified_via"] = marker
        self.set_verdict(url, kind, "ok", notes or "confirmed by rendering; probe blocked", stamp)
        return rec


def schema_errors(data):
    """Closed-world validation: unknown keys are errors, not extras."""
    problems = []
    for url, rec in data.items():
        extra = set(rec) - TOP_KEYS
        if extra:
            problems.append(f"{url}: unknown top-level keys {sorted(extra)}")
        if "verified_via" in rec and rec["verified_via"] != MARKER:
            problems.append(f"{url}: unknown verified_via {rec['verified_via']!r}")
        for kind, verdict in (rec.get("verdicts") or {}).items():
            extra_v = set(verdict) - VERDICT_KEYS
            if extra_v:
                problems.append(f"{url} [{kind}]: unknown verdict keys {sorted(extra_v)}")
            status = verdict.get("content_status")
            if not verdicts.is_valid("content_status", status):
                problems.append(f"{url} [{kind}]: unknown content_status {status!r}")
    return problems
