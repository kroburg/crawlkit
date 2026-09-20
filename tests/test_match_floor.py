"""A best match is not automatically a match — pinned for both metrics.

Geo and label matching are the same function wearing two different distance
functions, and the one thing worth protecting for a year is that the shared
part (`core.best_under`) never learns what either distance means, while both
callers convert their floor into "lower is better" correctly. Everything
below either exercises that shared refusal behaviour once, generically, or
checks that a given metric's conversion into it didn't get inverted.
"""

import ast
from pathlib import Path

from crawlkit import contract
from crawlkit.match import geo, tokens
from crawlkit.match.core import Match, best_under

CORE_PATH = Path(__file__).resolve().parents[1] / "crawlkit" / "match" / "core.py"


# --- geo: nearest candidate refused beyond the floor, accepted just inside it ---


def test_geo_nearest_candidate_refused_when_beyond_the_floor():
    here = (55.75, 37.61)
    far = {"lat": 56.0, "lon": 37.61, "name": "too far"}  # ~27.8 km away
    assert geo.nearest(here, [far]) is None


def test_geo_nearest_candidate_accepted_just_inside_the_floor():
    here = (0.0, 0.0)
    # 1 degree of latitude is ~111.2 km; pick an offset a hair under 1500 m.
    offset_deg = 1400 / 111_200
    close = {"lat": offset_deg, "lon": 0.0, "name": "just inside"}
    result = geo.nearest(here, [close])
    assert result is not None
    assert result.candidate is close
    assert result.provenance["distance"] < 1500


def test_geo_floor_defaults_to_the_contract_value():
    assert contract.get("match.floors.geo_m") == 1500


# --- tokens: shared common words don't match; a distinctive shared token does ---


def test_common_words_alone_do_not_match():
    # Both texts are long and share exactly one generic word ("guide"); that
    # single hit is a small enough fraction of either side (~3%) to stay
    # under the 5% floor, so a market-stalls page must not pass as a match
    # for a landscaping page just because both happen to say "guide".
    label = (
        "guide overview history culture exhibits tickets pricing schedule opening tours "
        "group booking online payment membership annual season weather forecast local transport "
        "shops market vendor stalls fresh produce bakery pastry cheese wine"
    )
    candidates = [
        "guide description flowers plants soil compost seeds bulbs pruning watering fertilizer "
        "pest disease drainage sunlight shade greenhouse nursery landscape design pathway "
        "fencing lighting furniture decor storage shed tools equipment"
    ]
    assert tokens.best_label(label, candidates) is None


def test_a_distinctive_shared_token_matches():
    label = "hiking guide description overview history geology wildlife kokoriha waterfall trail"
    candidates = [
        "Kokoriha waterfall trail entrance camping fees parking hours schedule map "
        "elevation gain difficulty rating"
    ]
    result = tokens.best_label(label, candidates)
    assert result is not None
    assert result.candidate == candidates[0]


# --- provenance carries the runner-up and the margin ---


def test_provenance_carries_runner_up_and_margin():
    result = best_under(
        candidates=["near", "mid", "far"],
        distance_fn={"near": 10, "mid": 12, "far": 1000}.get,
        floor=100,
        metric="test_metric",
    )
    assert result is not None
    assert result.candidate == "near"
    assert result.provenance["distance"] == 10
    assert result.provenance["runner_up"] == 12
    assert result.provenance["margin"] == 2
    assert result.provenance["metric"] == "test_metric"


def test_provenance_runner_up_is_none_with_a_single_candidate():
    result = best_under(["only"], lambda c: 1, floor=10)
    assert result is not None
    assert result.provenance["runner_up"] is None
    assert result.provenance["margin"] is None


# --- empty candidates, and a distance_fn that raises on one candidate ---


def test_empty_candidates_returns_none():
    assert best_under([], lambda c: 0, floor=10) is None


