"""Red-team probe for our own CAPTCHA using ddddocr.

  python scripts/captcha_probe.py img1.png [img2.png ...]

  from captcha_probe import solve
  solve("docs/distorted-image.png")  # -> "ekU3vk"
"""
import sys
from functools import lru_cache
from pathlib import Path

import ddddocr


@lru_cache(maxsize=1)
def _model():
    return ddddocr.DdddOcr(show_ad=False, beta=True)


def solve(path):
    """Return the CAPTCHA text read from the image at `path`."""
    return _model().classification(Path(path).read_bytes(), png_fix=True)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(f"{p}: {solve(p)}")
