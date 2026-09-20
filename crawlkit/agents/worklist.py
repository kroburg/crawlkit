"""What was dispatched — the denominator for everything downstream.

A work-list is machine-derived and then used twice: once to render the census
sentence in the prompt, and once to check the returned records. Passing the
same object to both is what makes "the prompt asked for X, the gate counted Y"
structurally impossible.

Selection is idempotent: items already recorded as done drop out, so re-running
a plan after a partial fanout dispatches only the gaps. Only success is
skipped — anything that failed or could not be measured is re-planned, because
the alternative is a permanent blind spot.
"""

import json
from pathlib import Path


class Worklist:
    def __init__(self, items, key="id", label="items"):
        self.items = [dict(item) for item in items]
        self.key = key
        self.label = label
        self._index = None

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def ids(self):
        return [item[self.key] for item in self.items]

    def index(self):
        # Built once. Census work over a few thousand items is O(n^2) without
        # it, which is slow enough to discourage checking at all.
        if self._index is None:
            self._index = {item[self.key]: item for item in self.items}
        return self._index

    def get(self, ident):
        return self.index().get(ident)

    def key_set(self):
        """The denominator, as a set. What the census gate compares against."""
        return set(self.index())

    def describe(self):
        return f"{len(self.items)} {self.label}"

    @classmethod
    def load(cls, path, key="id", label="items"):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        items = [{key: entry} if isinstance(entry, str) else entry for entry in data]
        missing = [item for item in items if not item.get(key)]
        if missing:
            raise ValueError(f"{path}: {len(missing)} entries have no {key!r}")
        return cls(items, key=key, label=label)

    def save(self, path):
        Path(path).write_text(
            json.dumps(self.items, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def batches(self, size):
        return [self.items[i : i + size] for i in range(0, len(self.items), size)]


def select(items, done, key="id", reverify=False, label="items"):
    """Drop items already recorded done. `done` maps id -> status or bool."""
    if reverify:
        return Worklist(items, key=key, label=label)

    def finished(ident):
        state = done.get(ident)
        if isinstance(state, dict):
            state = state.get("status")
        if isinstance(state, str):
            return state == "ok"
        return bool(state)

    return Worklist([item for item in items if not finished(item[key])], key=key, label=label)
