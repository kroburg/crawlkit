"""The closed vocabularies, and who is allowed to say what.

Every vocabulary is defined once, in the contract, with a gloss per value and
an `offer_to_agent` flag. `sections.verdict_guide` renders the in-prompt guide
from that object and this module validates against it, so the values a prompt
offers are a filtered view of the values the ingester accepts rather than a
second list maintained alongside the first. Two lists skew; the symptom is a
whole fanout's worth of rejected records and no obvious cause.

The load-bearing parameter here is `from_agent`. Some values are **derived** —
the script concludes them after comparing what the agent measured against what
is already stored. `manual` means "the measurement could not be made"; an agent
that reports `manual` has decided its own result is unmeasurable *and* named
the conclusion the script was going to draw. Accepting that lets an agent
pre-empt the judgement it is being measured by, so from an agent it is a
rejection, and the ingester counts it like any other malformed field.
"""

from crawlkit import contract


class VerdictError(ValueError):
    pass


def accepted(name):
    """Every value the ingester will store."""
    return contract.vocabulary(name)


def offered(name):
    """The subset a prompt may put in front of an agent."""
    return contract.offered_values(name)


def derived(name):
    """Values only the script may conclude."""
    return contract.derived_values(name)


def vocabularies():
    return sorted(key for key in contract.get("vocabularies") if not key.startswith("_"))


def is_valid(name, value, *, from_agent=False):
    allowed = offered(name) if from_agent else accepted(name)
    return value in allowed


def validate(name, value, *, from_agent=False, where=""):
    """Return `value`, or raise. For call sites where a bad value is a bug.

    Use this at apply time and on writes. Use `check_record` where a bad value
    is one more rejected record among many and the run should carry on.
    """
    if is_valid(name, value, from_agent=from_agent):
        return value
    allowed = sorted(offered(name) if from_agent else accepted(name))
    prefix = f"{where}: " if where else ""
    if from_agent and value in derived(name):
        raise VerdictError(
            f"{prefix}{value!r} is derived by the caller, not reported by an agent "
            f"({name}). An agent naming it is claiming the conclusion. Allowed: {allowed}"
        )
    raise VerdictError(f"{prefix}unknown {name} {value!r}; allowed: {allowed}")


def check_record(record, fields, *, from_agent=False, where=""):
    """Problems with one record, accumulated. Never raises.

    `fields` maps a record key to a vocabulary name. A missing key is not a
    problem here — absence is the ingester's business, not the vocabulary's.
    """
    problems = []
    for field, name in fields.items():
        if field not in record:
            continue
        try:
            validate(name, record[field], from_agent=from_agent, where=where or field)
        except VerdictError as exc:
            problems.append(str(exc))
    return problems


def gloss(name, value):
    entry = accepted(name).get(value)
    if entry is None:
        raise VerdictError(f"unknown {name} {value!r}")
    return entry["gloss"]
