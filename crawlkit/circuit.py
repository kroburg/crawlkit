"""Stop on the first sign that the site wants you to stop.

The instinct when a crawl starts returning 403 is to change something — another
exit address, another user agent, a longer sleep — and try again. That is the
move that converts a recoverable situation into a permanent one: the site's
defences escalate per identity and per network, and each retry teaches them
more about you than it teaches you about them.

So this breaker is deliberately asymmetric. Success decays the failure count
slowly; a refusal opens the circuit fast and the run ends with a written
reason. Resuming is a human decision made later, with a cache already on disk,
not an automatic one made two seconds later by a loop.

`tripped_by` distinguishes the three cases that look alike in a status code:
  throttled    the site is asking for less traffic (429, 503 + Retry-After)
  refused      the site is refusing this client (403, or a challenge body)
  unreachable  the network gave up (the -1 sentinel, timeouts)
"""

import time

from crawlkit import contract

REFUSAL_STATUSES = frozenset({401, 403, 407, 451})
THROTTLE_STATUSES = frozenset({429, 503})


class CircuitOpen(RuntimeError):
    def __init__(self, reason, kind, evidence=None):
        super().__init__(reason)
        self.reason = reason
        self.kind = kind
        self.evidence = evidence or {}


class Breaker:
    """Trips the whole run, not just one request."""

    def __init__(self, refusals=1, throttles=3, unreachable=5, clock=time.monotonic, locales=None):
        # One refusal is enough. A 403 is a decision, not a hiccup.
        self.limits = {"refused": refusals, "throttled": throttles, "unreachable": unreachable}
        self.counts = {"refused": 0, "throttled": 0, "unreachable": 0}
        self.opened = None
        self.clock = clock
        # A challenge page is written in the target's language. English only
        # unless the caller says otherwise; see contract.locales.
        self.challenge_markers = contract.markers("challenge_markers", locales)
        self.history = []

    @property
    def is_open(self):
        return self.opened is not None

    def classify(self, status=None, body=None, error=None):
        text = (body or "")[:4000].lower()
        if any(marker in text for marker in self.challenge_markers):
            return "refused"
        if status in REFUSAL_STATUSES:
            return "refused"
        if status in THROTTLE_STATUSES:
            return "throttled"
        if error is not None or status in (None, -1):
            return "unreachable"
        return None

    def record(self, url=None, status=None, body=None, error=None):
        """Feed every response through here. Raises CircuitOpen when it trips."""
        if self.is_open:
            raise CircuitOpen(self.opened["reason"], self.opened["kind"], self.opened)

        kind = self.classify(status, body, error)
        if kind is None:
            # Success decays the counters, but never below zero and never in a
            # way that lets a slow trickle of refusals hide under volume.
            for name in ("throttled", "unreachable"):
                self.counts[name] = max(0, self.counts[name] - 1)
            return None

        self.counts[kind] += 1
        self.history.append({"at": self.clock(), "url": url, "status": status, "kind": kind})

        if self.counts[kind] >= self.limits[kind]:
            self.opened = {
                "kind": kind,
                "reason": (
                    f"{kind} {self.counts[kind]}x (limit {self.limits[kind]}); "
                    f"last status {status} on {url}. Stopping — do not rotate identity "
                    f"and retry: read the cache, wait, and resume deliberately."
                ),
                "status": status,
                "url": url,
                "counts": dict(self.counts),
            }
            raise CircuitOpen(self.opened["reason"], kind, self.opened)
        return kind

    def summary(self):
        return {
            "open": self.is_open,
            "opened": self.opened,
            "counts": dict(self.counts),
            "events": len(self.history),
        }
