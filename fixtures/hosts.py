"""Real hostnames without touching /etc/hosts or the network.

The host-bucketing scheduler and the IDNA encoder can only be tested with
several *distinct hostnames*, not several ports. Patching getaddrinfo gives
real names in-process; Chrome gets the same effect out-of-process through
--host-resolver-rules, which is the mechanism the DNS-pinning counter uses
anyway.
"""

import socket
from contextlib import contextmanager

IDN_HOST = "пример.test"
IDN_HOST_ASCII = IDN_HOST.encode("idna").decode("ascii")

# Distinct names on distinct loopback addresses: within-host serialization and
# cross-host parallelism are observable only if the buckets are really separate.
DEFAULT_MAP = {
    "alpha.test": "127.0.0.1",
    "beta.test": "127.0.0.2",
    "gamma.test": "127.0.0.3",
    "pinned.invalid": "127.0.0.1",
    "badchain.test": "127.0.0.1",
    IDN_HOST_ASCII: "127.0.0.1",
}


@contextmanager
def resolving(mapping=None):
    mapping = {**DEFAULT_MAP, **(mapping or {})}
    real = socket.getaddrinfo

    def fake(host, port, *args, **kwargs):
        return real(mapping.get(host, host), port, *args, **kwargs)

    socket.getaddrinfo = fake
    try:
        yield mapping
    finally:
        socket.getaddrinfo = real


def resolver_rules(mapping=None):
    """The same mapping in Chromium's --host-resolver-rules syntax."""
    mapping = {**DEFAULT_MAP, **(mapping or {})}
    return ",".join(f"MAP {host} {ip}" for host, ip in mapping.items())
