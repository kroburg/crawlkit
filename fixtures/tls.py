"""A TLS endpoint the stdlib refuses and a browser would accept.

Real cause in the wild: a server that ships its leaf without the intermediate.
Browsers repair that silently by fetching the missing cert via AIA; Python's
stdlib does not, so the probe sees an SSL error on a site that is demonstrably
up. Reproducing AIA-repair offline is not worth it — an untrusted issuer
raises through the exact same code path, which is what the probe ladder's
three-level TLS classification is being tested on.
"""

import ssl
import subprocess
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / ".cache" / "tls"
HOSTNAME = "badchain.test"


def ensure_cert():
    CACHE.mkdir(parents=True, exist_ok=True)
    cert, key = CACHE / "leaf.pem", CACHE / "leaf.key"
    if cert.exists() and key.exists():
        return cert, key
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "3650",
            "-subj",
            f"/CN={HOSTNAME}",
            "-addext",
            f"subjectAltName=DNS:{HOSTNAME},IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


def wrap(sock):
    cert, key = ensure_cert()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    return ctx.wrap_socket(sock, server_side=True)
