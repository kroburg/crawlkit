"""The probe ladder: is this URL actually reachable?

Pure stdlib, deliberately. A link checker is the thing you want to run on a
bare interpreter on someone else's box five years from now, and
tests/test_stdlib_purity.py fails the build if an import creeps in here.

The ladder is HEAD -> relaxed-TLS retry -> GET, and its one surprising rule is
that **the last attempt wins, even if it is worse than the first**. A browser
issuing a GET is what a reader will actually experience, so that is the verdict
worth recording. Reporting the more flattering HEAD result instead is how a
checker ends up disagreeing with the human looking at the same page.
"""

import ssl
import urllib.error
import urllib.parse
import urllib.request

from crawlkit import contract, ua

LIVE_HTTP = contract.LIVE_HTTP
FAILURE = contract.FAILURE

TIMEOUT_S = contract.get("http.timeout_s")
PDF_TIMEOUT_S = contract.get("http.pdf_timeout_s")


def timeout_for(url, timeout_s=None, pdf_timeout_s=None):
    """PDFs are slow to first byte; a short cap turns a live file into a false -1."""
    if url.lower().split("?")[0].endswith(".pdf"):
        return pdf_timeout_s if pdf_timeout_s is not None else PDF_TIMEOUT_S
    return timeout_s if timeout_s is not None else TIMEOUT_S


def encode_url(url):
    """IDNA the host, percent-encode the rest, and stay idempotent.

    Host and path need *different* encodings — punycode for one, percent for
    the other — and applying either to the wrong component yields a URL that
    resolves nowhere. Keeping "%" in every safe set is what makes a second pass
    a no-op instead of turning %D0 into %25D0.
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    try:
        host_ascii = host.encode("idna").decode("ascii") if host else ""
    except (UnicodeError, UnicodeEncodeError):
        # Over-long or empty labels: pass the host through and let the probe
        # fail honestly rather than dropping the URL here.
        host_ascii = host

    netloc = host_ascii
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    if parts.username:
        credentials = parts.username
        if parts.password:
            credentials = f"{credentials}:{parts.password}"
        netloc = f"{credentials}@{netloc}"

    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            netloc,
            urllib.parse.quote(parts.path, safe="/%"),
            urllib.parse.quote(parts.query, safe="=&%"),
            urllib.parse.quote(parts.fragment, safe="%"),
        )
    )


def is_tls_error(exc):
    """urllib buries TLS failures inconsistently, so look in three places."""
    if isinstance(exc, ssl.SSLError):
        return True
    if isinstance(getattr(exc, "reason", None), ssl.SSLError):
        return True
    message = str(exc).lower()
    return "certificate" in message or "ssl" in message


def _open(encoded, method, timeout, verify):
    ctx = ssl.create_default_context()
    if not verify:
        # Order matters: disabling verify_mode while hostname checking is still
        # on raises.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    request = urllib.request.Request(encoded, method=method, headers={"User-Agent": ua.ua()})
    return urllib.request.urlopen(request, timeout=timeout, context=ctx)


def probe(encoded, method, timeout):
    """One rung: status code, retrying once with relaxed TLS on a cert error."""
    try:
        with _open(encoded, method, timeout, verify=True) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        # An HTTPError IS a response. Catching it under the generic handler
        # below would relabel every 404 as a connection failure.
        return exc.code
    except Exception as exc:
        if not is_tls_error(exc):
            return FAILURE
        try:
            with _open(encoded, method, timeout, verify=False) as resp:
                return resp.status
        except urllib.error.HTTPError as exc2:
            return exc2.code
        except Exception:
            return FAILURE


def check_one(url, timeout_s=None, pdf_timeout_s=None):
    """Final status for one URL. HEAD first, GET whenever HEAD is inconclusive."""
    try:
        encoded = encode_url(url)
    except Exception:
        return FAILURE
    timeout = timeout_for(url, timeout_s, pdf_timeout_s)
    head = probe(encoded, "HEAD", timeout)
    if head in LIVE_HTTP:
        return head
    return probe(encoded, "GET", timeout)
