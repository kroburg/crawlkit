"""Three calibration findings, kept as synthetic fixtures so they always run.

Each of these came from checking the toolkit against real harvested pages and
photographs rather than against invented ones, and each one contradicted a rule
the code already shipped. The artefacts that produced them are not public, but
the property each demonstrated is reproducible from a few bytes — so they are
regenerated here instead of being remembered in a commit message.
"""

import io
import re

import pytest

from crawlkit import contract, render
from crawlkit.qa import jpeg_frame

# -- 1. a valid photograph a strict end-marker check throws away ----------


def jpeg_with_trailer(trailer=b"F/W Version: 0.32\nCAL: M:18 FF:129 NF:134\n" * 200):
    """A complete JPEG carrying a plain-text sensor log after the image stream.

    Cameras really do this. The image is intact and decodes; the file simply
    does not *end* at the end-of-image marker.
    """
    pytest.importorskip("PIL")
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), (90, 120, 160)).save(buffer, "JPEG", quality=92)
    return buffer.getvalue() + trailer


def test_a_complete_image_with_trailing_data_is_not_corrupt():
    data = jpeg_with_trailer()
    assert jpeg_frame.is_valid(data)
    assert "trailing after EOI" in jpeg_frame.describe(data)


def test_the_strict_rule_is_what_rejects_it():
    """Kept as an explicit contrast: the obvious check is wrong, and this is
    the line that shows the cost of adopting it."""
    data = jpeg_with_trailer()
    assert not jpeg_frame.strictly_terminated(data)
    assert jpeg_frame.is_valid(data)


def test_a_genuinely_truncated_image_is_still_rejected():
    """The relaxation must not become a blanket pass."""
    whole = jpeg_with_trailer(trailer=b"")
    assert not jpeg_frame.is_valid(whole[: int(len(whole) * 0.4)])


# -- 2. real pages are sometimes thinner than the default floor -----------

THIN_PAGES = [
    "<html><head><title>Bay</title></head><body><h1>Bay</h1>"
    "<p>Anchorage on the north shore. Depth 6-9 m over sand with weed patches; "
    "holding is good once the anchor is through. Shelter from north and "
    "north-east, open to the south-west, and a swell works in overnight when "
    "the wind backs. Room for perhaps eight boats at anchor.</p>"
    "<p>No facilities ashore. Water and fuel are two hours away. The track up "
    "from the beach reaches a road after about a kilometre.</p>"
    "<p>Two reviews, both from last season, both noting the swell.</p>"
    "</body></html>",
    "<html><head><title>Cove</title></head><body><h1>Cove</h1>"
    "<p>Small cove with room for three boats. Weed in patches, so check the "
    "set. Protected from the prevailing wind; uncomfortable in anything from "
    "the south. Depths shoal quickly towards the head.</p>"
    "<p>A restaurant operates in season and will lend a mooring to diners. No "
    "water, no power, no shop.</p></body></html>",
]


def visible_text(html):
    stripped = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", stripped)).strip()


def test_a_genuine_page_can_render_less_text_than_the_default_floor():
    """Thin is not blocked. Roughly a third of one real harvest sat below the
    default `min_body`, which makes the floor a per-target parameter."""
    floor = contract.get("challenge.min_body")
    assert all(len(visible_text(page)) < floor for page in THIN_PAGES)


def test_the_growth_gate_is_therefore_opt_in():
    """This test exists to fail loudly if anyone makes the gate the default: at
    the shipped floor, a harvest of a terse site would reject its own results."""
    import inspect

    assert inspect.signature(render.fetch).parameters["require_growth"].default is False


def test_a_challenge_stub_is_two_orders_of_magnitude_thinner_still():
    """Why the predicate works despite the calibration hazard: the gap between
    a stub and even a thin real page is enormous, so any floor between them
    works — you just have to pick one per target."""
    stub = "<html><head><title>Just a moment...</title></head><body>Just a moment...</body></html>"
    assert len(visible_text(stub)) < 100
    assert min(len(visible_text(page)) for page in THIN_PAGES) > 100


# -- 3. a vendor's name in ordinary content is not a wall -----------------

PAGE_WITH_WIDGET = """<html><head><title>Members area</title></head><body>
<h1>Members area</h1>
<p>Sign in to see your saved items. Plenty of ordinary content here.</p>
<form id="login">
  <div class="cf-turnstile" data-sitekey="0x000"></div>
  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>
</form>
<script src="/cdn-cgi/challenge-platform/scripts/main.js"></script>
</body></html>"""


def test_a_substring_detector_calls_an_ordinary_page_a_wall():
    """Sites embed challenge widgets inside their own login forms, so the
    vendor's name appears on pages that were fetched perfectly well."""
    assert "cloudflare" in PAGE_WITH_WIDGET.lower()
    assert "cf-turnstile" in PAGE_WITH_WIDGET.lower()


def test_the_predicate_we_ship_does_not():
    pattern = contract.get("challenge.title_pattern")
    assert pattern not in PAGE_WITH_WIDGET.lower()

    from crawlkit import circuit

    assert circuit.Breaker().classify(status=200, body=PAGE_WITH_WIDGET) is None
