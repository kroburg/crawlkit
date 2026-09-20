"""The local target.

Every wall this toolkit counters is reproduced here, so the regression suite
never touches a third-party site. The endpoints are written to *fail the naive
implementation*, not merely to pass the good one:

  /challenge/autoreload  fails a one-shot content read, passes a re-evaluating
                         predicate, because the document is swapped underneath
  /challenge/clears-after  serves a 40 KB stub carrying <100 chars of TEXT, so
                         a body-length check on innerHTML passes on the stub
  /lazy                  grows on every scroll event, so a loop that caches
                         scrollHeight stops a third of the way down
  /media/<id>            403s without the page Referer, so an out-of-band
                         download of a URL scraped from the HTML gets nothing

Run standalone:  python -m fixtures.server --port 8080
"""

import argparse
import http.cookies
import json
import mimetypes
import threading
import time
import urllib.parse
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fixtures import media

TEXT_STUB = "Just a moment..."
CHALLENGE_COOKIE = "ck_session"

# Filler that inflates the stub's *markup* without contributing rendered text.
_NOISE = "".join(
    f"<script>/*{i:05d}*/var _{i}=function(){{return {i}*Math.random();}};</script>\n"
    for i in range(420)
)


class State:
    """Per-session counters, shared across threads."""

    def __init__(self):
        self.lock = threading.Lock()
        self.challenge_hits = defaultdict(int)
        self.navigations = defaultdict(int)
        self.arrivals = defaultdict(list)
        self.next_session = 0

    def session(self):
        with self.lock:
            self.next_session += 1
            return f"s{self.next_session}"

    def hit(self, session, path):
        with self.lock:
            self.challenge_hits[(session, path)] += 1
            self.navigations[path] += 1
            return self.challenge_hits[(session, path)]

    def arrive(self, host):
        with self.lock:
            self.arrivals[host].append(time.monotonic())

    def snapshot(self):
        with self.lock:
            return {
                "navigations": dict(self.navigations),
                "arrivals": {h: list(v) for h, v in self.arrivals.items()},
            }


STATE = State()


def _challenge_stub(reload_after_ms=None):
    reload_js = (
        f"<script>setTimeout(function(){{location.reload();}}, {reload_after_ms});</script>"
        if reload_after_ms
        else ""
    )
    return (
        "<html><head><title>Just a moment...</title></head>"
        f"<body><div id='cf'>{TEXT_STUB}</div>{_NOISE}{reload_js}</body></html>"
    ).encode()


def _real_page(marker="cleared"):
    body = " ".join(f"word{i}" for i in range(600))
    return (
        f"<html><head><title>Real content</title></head><body>"
        f"<h1 id='{marker}'>{marker}</h1><p>{body}</p></body></html>"
    ).encode()


LAZY_PAGE = b"""<html><head><title>Lazy</title>
<style>#top{min-height:2400px}section{min-height:900px}</style></head><body>
<div id="top">start</div><div id="sink"></div>
<script>
var added = 0, chunks = 6;
function grow() {
  if (added >= chunks) {
    if (!document.getElementById('done')) {
      var d = document.createElement('div'); d.id = 'done'; d.textContent = 'ALL LOADED';
      document.body.appendChild(d);
    }
    return;
  }
  added++;
  var s = document.createElement('section');
  s.className = 'chunk';
  s.setAttribute('data-chunk', String(added));
  var words = []; for (var i = 0; i < 400; i++) words.push('c' + added + 'w' + i);
  s.textContent = words.join(' ');
  document.getElementById('sink').appendChild(s);
}
window.addEventListener('scroll', grow, {passive: true});
grow();
</script></body></html>"""

LAZY_IMAGES = b"""<html><head><title>Gallery</title></head><body>
<div id="strip"></div>
<script>
var ids = ['aaaaaaaaaaaaaaaaaaaaaa1', 'aaaaaaaaaaaaaaaaaaaaaa2'];
var shown = 0;
function reveal() {
  if (shown >= ids.length) return;
  var im = new Image();
  im.src = '/media/' + ids[shown] + '?w=800';
  document.getElementById('strip').appendChild(im);
  var av = new Image();
  av.src = '/media/' + ids[shown] + '?w=64&crop_square=1';
  document.getElementById('strip').appendChild(av);
  shown++;
}
window.addEventListener('scroll', reveal, {passive: true});
reveal();
</script></body></html>"""

