"""robots.txt and sitemaps: the crawl surface the site is offering you.

Worth reading before anything else, and not only for manners. A robots file is
a map of where the expensive queries live. Sites routinely disallow their
dynamic endpoints — search, per-entity listings, citation expanders — while
leaving the static item pages open and publishing a sitemap index of every one
of them. The disallowed set is usually exactly the set that gets a crawler
banned, so honouring it is the same decision as not getting blocked.

A published sitemap is also the cheapest possible discovery: no link graph to
walk, no query pages to hit, just the canonical list.

Pure stdlib (`urllib.robotparser`, `xml.etree`), so this runs alongside the
probe layer with nothing installed.
"""

import gzip
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from crawlkit import ua

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


# Why this is hand-rolled instead of using urllib.robotparser:
#
# The stdlib parser returns the FIRST matching rule in file order and supports
# no wildcards. Real files are routinely written as an opening `Allow: /`
# followed by a list of `Disallow:` lines for the expensive endpoints — under
# first-match-wins every one of those Disallows is invisible, and a crawler
# concludes it may hit exactly the pages the site was protecting. RFC 9309
# §2.2.2 requires the MOST SPECIFIC (longest) match to win, with `*` and `$`
# supported. Getting this wrong looks like compliance right up until the ban.
class Rule:
    __slots__ = ("allow", "pattern", "regex", "length")

    def __init__(self, allow, pattern):
        self.allow = allow
        self.pattern = pattern
        self.length = len(pattern)
        self.regex = re.compile(_pattern_to_regex(_normalize(pattern)))

    def matches(self, path):
        return bool(self.regex.match(path))


def _normalize(pattern):
    """Make a bare `foo.asp` behave as `*foo.asp`.

    The standard says a rule value is a path and starts with `/`, but real
    files frequently omit it: a bare `foo.asp` in a disallow list is common. Anchoring such a pattern at the root would match nothing and
    quietly grant access to every endpoint the site meant to close, so an
    ambiguous pattern is widened to match anywhere. The bias is deliberate:
    when a rule is unclear, do not crawl.
    """
    if pattern.startswith(("/", "*")):
        return pattern
    return "*" + pattern


def _pattern_to_regex(pattern):
    out = ["^"]
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    for char in body:
        if char == "*":
            out.append(".*")
        else:
            out.append(re.escape(char))
    out.append("$" if anchored else "")
    return "".join(out)


def _path_of(url):
    parts = urllib.parse.urlsplit(url)
    path = parts.path or "/"
    return f"{path}?{parts.query}" if parts.query else path


def _agent_matches(pattern, agent):
    return pattern == "*" or pattern.lower() in agent.lower()


def parse_rules(text):
    """{agent_pattern: {"rules": [Rule], "crawl_delay": float|None}} + sitemaps."""
    groups = {}
    sitemaps = []
    current = []
    starting_group = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            if not starting_group:
                current = []
                starting_group = True
            current.append(value)
            groups.setdefault(value, {"rules": [], "crawl_delay": None})
            continue

        starting_group = False
        if field == "sitemap":
            sitemaps.append(value)
        elif field in ("allow", "disallow") and current:
            for agent in current:
                if field == "disallow" and value == "":
                    continue  # an empty Disallow means "nothing is disallowed"
                groups[agent]["rules"].append(Rule(field == "allow", value))
        elif field == "crawl-delay" and current:
            for agent in current:
                try:
                    groups[agent]["crawl_delay"] = float(value)
                except ValueError:
                    pass

    return groups, sitemaps


class Robots:
    def __init__(self, base_url, groups=None, sitemaps=(), text="", reachable=True):
        self.base_url = base_url
        self.groups = groups or {}
        self._sitemaps = list(sitemaps)
        self.text = text
        self.reachable = reachable

    @classmethod
    def load(cls, base_url, opener=None, timeout=20):
        """Fetch and parse /robots.txt for the origin of `base_url`."""
        parts = urllib.parse.urlsplit(base_url)
        root = f"{parts.scheme}://{parts.netloc}"
        try:
            text = _get(f"{root}/robots.txt", opener, timeout).decode("utf-8", "replace")
        except Exception:
            # Silence is not permission: deny everything and make the caller
            # decide, rather than crawling a site whose rules we never read.
            return cls(root, {}, [], "", reachable=False)
        groups, sitemaps = parse_rules(text)
        return cls(root, groups, sitemaps, text)

    @classmethod
    def from_text(cls, base_url, text):
        parts = urllib.parse.urlsplit(base_url)
        groups, sitemaps = parse_rules(text)
        return cls(f"{parts.scheme}://{parts.netloc}", groups, sitemaps, text)

    def _group(self, agent):
        agent = agent or ua.ua()
        # A named group wins over the wildcard, exactly one group applies.
        named = [key for key in self.groups if key != "*" and _agent_matches(key, agent)]
        if named:
            return self.groups[max(named, key=len)]
        return self.groups.get("*")

    def allowed(self, url, agent=None):
        if not self.reachable:
            return False
        group = self._group(agent)
        if not group:
            return True
        path = _path_of(url)
        best = None
        for rule in group["rules"]:
            if not rule.matches(path):
                continue
            # Longest match wins; on a tie Allow beats Disallow (RFC 9309).
            if (
                best is None
                or rule.length > best.length
                or (rule.length == best.length and rule.allow and not best.allow)
            ):
                best = rule
        return best.allow if best else True

    def crawl_delay(self, agent=None):
        group = self._group(agent)
        return group["crawl_delay"] if group else None

    def sitemaps(self):
        return list(self._sitemaps)

    def filter(self, urls, agent=None):
        """(allowed, blocked) — blocked is reported, never silently dropped."""
        allowed, blocked = [], []
        for url in urls:
            (allowed if self.allowed(url, agent) else blocked).append(url)
        return allowed, blocked


def _get(url, opener=None, timeout=20):
    if opener:
        return opener(url)
    request = urllib.request.Request(url, headers={"User-Agent": ua.ua()})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def parse_sitemap(xml_text):
    """Returns (child_sitemaps, page_urls). A sitemap index yields the former."""
    root = ET.fromstring(xml_text)
    tag = root.tag.replace(SITEMAP_NS, "")
    locations = [
        element.text.strip()
        for element in root.iter(f"{SITEMAP_NS}loc")
        if element.text and element.text.strip()
    ]
    if tag == "sitemapindex":
        return locations, []
    return [], locations


def walk_sitemaps(entry_urls, opener=None, limit=None, on_fetch=None):
    """Breadth-first over sitemap indexes. `limit` caps CHILD FETCHES, not URLs.

    Deliberately explicit: a top-level index can name a thousand children and
    tens of millions of pages, so the caller states how much of it to pull
    rather than discovering the size the hard way.
    """
    pending = list(entry_urls)
    seen_sitemaps = set()
    pages = []
    fetched = 0

    while pending:
        if limit is not None and fetched >= limit:
            break
        current = pending.pop(0)
        if current in seen_sitemaps:
            continue
        seen_sitemaps.add(current)
        fetched += 1
        if on_fetch:
            on_fetch(current, fetched)
        children, urls = parse_sitemap(_get(current, opener).decode("utf-8", "replace"))
        pending.extend(children)
        pages.extend(urls)

    return {
        "pages": pages,
        "fetched_sitemaps": sorted(seen_sitemaps),
        "unfetched_sitemaps": [u for u in pending if u not in seen_sitemaps],
    }
