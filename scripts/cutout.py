#!/usr/bin/env python3
"""
cutout.py - flood-fill a studio backdrop out of a headshot into an alpha channel.

    python scripts/cutout.py photo.png assets/tarun.png

dotify.py treats an alpha channel as a subject cutout: nothing is drawn outside
it, and --equalize measures the subject's own histogram rather than a huge flat
background. A straight studio photo has no alpha, so its backdrop renders as a
solid slab of grey dots around the head and drags the equalisation with it.

The fill spreads inward from the border comparing each pixel to the neighbour it
came from, not to a single seed colour - a lit backdrop is a smooth gradient, so
local deltas stay tiny across it while the edge into hair, skin or collar is a
cliff. --step is that per-pixel tolerance and --sat rejects anything too colourful
to be a grey backdrop; raise --step if a backdrop survives, lower it if the fill
leaks into the subject.

Requires Pillow (same dependency as dotify.py).
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

try:
    from PIL import Image, ImageFilter
except ImportError:
    raise SystemExit("cutout.py needs Pillow:  pip install pillow")


def lum(p) -> float:
    return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]


def sat(p) -> int:
    return max(p[:3]) - min(p[:3])


def cutout(im: Image.Image, step: float, sat_max: int, feather: float) -> Image.Image:
    im = im.convert("RGBA")
    W, H = im.size
    px = im.load()

    bg = bytearray(W * H)
    q: deque[tuple[int, int]] = deque()
    for x in range(W):
        for y in (0, H - 1):
            q.append((x, y))
            bg[y * W + x] = 1
    for y in range(H):
        for x in (0, W - 1):
            if not bg[y * W + x]:
                q.append((x, y))
                bg[y * W + x] = 1

    while q:
        x, y = q.popleft()
        l0 = lum(px[x, y])
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not bg[ny * W + nx]:
                p = px[nx, ny]
                if abs(lum(p) - l0) <= step and sat(p) <= sat_max:
                    bg[ny * W + nx] = 1
                    q.append((nx, ny))

    mask = Image.frombytes("L", (W, H), bytes(255 - b * 255 for b in bg))
    # Close the pinholes a strict tolerance punches in the subject, then soften
    # the cut so the dot grid does not land on a hard jagged edge.
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    im.putalpha(mask)
    print(f"  {sum(bg) * 100 // (W * H)}% of the frame removed as background")
    return im


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", type=Path, help="source headshot")
    p.add_argument("out", type=Path, help="destination PNG (alpha is required, so PNG)")
    p.add_argument("--step", type=float, default=7.0,
                   help="per-pixel luminance tolerance while spreading (default 7)")
    p.add_argument("--sat", type=int, default=22,
                   help="max saturation a background pixel may have (default 22)")
    p.add_argument("--feather", type=float, default=1.2,
                   help="gaussian blur on the mask edge, 0 for a hard cut")
    args = p.parse_args(argv)

    im = cutout(Image.open(args.image), args.step, args.sat, args.feather)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    im.save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
