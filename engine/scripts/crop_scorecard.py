#!/usr/bin/env python3
"""Crop & enlarge horizontal bands of a scorecard image so the ball-by-ball
grid becomes legible for transcription.

Usage:
    python scripts/crop_scorecard.py <image> <outdir> \
        --band name:y0:y1 [--band ...] [--x0 0.06] [--x1 0.865] [--scale 4]

y0/y1/x0/x1 are fractions (0..1) of image height/width. Each band is cropped
full-width (x0..x1) and upscaled by <scale> with LANCZOS, saved as <outdir>/<name>.png.
"""
import argparse, os
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("outdir")
    ap.add_argument("--band", action="append", default=[], help="name:y0:y1")
    ap.add_argument("--x0", type=float, default=0.06)
    ap.add_argument("--x1", type=float, default=0.865)
    ap.add_argument("--scale", type=int, default=4)
    args = ap.parse_args()

    im = Image.open(args.image).convert("L")
    W, H = im.size
    os.makedirs(args.outdir, exist_ok=True)
    for spec in args.band:
        name, y0, y1 = spec.split(":")
        y0, y1 = float(y0), float(y1)
        box = (int(args.x0 * W), int(y0 * H), int(args.x1 * W), int(y1 * H))
        c = im.crop(box)
        c = c.resize((c.width * args.scale, c.height * args.scale), Image.LANCZOS)
        out = os.path.join(args.outdir, f"{name}.png")
        c.save(out)
        print(f"{name}: {box} -> {c.size} {out}")


if __name__ == "__main__":
    main()
