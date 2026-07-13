"""Batch-render frames from a trajectory / multi-frame file to vector PDFs.

Usage:
    python batch_extxyz.py INPUT.extxyz OUTDIR [--stride N] [--limit K] [--style S]
"""
import argparse
import os

from ase.io import read

import crystalvase as cv


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument("outdir")
    p.add_argument("--stride", type=int, default=1, help="take every Nth frame")
    p.add_argument("--limit", type=int, default=None, help="max number of frames")
    p.add_argument("--palette", default="jmol")
    p.add_argument("--style", default="01_glossy")
    p.add_argument("--ext", default="pdf", help="output extension (pdf, svg, png, jpg, ...)")
    p.add_argument("--reduce-cell", action="store_true",
                   help="Niggli-reduce oblique cells so boxes aren't sheared")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    frames = read(args.input, index=f"::{args.stride}")
    if not isinstance(frames, list):
        frames = [frames]
    if args.limit:
        frames = frames[:args.limit]

    for i, atoms in enumerate(frames):
        formula = atoms.get_chemical_formula()
        out = os.path.join(args.outdir, f"struct_{i:03d}_{formula}.{args.ext}")
        cv.write(atoms, out, palette=args.palette, style=args.style,
                  reduce_cell=args.reduce_cell)
        print("wrote", out)


if __name__ == "__main__":
    main()
