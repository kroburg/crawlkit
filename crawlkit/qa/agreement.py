"""Two independent extractions of the same record, and what to trust.

A single parser pass can be confidently wrong: a selector that matches the
wrong node still returns a value, and nothing about that value looks
abnormal on its own. Running two independent passes over the same pages (two
selector sets, two parser versions, a re-scrape) turns that into something
checkable — a value both passes agree on has survived a second, unrelated
implementation trying to get it wrong the same way, which a single pass never
does.

The rule this module exists to enforce: **absence is not assent.** A value
one pass produced and the other did not is missing information, not a tie
that the value which exists wins by default — treating it as agreement is
the shortcut that quietly reintroduces the single-pass failure mode this
whole exercise was meant to close.
"""

from collections.abc import Callable
from dataclasses import dataclass


def text_norm(v) -> str:
    """Canonical form for equality across two independently-written extractions.

    Two passes rarely agree byte-for-byte even when they agree in substance —
    trailing whitespace, doubled internal spaces, and case are the routine
    noise. `None` and `""` both normalize to `""` so a genuinely absent value
    compares equal to itself; whether a value counts as *present* at all is
    decided separately, before normalization ever runs.
    """
    if v is None:
        return ""
    return " ".join(str(v).split()).casefold()


def number_norm(tol) -> Callable:
    """A normalizer that treats numbers within `tol` of each other as equal.

    Two independent parses of the same number rarely match exactly (100 vs
    100.0, 19.99 vs 19.990004), so exact equality is the wrong comparison.
    This buckets each value into a `tol`-wide bin before comparing, which is
    an approximation: two values on opposite sides of a bin edge can fall
    into different buckets despite being closer together than `tol`. Accepted
    because the surrounding architecture compares two independently-normalized
    values for equality, not a live pairwise distance.
    """

    def norm(v):
        try:
            value = float(v)
        except (TypeError, ValueError):
            return text_norm(v)
        return int(value // tol) if tol > 0 else value

    return norm


def _present(record, field):
    if record is None or field not in record:
        return False
    value = record[field]
    return value is not None and value != ""


@dataclass(frozen=True)
class Agreement:
    agreed: dict
    disputed: dict
    only_in_a: dict
    only_in_b: dict

    def rate(self) -> float:
        """Fraction of comparable values (both passes produced one) that matched.

        Deliberately excludes only_in_a/only_in_b from the denominator: those
        are coverage gaps, not disagreements, and folding them in would let a
        pass that simply extracts fewer fields masquerade as more agreeable.
        Vacuously 1.0 when the two passes never produced an overlapping value
        at all — nothing to disagree about is not the same as disagreement.
        """
        agreed_n = sum(len(fields) for fields in self.agreed.values())
        disputed_n = sum(len(fields) for fields in self.disputed.values())
        total = agreed_n + disputed_n
        return agreed_n / total if total else 1.0

    def render(self) -> str:
        agreed_n = sum(len(fields) for fields in self.agreed.values())
        disputed_n = sum(len(fields) for fields in self.disputed.values())
        only_a_n = sum(len(fields) for fields in self.only_in_a.values())
        only_b_n = sum(len(fields) for fields in self.only_in_b.values())
        return "\n".join(
            [
                f"agreement rate: {self.rate():.1%}",
                f"agreed: {agreed_n}",
                f"disputed: {disputed_n}",
                f"only in pass a: {only_a_n}",
                f"only in pass b: {only_b_n}",
            ]
        )


def compare(pass_a, pass_b, fields, *, normalize=None, key="id") -> Agreement:
    norm_by_field = normalize or {}
    index_a = {record[key]: record for record in pass_a}
    index_b = {record[key]: record for record in pass_b}
    ids = dict.fromkeys(list(index_a) + list(index_b))

    agreed: dict = {}
    disputed: dict = {}
    only_in_a: dict = {}
    only_in_b: dict = {}

    for record_id in ids:
        record_a = index_a.get(record_id)
        record_b = index_b.get(record_id)
        for field in fields:
            present_a = _present(record_a, field)
            present_b = _present(record_b, field)

            if present_a and present_b:
                norm = norm_by_field.get(field, text_norm)
                value_a, value_b = record_a[field], record_b[field]
                if norm(value_a) == norm(value_b):
                    agreed.setdefault(record_id, {})[field] = value_a
                else:
                    disputed.setdefault(record_id, {})[field] = {"a": value_a, "b": value_b}
            elif present_a:
                only_in_a.setdefault(record_id, {})[field] = record_a[field]
            elif present_b:
                only_in_b.setdefault(record_id, {})[field] = record_b[field]
            # Neither pass produced a value: nothing to report either way.

    return Agreement(agreed=agreed, disputed=disputed, only_in_a=only_in_a, only_in_b=only_in_b)


def auto_applicable(agreement: Agreement) -> dict:
    """What a caller may write back without a human in the loop.

    This is exactly `agreement.agreed` — a separate function exists so a
    caller reaches for a name that states the safety property directly,
    rather than reading the dataclass's internals and re-deriving "agreed
    means safe to apply" at every call site.
    """
    return {record_id: dict(fields) for record_id, fields in agreement.agreed.items()}
