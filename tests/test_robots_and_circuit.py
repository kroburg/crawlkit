"""Reading the crawl surface a site offers, and stopping when it withdraws it."""

import pytest

from crawlkit import circuit, robots

# -- robots.txt ----------------------------------------------------------


def test_the_open_surface_and_the_closed_endpoints_are_both_recognised(fixture_http):
    rules = robots.Robots.load(fixture_http)
    assert rules.allowed(f"{fixture_http}/item.asp?id=1")
    assert not rules.allowed(f"{fixture_http}/author_items.asp?authorid=1")
    assert not rules.allowed(f"{fixture_http}/query_results.asp")


def test_wildcard_extension_rules_are_honoured(fixture_http):
    rules = robots.Robots.load(fixture_http)
    assert not rules.allowed(f"{fixture_http}/export/table.xls")


def test_crawl_delay_and_sitemaps_are_read_from_the_file(fixture_http):
    rules = robots.Robots.load(fixture_http)
    assert rules.crawl_delay() == 2
    assert any(url.endswith("/sitemaps/index.xml") for url in rules.sitemaps())


def test_blocked_urls_are_reported_rather_than_silently_dropped(fixture_http):
    rules = robots.Robots.load(fixture_http)
    allowed, blocked = rules.filter(
        [f"{fixture_http}/item.asp?id=1", f"{fixture_http}/author_items.asp?id=2"]
    )
    assert len(allowed) == 1 and len(blocked) == 1


def test_an_unreachable_robots_file_denies_rather_than_permits(free_port):
    """Absence of an answer is not permission."""
    rules = robots.Robots.load(f"http://127.0.0.1:{free_port}/")
    assert not rules.allowed(f"http://127.0.0.1:{free_port}/anything")


def test_rules_can_be_parsed_without_a_fetch():
    rules = robots.Robots.from_text("https://example.test/", "User-agent: *\nDisallow: /private\n")
    assert rules.allowed("https://example.test/public")
    assert not rules.allowed("https://example.test/private/x")


# -- sitemaps ------------------------------------------------------------


def test_an_index_is_walked_into_page_urls(fixture_http):
    rules = robots.Robots.load(fixture_http)
    found = robots.walk_sitemaps(rules.sitemaps())
    assert len(found["pages"]) == 15
    assert all("/item.asp?id=" in url for url in found["pages"])
    assert len(found["fetched_sitemaps"]) == 4  # the index plus three shards


def test_the_walk_is_capped_because_an_index_can_name_millions(fixture_http):
    rules = robots.Robots.load(fixture_http)
    found = robots.walk_sitemaps(rules.sitemaps(), limit=2)
    assert len(found["fetched_sitemaps"]) == 2
    assert found["unfetched_sitemaps"], "the remainder is reported, not forgotten"
    assert len(found["pages"]) == 5


def test_a_leading_allow_does_not_cancel_the_disallows_below_it():
    """The hazard that makes this module hand-rolled.

    This is the common real-world layout: open the site in general, then close
    the expensive dynamic endpoints. Python's stdlib robotparser returns the
    FIRST matching rule in file order, so `Allow: /` swallows every Disallow
    beneath it and a crawler walks straight into the pages the site was
    protecting — believing itself compliant. RFC 9309 requires the longest
    match to win.
    """
    text = (
        "User-agent: *\nAllow: /\nDisallow: author_items.asp\nDisallow: refs.asp\nDisallow: *.xls\n"
    )
    rules = robots.Robots.from_text("https://example.test/", text)

    assert rules.allowed("https://example.test/item.asp?id=12345")
    assert not rules.allowed("https://example.test/author_items.asp?authorid=7")
    assert not rules.allowed("https://example.test/refs.asp?id=1")
    assert not rules.allowed("https://example.test/data/export.xls")

    # And the stdlib, on the very same file, disagrees about all three.
    from urllib.robotparser import RobotFileParser

    stdlib = RobotFileParser()
    stdlib.parse(text.splitlines())
    assert stdlib.can_fetch("*", "https://example.test/author_items.asp?authorid=7")


