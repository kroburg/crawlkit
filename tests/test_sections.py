"""The prompt's anatomy, and the three sections that are generated not written.

Each section here exists because its absence produced a specific failure in a
real fanout. The tests worth having are the ones that pin the *relationships* —
between the offered enum and the accepted one, between the census sentence and
the census gate, between the opening output contract and its closing echo —
because those are what silently drift.
"""

import pytest

from crawlkit import contract
from crawlkit.agents import sections
from crawlkit.agents.worklist import Worklist


def test_the_verdict_guide_offers_exactly_what_the_ingester_accepts_from_an_agent():
    """Retyping the enum into the prompt is how the two skew; this renders it."""
    guide = sections.verdict_guide("coverage_status")
    offered = contract.offered_values("coverage_status")
    for name, value in offered.items():
        assert name in guide
        assert value["gloss"] in guide


def test_a_derived_verdict_is_never_offered_to_an_agent():
    """`manual` and `undercoverage` are the script's conclusions. An agent that
    can name them can pre-empt the judgement it is being measured by."""
    guide = sections.verdict_guide("coverage_status")
    assert "manual" not in guide
    assert "undercoverage" not in guide


def test_the_census_sentence_carries_the_real_denominator():
    worklist = Worklist([{"id": f"item-{n}"} for n in range(53)], label="programmes")
    sentence = sections.census_rule(worklist, "the source lists a place")
    assert "53 programmes" in sentence
    assert "Census, not sample" in sentence


def test_the_scalar_request_never_leaks_the_passing_value():
    """The agent measures; the script judges. A measurement taken by someone
    who knows which number passes is not independent of the judgement.

    Note what is *not* forbidden: the words "ratio" and "compare" appear, in a
    prohibition. Telling the agent not to compute a ratio discloses nothing —
    naming the threshold or the verdict it would be compared against does.
    """
    text = sections.scalar_request("how many items the source lists")
    lowered = text.lower()

    threshold = contract.get("coverage.threshold")
    for leak in (str(threshold), f"{threshold:.0%}", "threshold", "undercoverage", "manual"):
        assert leak.lower() not in lowered, f"the prompt leaks {leak!r}"


def test_the_scalar_request_forbids_the_agent_from_judging():
    text = sections.scalar_request("how many items the source lists").lower()
    assert "do not compare" in text
    assert "do not compute a ratio" in text
    assert "the calling script does that" in text


def test_the_self_report_header_asks_for_both_numbers():
    header = sections.self_report_header("the source URL", "today's date")
    assert "<N> of <M>" in header
    assert "Excluded" in header


def test_the_blocked_source_escape_names_a_marker_and_the_next_step():
    """An agent with no sanctioned way to say 'I could not read this' invents
    content instead."""
    text = sections.blocked_source_escape(marker="BLOCKED", tool_hint="render it with a browser")
    assert "BLOCKED" in text
    assert "render it with a browser" in text
    assert "Do not pretend" in text


def test_the_anti_list_renders_each_drift_with_its_incident():
    table = sections.anti_list([("level: bachelor", "level: undergraduate", "first fanout")])
    assert "| Wrong | Right | Seen in |" in table
    assert "first fanout" in table


def test_an_empty_anti_list_renders_nothing_rather_than_an_empty_table():
    assert sections.anti_list([]) == ""


def test_the_refute_instruction_asks_for_refutation_and_fixes_the_tie_break():
    text = sections.refute_instruction()
    assert "REFUTE" in text
    assert "uncertain" in text


# -- assembly -------------------------------------------------------------


def test_the_closing_restatement_is_derived_from_the_opening_declaration():
    """Bookending only works if both ends say the same thing. Retyping the
    closer lets the prompt contradict itself."""
    declaration = sections.output_reply(language="json")
    closing = sections.restatement(declaration)
    assert declaration.splitlines()[0] in closing


def test_build_walks_the_declared_order_not_the_dict_order():
    out = sections.build(
        {
            "process": sections.process(["measure", "report"]),
            "role": sections.role("harvesting", "one item"),
            "output": sections.output_reply(),
        }
    )
    assert out.index("exactly one target") < out.index("## Process")


def test_build_appends_the_restatement_automatically():
    out = sections.build({"role": "r", "output": sections.output_reply()})
    assert out.count("ONE fenced") == 2, "declared once at the top, echoed once at the end"


def test_build_skips_sections_a_prompt_does_not_need():
    out = sections.build({"role": "r"})
    assert out == "r"


def test_an_unknown_section_is_an_error_not_a_silent_omission():
    """The failure this prevents: a section someone wrote, misspelled, and
    believed was being rendered."""
    with pytest.raises(KeyError):
        sections.build({"role": "r", "antilist": "oops"})
