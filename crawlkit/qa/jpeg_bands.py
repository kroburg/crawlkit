"""Detecting a truncated image that decodes perfectly well.

This is the subtlest corruption in a harvest. A JPEG cut mid-scan still opens,
still reports correct dimensions, and still renders — the decoder simply fills
the undecoded remainder with flat mid-grey. No header check, no size check and
no exception will tell you. Only the pixels will.

So: sample a few full-width strips across the lower half (truncation eats the
bottom of a top-down encode), box-average each strip down to a handful of
samples to kill per-pixel noise, and flag a strip whose mean sits on the fill
value AND whose variance is near zero.

Both halves of that conjunction are load-bearing. Uniformity alone would
condemn every photograph of an overcast sky; sitting exactly on 128 alone would
condemn any evenly-lit grey subject. Requiring both is what makes the rule safe
enough to delete files on.
"""

from crawlkit import contract

CFG = contract.get("qa.gray_band")


def _pil():
    try:
        from PIL import Image, ImageFile
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "crawlkit.qa.jpeg_bands needs pillow: pip install 'crawlkit[qa]'"
        ) from exc
    # Let the decoder hand back the damaged image instead of raising, or the
    # damage stays invisible to us as well.
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    return Image


def band_stats(image, fraction, cfg=None):
    """(mean per channel, variance) for one full-width strip."""
    cfg = cfg or CFG
    width, height = image.size
    top = int(height * fraction)
    strip = image.crop((0, top, width, min(height, top + cfg["strip_px"])))
    strip = strip.resize((cfg["samples"], 1))
    pixels = [strip.getpixel((x, 0)) for x in range(cfg["samples"])]
    means = [sum(channel) / len(pixels) for channel in zip(*pixels, strict=True)]
    variance = sum(sum((pixel[i] - means[i]) ** 2 for i in range(3)) for pixel in pixels) / len(
        pixels
    )
    return means, variance


def band_fractions(cfg=None):
    cfg = cfg or CFG
    return [
        cfg["height_start"] + cfg["height_span"] * index / cfg["bands"]
        for index in range(cfg["bands"])
    ]


def inspect(path, cfg=None):
    """Returns (bad, reason). A file that will not decode at all counts as bad."""
    cfg = cfg or CFG
    Image = _pil()
    try:
        image = Image.open(path).convert("RGB")
        image.load()
    except Exception as exc:
        return True, f"undecodable: {exc}"

    flat = 0
    for fraction in band_fractions(cfg):
        means, variance = band_stats(image, fraction, cfg)
        on_fill_value = all(
            abs(mean - cfg["target_level"]) < cfg["mean_tolerance"] for mean in means
        )
        featureless = variance < cfg["variance_max"]
        if on_fill_value and featureless:
            flat += 1

    if flat >= cfg["min_bad_bands"]:
        return True, f"{flat}/{cfg['bands']} lower bands are decoder fill grey"
    return False, "ok"


def scan(paths, cfg=None):
    """[(path, reason)] for every file that looks truncated."""
    return [(path, reason) for path in paths for bad, reason in [inspect(path, cfg)] if bad]
