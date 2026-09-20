"""Generated test images.

Three of these matter, and the third is the one people forget:

  good_jpeg       a complete image, big enough to pass the byte-level floor
  truncated_jpeg  cut mid-scan: no EOI marker, and a decoder told to tolerate
                  truncation fills the remainder with flat mid-gray (128)
  flat_gray_jpeg  a *genuine* overcast sky — flat-looking, complete, and NOT
                  the decoder's fill value. The false-positive control. A
                  detector that only asks "is the bottom uniform?" fails here,
                  which is why the real rule tests mean AND variance.

Images are generated once per session into .cache/ so the repo stays free of
binary fixtures.
"""

import io
import random
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / ".cache" / "media"


def _pil():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dev dependency
        raise RuntimeError("fixtures.media needs pillow: pip install -e '.[dev]'") from exc
    return Image


def _cached(name, build):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists():
        path.write_bytes(build())
    return path.read_bytes()


def _noisy(width, height, seed=7):
    """Detailed content, so the encoder cannot compress it to nothing."""
    Image = _pil()
    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    img.putdata(
        [
            (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for _ in range(width * height)
        ]
    )
    return img


def good_jpeg(width=1400):
    def build():
        height = max(64, width * 3 // 4)
        buf = io.BytesIO()
        _noisy(width, height).save(buf, "JPEG", quality=92)
        return buf.getvalue()

    return _cached(f"good_{width}.jpg", build)


def truncated_jpeg():
    """A real JPEG cut mid-scan — decodes fine, renders a gray tail."""

    def build():
        whole = good_jpeg(900)
        return whole[: int(len(whole) * 0.45)]

    return _cached("trunc.jpg", build)


def flat_gray_jpeg():
    """Overcast sky: low detail, complete, but not the decoder's fill colour."""

    def build():
        Image = _pil()
        width, height = 900, 600
        img = Image.new("RGB", (width, height))
        rng = random.Random(11)
        pixels = []
        for _ in range(height):
            for x in range(width):
                # Horizontal gradient survives the detector's box-averaging,
                # so the variance test sees real structure.
                level = 118 + int(46 * x / width) + rng.randint(-2, 2)
                pixels.append((level, level + 2, level + 8))
        img.putdata(pixels)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        return buf.getvalue()

    return _cached("flatsky.jpg", build)