def test_a_raising_distance_fn_is_skipped_not_fatal():
    def flaky(candidate):
        if candidate == "poison":
            raise ValueError("malformed record")
        return {"good": 5, "poison": None, "bad_but_scored": 50}[candidate]

    result = best_under(["poison", "good", "bad_but_scored"], flaky, floor=10)
    assert result is not None
    assert result.candidate == "good"
    assert result.provenance["skipped"] == 1


def test_all_candidates_raising_returns_none():
    def always_raises(candidate):
        raise RuntimeError("boom")

    assert best_under(["a", "b"], always_raises, floor=10) is None


# --- core.py knows nothing about geography or text ---


def test_core_imports_neither_geo_nor_tokens_nor_math():
    """The one check that keeps "one function, two metrics" true a year from
    now: nothing about distance, ever, creeps back into the shared floor
    logic. A plain grep would miss a `from crawlkit.match import geo as g`
    alias, so this walks the real import graph instead."""
    tree = ast.parse(CORE_PATH.read_text(encoding="utf-8"))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
            imported_names.update(f"{node.module}.{alias.name}" for alias in node.names)

    forbidden = {"math", "geo", "tokens", "crawlkit.match.geo", "crawlkit.match.tokens"}
    hit = {name for name in imported_names if name.split(".")[-1] in {"math", "geo", "tokens"}}
    assert not hit, (
        f"core.py must not import geo/tokens/math, found: {hit} in {imported_names & forbidden}"
    )


# --- overlap direction: high overlap matches, low overlap does not ---


def test_overlap_direction_is_not_inverted():
    """Pins the one edit that would fail silently instead of loudly: swapping
    `distance = 1 - overlap` for `distance = overlap` (or the floor for its
    complement) does not raise anywhere — it just makes every low-overlap
    pair match and every high-overlap pair a coin flip, because the sense of
    "better" flips underneath an unchanged floor. A high-overlap label must
    win here, and a low-overlap one must be refused, or the conversion has
    silently gone in the wrong direction.
    """
    text = "Kokoriha waterfall nature reserve visitor trail"
    high_overlap_candidate = "Complete guide to the Kokoriha waterfall reserve trail"
    low_overlap_candidate = "Downtown municipal parking garage renovation schedule"

    high = tokens.best_label(text, [high_overlap_candidate])
    assert high is not None
    assert high.candidate == high_overlap_candidate

    low = tokens.best_label(text, [low_overlap_candidate])
    assert low is None


def test_token_floor_defaults_to_the_contract_value():
    assert contract.get("match.floors.token_overlap") == 0.05


def test_tokenize_keeps_latin_and_cyrillic_drops_short_words():
    words = tokens.tokenize("the дворец на набережной is a book")
    assert "дворец" in words
    assert "набережной" in words
    assert "the" not in words  # 3 letters
    assert "is" not in words  # 2 letters
    assert "a" not in words  # 1 letter
    assert "book" in words


def test_overlap_is_zero_when_either_side_is_empty():
    assert tokens.overlap(frozenset(), frozenset({"word"})) == 0.0
    assert tokens.overlap(frozenset({"word"}), frozenset()) == 0.0
    assert tokens.overlap(frozenset(), frozenset()) == 0.0


def test_overlap_is_containment_not_jaccard():
    """A short label fully contained in a long title must score high, which
    Jaccard (divide by the union) would score near zero on."""
    short_label = frozenset({"kokoriha", "waterfall"})
    long_title = frozenset(
        {"complete", "guide", "kokoriha", "waterfall", "reserve", "trail", "entrance", "hours"}
    )
    assert tokens.overlap(short_label, long_title) == 1.0


def test_match_is_a_namedtuple_with_candidate_and_provenance():
    result = best_under(["x"], lambda c: 1, floor=10)
    assert isinstance(result, Match)
    assert result.candidate == "x"
    assert isinstance(result.provenance, dict)
