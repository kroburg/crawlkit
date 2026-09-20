"""Which of several places this record is actually about.

Nearest is cheap to compute and wrong often enough to matter: a candidate
40 km away is not "close enough", it is a different place with a similar
name. `nearest` refuses anything the floor doesn't clear rather than handing
back the least-bad guess — see `core.best_under` for why that refusal is the
whole point.
"""

import math

from crawlkit import contract
from crawlkit.match.core import best_under

EARTH_RADIUS_M = 6_371_000


def haversine_m(a, b):
    """Great-circle distance in metres between two (lat, lon) points."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _default_key(candidate):
    return candidate["lat"], candidate["lon"]


def nearest(point, candidates, *, key=None, floor_m=None):
    """The closest candidate to `point`, refused if it's beyond `floor_m`.

    `floor_m` defaults to the shared floor rather than a literal here, so
    tightening the geo tolerance for every caller in the toolkit is a single
    constants-file edit, not a grep-and-replace across modules.
    """
    key = key or _default_key
    floor_m = contract.get("match.floors.geo_m") if floor_m is None else floor_m
    return best_under(
        candidates,
        lambda candidate: haversine_m(point, key(candidate)),
        floor_m,
        metric="geo_m",
    )
