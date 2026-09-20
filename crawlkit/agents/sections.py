"""The anatomy of a harvesting prompt, as code.

Each function below is one section that earned its place by preventing a
specific, observed failure. Assembled in `standard_order`, they are the shape
of a prompt that reliably comes back usable.

The register throughout is deliberate and worth copying: second person
imperative, bold on the irreversible rules, an explicit "do X, never Y" pair
wherever agents drifted, and — most importantly — *every rule that costs the
agent effort says what it buys*. A rule without a reason gets optimized away.

Two sections are generated rather than written, and that is the point:
`verdict_guide` renders from the shared vocabulary, so the values offered to an
agent can never drift from the values the ingester accepts; `census_rule` takes
the same work-list object the census gate later checks against.
"""

from crawlkit import contract


def role(task, subject, scope_note="Work on this one only."):
    """Scope to a single item. An unscoped prompt invites an agent to widen."""
    return f"You are {task} for exactly one target: **{subject}**.\n{scope_note}"


def output_reply(language="json", preamble_ban=True):
    """Reply-with-a-fenced-block: the harvester mines transcripts.

    Files written to paths the caller did not choose cannot be collected, and
    prose outside the fence breaks the extractor's block selection.
    """
    lines = [
        f"Your entire output is ONE fenced ```{language} block, in your reply.",
        "**DO NOT WRITE FILES.**",
    ]
    if preamble_ban:
        lines.append("No preamble, no commentary, nothing outside the fence.")
    return "\n".join(lines)


def output_file(path, receipt="the number of records you wrote"):
    """Write-a-file-and-reply-with-a-receipt: the payload never enters context.

    Preferred for large payloads — the orchestrator sees one line instead of
    the whole harvest, which is what keeps a wide fanout affordable.
    """
    return (
        f"Write your output to `{path}` using the Write tool. "
        "Do NOT print it in chat.\n"
        f"Then reply with one line: {receipt}."
    )


def schema_verbatim(block, language="yaml"):
    """Never paraphrase a schema: paraphrase is how each agent drifts differently."""
    return (
        f"## Schema (verbatim — do not paraphrase, do not 'improve')\n\n```{language}\n{block}\n```"
    )


def census_rule(worklist, criterion, incident=None):
    """Enumerate, do not sample.

    Without this sentence an agent's default on "produce a record for X" is a
    representative sample: it costs fewer tokens and looks finished. The
    work-list passed here is the same object the census gate checks, so the
    instruction and the check cannot disagree.
    """
    text = (
        f"**Census, not sample.** Every one of the {worklist.describe()} where "
        f"{criterion} belongs in your output. Not a representative subset — all of them."
    )
    if incident:
        text += f"\n({incident})"
    return text


def self_report_header(source_field, date_field, comment="#"):
    """Make the denominator visible.

    Silent omission is the failure mode a reviewer cannot see. A first line
    reading "8 of 53" is legible at a glance, and an independent recount can
    later compare against that M.
    """
    return (
        "Your first line MUST be exactly this shape:\n\n"
        f"    {comment} verification: <N> of <M> items from {source_field}, {date_field}. "
        'Excluded: <list or "none">.\n\n'
        "N is what you are returning, M is what the source lists. If N < M, the "
        "exclusions are named individually — never left implicit."
    )


def source_grounding(fetch_verb="fetch", aggregator_rule=None):
    lines = [
        f"**Ground every claim.** {fetch_verb.capitalize()} each source before citing it; "
        "the page must actually contain the fact you attach to it.",
        "A landing page that merely links to the fact FAILS: omit the field rather "
        "than cite a parent URL.",
        "NEVER cite from prior knowledge — only what you fetched in this session.",
    ]
    if aggregator_rule:
        lines.append(aggregator_rule)
    return "\n".join(lines)


def blocked_source_escape(marker="BLOCKED", tool_hint=None, caller_action=None):
    """Give failure a legitimate, machine-readable name.

    An agent with no sanctioned way to say "I could not read this" will invent
    content instead. So: name the symptom, name the marker, and say what the
    caller will do next — which also tells the agent the report is useful
    rather than a confession of failure.
    """
    lines = [
        "**If a source is walled.** A sub-2KB body, a challenge interstitial, or an "
        "empty JS shell means you did NOT read the page. Do not pretend you did.",
        f"Omit the affected field and record `{marker}: <url>` in your exclusions.",
    ]
    if tool_hint:
        lines.append(f"Do not try to work around it yourself; the caller will {tool_hint}.")
    if caller_action:
        lines.append(caller_action)
    return "\n".join(lines)


