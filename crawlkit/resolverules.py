"""Pin DNS for a host, the way curl --resolve does, but for a whole browser.

Needed when the local resolver flaps on a domain that is demonstrably up: the
canonical diagnostic is `dig +short @1.1.1.1 HOST` answering while `getent`
does not. Chromium takes `--host-resolver-rules=MAP host addr`.

Splitting each entry on every colon and taking fields 0 and 1 is the obvious
parse, and it mangles `[::1]` into `[` — silently dropping IPv6 support. Splitting on the
first colon only is both simpler and correct: a hostname cannot contain one.
"""

import ipaddress


def parse_entry(entry):
    host, separator, address = entry.partition(":")
    if not separator or not host or not address:
        raise ValueError(f"expected HOST:ADDRESS, got {entry!r}")
    literal = address[1:-1] if address.startswith("[") and address.endswith("]") else address
    try:
        parsed = ipaddress.ip_address(literal)
    except ValueError as exc:
        raise ValueError(f"{entry!r}: {literal!r} is not an IP address") from exc
    return host, f"[{literal}]" if parsed.version == 6 else literal


def rules(entries):
    """["h:1.2.3.4", "g:[::1]"] -> "MAP h 1.2.3.4,MAP g [::1]" (None if empty)."""
    pairs = [parse_entry(entry) for entry in entries or []]
    if not pairs:
        return None
    return ",".join(f"MAP {host} {address}" for host, address in pairs)


def launch_args(entries):
    rule = rules(entries)
    return [f"--host-resolver-rules={rule}"] if rule else []