CONSENT_PAGE = b"""<html><head><title>Consent</title></head><body>
<div id="wall"><button id="agree">I agree</button></div>
<div id="content" style="display:none">the actual content</div>
<img src="/static/logo.png"><script src="/analytics.js"></script>
<script>
document.getElementById('agree').addEventListener('click', function () {
  document.getElementById('wall').style.display = 'none';
  document.getElementById('content').style.display = 'block';
  fetch('/api/after-consent').catch(function () {});
});
</script></body></html>"""

CSP_PAGE = b"""<html><head><title>CSP</title></head><body>
<div id="x">csp</div><script src="/blocked/evil.js"></script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "fixture/1.0"

    def log_message(self, *args):
        pass

    # -- helpers ---------------------------------------------------------

    def _session(self):
        raw = self.headers.get("Cookie", "")
        jar = http.cookies.SimpleCookie(raw)
        if CHALLENGE_COOKIE in jar:
            return jar[CHALLENGE_COOKIE].value, False
        return STATE.session(), True

    def _send(self, code, body=b"", ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def _origin(self):
        return f"http://{self.headers.get('Host', '')}"

    def _referer_is_on_origin(self):
        ref = self.headers.get("Referer", "")
        host = self.headers.get("Host", "")
        return bool(ref) and host and urllib.parse.urlsplit(ref).netloc == host

    # -- routing ---------------------------------------------------------

    def do_GET(self):
        self._route("GET")

    def do_HEAD(self):
        self._route("HEAD")

    def _route(self, method):
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        host = self.headers.get("Host", "").split(":")[0]

        if path == "/health":
            return self._send(200, b"ok", "text/plain")

        if path == "/robots.txt":
            # Shaped like a real one: open in general, with the expensive
            # dynamic endpoints closed and a sitemap index advertised.
            body = (
                "User-agent: *\n"
                "Allow: /\n"
                "Disallow: /query_results.asp\n"
                "Disallow: /author_items.asp\n"
                "Disallow: *.xls\n"
                "Crawl-delay: 2\n"
                f"Sitemap: http://{self.headers.get('Host', '')}/sitemaps/index.xml\n"
            )
            return self._send(200, body.encode(), "text/plain")

        if path.startswith("/sitemaps/"):
            return self._sitemap(path)

        if path.startswith("/item"):
            return self._send(200, _real_page(f"item-{query.get('id', ['0'])[0]}"))

        if path == "/throttled":
            STATE.arrive("throttled")
            return self._send(429, b"slow down", "text/plain", {"Retry-After": "120"})

        if path == "/refused":
            return self._send(403, b"forbidden", "text/plain")

        if path == "/stats":
            return self._send(200, json.dumps(STATE.snapshot()).encode(), "application/json")

        if path.startswith("/challenge/"):
            return self._challenge(path, query)

        if path == "/lazy":
            return self._send(200, LAZY_PAGE)

        if path == "/lazy-images":
            return self._send(200, LAZY_IMAGES)

        if path.startswith("/media/"):
            return self._media(path.removeprefix("/media/"), query)

        if path == "/api/items":
            return self._api_items()

        if path == "/api/items/malformed":
            return self._send(200, b'{"items": [{"id": 1}, {"id"', "application/json")

        if path == "/api/after-consent":
            return self._send(200, b'{"ok": true}', "application/json")

        if path == "/consent":
            return self._send(200, CONSENT_PAGE)

        if path == "/csp":
            return self._send(
                200,
                CSP_PAGE,
                extra={"Content-Security-Policy": "script-src 'unsafe-inline'; img-src 'self'"},
            )

        if path == "/analytics.js":
            return self._send(200, b"/* analytics */", "application/javascript")

        if path.startswith("/static/"):
            return self._send(200, b"\x89PNG\r\n\x1a\n", "image/png")

        if path.startswith("/blocked/"):
            return self._send(200, b"/* blocked by csp */", "application/javascript")

        if path == "/head405":
            if method == "HEAD":
                return self._send(405, b"", extra={"Allow": "GET"})
            return self._send(200, b"reachable only by GET")

        if path == "/head404":
            if method == "HEAD":
                return self._send(404)
            return self._send(200, b"this host rejects HEAD outright")

        if path == "/dead":
            return self._send(404, b"genuinely missing")

        if path in ("/slow.pdf", "/slow.bin"):
            time.sleep(float(query.get("delay", ["1.5"])[0]))
            ctype = "application/pdf" if path.endswith(".pdf") else "application/octet-stream"
            return self._send(200, b"%PDF-1.4 fixture", ctype)

        if path.startswith("/hostlog"):
            STATE.arrive(host)
            time.sleep(float(query.get("work", ["0"])[0]))
            return self._send(200, host.encode(), "text/plain")

        if path == "/пример/страница.pdf":
            return self._send(200, b"%PDF-1.4 cyrillic path", "application/pdf")

        if path == "/pinned":
            return self._send(200, f"resolved to {host}".encode(), "text/plain")

        ctype = mimetypes.guess_type(path)[0] or "text/html; charset=utf-8"
        return self._send(404, b"no such fixture endpoint", ctype)

    # -- endpoint bodies -------------------------------------------------

    def _challenge(self, path, query):
        session, fresh = self._session()
        hits = STATE.hit(session, path)
        # Max-Age matters: a session cookie is never written to disk, so a warm
        # profile could not carry it across processes — and real clearance
        # cookies do carry a TTL.
        cookie = (
            {"Set-Cookie": f"{CHALLENGE_COOKIE}={session}; Path=/; Max-Age=3600"} if fresh else {}
        )

        if path == "/challenge/never":
            return self._send(200, _challenge_stub(), extra=cookie)

        if path == "/challenge/autoreload":
            # The stub reloads itself; the third document is the real page. A
            # predicate evaluated once against the first document never sees it.
            if hits >= 3:
                return self._send(200, _real_page("autoreload-cleared"), extra=cookie)
            return self._send(200, _challenge_stub(reload_after_ms=400), extra=cookie)

        if path.startswith("/challenge/clears-after/"):
            need = int(path.rsplit("/", 1)[-1] or 3)
            if hits > need:
                return self._send(200, _real_page(), extra=cookie)
            return self._send(200, _challenge_stub(), extra=cookie)

        return self._send(404)

    def _sitemap(self, path):
        host = self.headers.get("Host", "")
        name = path.rsplit("/", 1)[-1]
        if name == "index.xml":
            children = "".join(
                f"<sitemap><loc>http://{host}/sitemaps/pages_{i}.xml</loc></sitemap>"
                for i in range(1, 4)
            )
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f"{children}</sitemapindex>"
            )
            return self._send(200, body.encode(), "application/xml")

        if name.startswith("pages_"):
            shard = int(name.removeprefix("pages_").removesuffix(".xml"))
            entries = "".join(
                f"<url><loc>http://{host}/item.asp?id={shard}{i:02d}</loc></url>"
                for i in range(1, 6)
            )
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f"{entries}</urlset>"
            )
            return self._send(200, body.encode(), "application/xml")

        return self._send(404)

    def _media(self, ident, query):
        if ident == "trunc":
            return self._send(200, media.truncated_jpeg(), "image/jpeg")
        if ident == "flatsky":
            return self._send(200, media.flat_gray_jpeg(), "image/jpeg")
        if ident == "good":
            return self._send(200, media.good_jpeg(1400), "image/jpeg")

        # Everything else is referer-gated, like a real CDN behind the same WAF.
        if not self._referer_is_on_origin():
            return self._send(403, b"referer required", "text/plain")
        width = int(query.get("w", ["800"])[0])
        if "crop_square" in query:
            return self._send(200, media.good_jpeg(64), "image/jpeg")
        return self._send(200, media.good_jpeg(width), "image/jpeg")

    def _api_items(self):
        same_origin = self.headers.get("Sec-Fetch-Site") == "same-origin"
        has_cookie = CHALLENGE_COOKIE in http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        if not (same_origin and self._referer_is_on_origin() and has_cookie):
            return self._send(
                403,
                b"blocked: call me from inside a cleared page of this origin",
                "text/plain",
            )
        payload = {"items": [{"id": i, "name": f"item-{i}"} for i in range(5)]}
        return self._send(200, json.dumps(payload).encode(), "application/json")


def serve(port=0, host="", https=False):
    """Start a server thread; returns (httpd, port)."""
    httpd = ThreadingHTTPServer((host, port), Handler)
    if https:
        from fixtures import tls

        httpd.socket = tls.wrap(httpd.socket)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument(
        "--https-port", type=int, default=0, help="also serve TLS with an untrusted chain"
    )
    args = ap.parse_args()

    _, port = serve(args.port)
    # Machine-readable and first: test harnesses wait on this exact line.
    print(f"LISTENING http://127.0.0.1:{port}", flush=True)
    if args.https_port:
        _, sport = serve(args.https_port, https=True)
        print(f"LISTENING_TLS https://127.0.0.1:{sport} (untrusted issuer)", flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