def anti_list(rows, title="Previously observed drift — do not repeat"):
    """A wrong/right/incident table beats a paragraph asking for care.

    Every row is a mutation that actually arrived in real output. Naming the
    incident is what stops the row from being read as pedantry.
    """
    if not rows:
        return ""
    lines = [f"## {title}", "", "| Wrong | Right | Seen in |", "|---|---|---|"]
    for row in rows:
        wrong, right, incident = (list(row) + ["", "", ""])[:3]
        lines.append(f"| `{wrong}` | `{right}` | {incident} |")
    return "\n".join(lines)


def field_rules(rules):
    """Per-field instructions, each with an explicit omit-don't-invent branch."""
    return "\n".join(f"- `{field}` — {rule}" for field, rule in rules)


def verdict_guide(vocabulary, intro="Return exactly one of these:"):
    """Generated from the shared vocabulary, never retyped.

    Retyping is how the enum in the prompt and the enum the ingester validates
    drift apart, and the symptom is a whole fanout's worth of rejected records.
    """
    offered = contract.offered_values(vocabulary)
    width = max(len(name) for name in offered)
    lines = [intro]
    lines += [f"  {name.ljust(width)}  — {value['gloss']}" for name, value in offered.items()]
    return "\n".join(lines)


def scalar_request(what, forbid_comparison=True):
    """Ask for one measured number and nothing else.

    The agent must not know what value would pass, and must not be the one
    judging it — so no threshold, no ratio and no verdict name appears here.
    The caller computes all of that from its own side of the comparison.
    """
    lines = [f"Your one job: measure **{what}** at the source and report that number."]
    if forbid_comparison:
        lines.append(
            "Do NOT compare it against anything, do not compute a ratio, and do not "
            "judge whether it is acceptable. The calling script does that."
        )
    lines.append(
        "NEVER estimate or fabricate a count. If you cannot read the source, say so "
        "with the appropriate status and report 0."
    )
    return "\n".join(lines)


def refute_instruction(claim_field="claim", sources="independent, primary sources"):
    """Adversarial verification: ask for refutation, not confirmation.

    "Check this claim" returns agreement. "Try to refute it" returns evidence.
    The tie-break is stated so the uncertain case has a defined safe direction
    instead of being resolved by whichever way the model leans.
    """
    return (
        f"Adversarially fact-check the {claim_field}. Try to REFUTE it using {sources}.\n"
        "If the evidence is mixed, stale, or you cannot settle it, return `uncertain` "
        "together with the safest corrected statement — never split the difference."
    )


def process(steps):
    return "## Process\n\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))


def restatement(output_declaration, closer="Now begin."):
    """Close by repeating the output contract that opened the prompt.

    Takes the string `output_reply`/`output_file` returned rather than a fresh
    one, because a restatement retyped by hand drifts from the declaration it
    is supposed to echo — and then the prompt contradicts itself, which is
    worse than not bookending at all.
    """
    first = output_declaration.strip().splitlines()[0]
    return f"{first}\n{closer}"


def assemble(*sections, separator="\n\n"):
    return separator.join(section for section in sections if section)


ORDER = (
    ("role", "scope to one item before anything else"),
    ("output", "state the contract early"),
    ("schema", "verbatim, never paraphrased"),
    ("census", "enumerate, do not sample"),
    ("self_report", "make the denominator visible"),
    ("grounding", "no claim without a fetched source"),
    ("blocked", "a sanctioned way to report failure"),
    ("anti_list", "observed drift, with incidents"),
    ("field_rules", "omit rather than invent"),
    ("process", "ordering, so the measurement precedes the report"),
    ("restatement", "repeat the output contract last"),
)


def build(spec, separator="\n\n"):
    """Assemble a prompt by walking ORDER over a {name: text} mapping.

    The order is executed rather than documented. A list of section names that
    nothing consumes is a comment with extra steps: it drifts from what the
    emitter actually does and nobody finds out.

    Sections absent from `spec` are skipped, so a prompt that genuinely needs
    no anti-list simply omits it. An unknown key is an error — it is either a
    typo or a section somebody expected to be rendered and which silently
    would not have been.
    """
    unknown = set(spec) - {name for name, _ in ORDER}
    if unknown:
        raise KeyError(f"unknown prompt sections {sorted(unknown)}; known: {[n for n, _ in ORDER]}")

    if "restatement" not in spec and "output" in spec:
        spec = dict(spec, restatement=restatement(spec["output"]))

    return separator.join(spec[name] for name, _ in ORDER if spec.get(name))
