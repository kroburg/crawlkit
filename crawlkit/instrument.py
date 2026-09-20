"""Watching what a page does, from inside it.

`add_init_script` runs before any script the document itself loads, which is
the only hook early enough to catch events fired during initial parse. A
listener attached after `goto` has already missed them — the usual symptom is
an empty violation list on a page that visibly failed to load a resource.

Useful for finding out why a page is broken under automation but fine in your
own browser: blocked resources, failed requests, console errors.
"""

COLLECTOR = """
(() => {
  window.__ck = window.__ck || { csp: [], errors: [] };
  document.addEventListener('securitypolicyviolation', (e) => {
    window.__ck.csp.push({
      directive: e.effectiveDirective || e.violatedDirective,
      blocked: e.blockedURI,
      source: e.sourceFile || null,
    });
  });
  window.addEventListener('error', (e) => {
    window.__ck.errors.push(String((e && e.message) || e));
  });
})();
"""


class Recorder:
    """Attach before navigating; read after."""

    def __init__(self):
        self.requests = []
        self.failed = []
        self.console = []

    def attach(self, page):
        page.add_init_script(COLLECTOR)
        page.on(
            "request", lambda request: self.requests.append((request.resource_type, request.url))
        )
        page.on(
            "requestfailed",
            lambda request: self.failed.append((request.url, (request.failure or ""))),
        )
        page.on("console", lambda message: self.console.append((message.type, message.text)))
        return self

    def violations(self, page):
        try:
            return page.evaluate("(window.__ck && window.__ck.csp) || []")
        except Exception:
            return []

    def page_errors(self, page):
        try:
            return page.evaluate("(window.__ck && window.__ck.errors) || []")
        except Exception:
            return []