def test_longest_match_wins_and_ties_go_to_allow():
    rules = robots.Robots.from_text(
        "https://example.test/",
        "User-agent: *\nDisallow: /a/\nAllow: /a/public/\n",
    )
    assert not rules.allowed("https://example.test/a/private")
    assert rules.allowed("https://example.test/a/public/x")


def test_a_named_group_overrides_the_wildcard_group():
    rules = robots.Robots.from_text(
        "https://example.test/",
        "User-agent: *\nDisallow: /\n\nUser-agent: CustomBot\nAllow: /\n",
    )
    assert not rules.allowed("https://example.test/x", agent="Mozilla/5.0")
    assert rules.allowed("https://example.test/x", agent="CustomBot/1.0")


def test_an_empty_disallow_means_nothing_is_disallowed():
    rules = robots.Robots.from_text("https://example.test/", "User-agent: *\nDisallow:\n")
    assert rules.allowed("https://example.test/anything")


def test_sitemap_parsing_distinguishes_an_index_from_a_page_list():
    index = (
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>http://h/a.xml</loc></sitemap></sitemapindex>"
    )
    urlset = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>http://h/page</loc></url></urlset>"
    )
    assert robots.parse_sitemap(index) == (["http://h/a.xml"], [])
    assert robots.parse_sitemap(urlset) == ([], ["http://h/page"])


# -- the breaker ---------------------------------------------------------


def test_a_single_refusal_stops_the_run():
    """A 403 is a decision, not a hiccup."""
    breaker = circuit.Breaker()
    with pytest.raises(circuit.CircuitOpen) as caught:
        breaker.record(url="http://h/x", status=403)
    assert caught.value.kind == "refused"
    assert "do not rotate identity" in str(caught.value)


def test_throttling_is_tolerated_briefly_then_stops():
    breaker = circuit.Breaker(throttles=3)
    breaker.record(status=429)
    breaker.record(status=429)
    with pytest.raises(circuit.CircuitOpen) as caught:
        breaker.record(status=429)
    assert caught.value.kind == "throttled"


def test_a_challenge_body_counts_as_a_refusal_even_with_a_200():
    """The status line says fine; the body says prove you are human."""
    breaker = circuit.Breaker()
    with pytest.raises(circuit.CircuitOpen):
        breaker.record(status=200, body="<title>Just a moment...</title>")


def test_a_non_english_block_page_is_recognised_once_its_locale_is_enabled():
    """Matching a block page means matching the language it is written in, so
    the language list is the caller's choice rather than a default that quietly
    narrows the tool to wherever it was written."""
    breaker = circuit.Breaker(locales=["en", "ru"])
    with pytest.raises(circuit.CircuitOpen):
        breaker.record(status=200, body="Доступ ограничен: подозрительная активность")


def test_successes_decay_transient_failures():
    breaker = circuit.Breaker(throttles=3)
    breaker.record(status=429)
    breaker.record(status=200, body="fine")
    breaker.record(status=429)
    breaker.record(status=200, body="fine")
    breaker.record(status=429)
    assert not breaker.is_open, "isolated throttles spread over a run are not a ban"


def test_success_never_decays_a_refusal():
    breaker = circuit.Breaker(refusals=2)
    breaker.record(status=403)
    for _ in range(5):
        breaker.record(status=200, body="fine")
    with pytest.raises(circuit.CircuitOpen):
        breaker.record(status=403)


def test_once_open_it_stays_open():
    breaker = circuit.Breaker()
    with pytest.raises(circuit.CircuitOpen):
        breaker.record(status=403)
    with pytest.raises(circuit.CircuitOpen):
        breaker.record(status=200, body="fine")


def test_it_trips_against_the_real_fixture_endpoints(fixture_http):
    import urllib.error
    import urllib.request

    breaker = circuit.Breaker()
    try:
        urllib.request.urlopen(f"{fixture_http}/refused", timeout=5)
    except urllib.error.HTTPError as exc:
        with pytest.raises(circuit.CircuitOpen):
            breaker.record(url=f"{fixture_http}/refused", status=exc.code, body=exc.read().decode())
    assert breaker.summary()["opened"]["kind"] == "refused"
