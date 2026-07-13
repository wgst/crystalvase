"""Render one structure under all 10 shade styles (colours fixed) in a 2x5 grid.

Usage:
    python compare_styles.py INPUT OUT.png [--index I] [--palette P]
"""
import argparse
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ase.io import read

import crystalvase as cv


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--palette", default="jmol")
    p.add_argument("--reduce-cell", action="store_true")
    args = p.parse_args()

    atoms = read(args.input, index=args.index)
    names = sorted(cv.STYLES)
    ncol = 5
    nrow = math.ceil(len(names) / ncol)

    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 4 * nrow), squeeze=False)
    for ax, name in zip(axes.flat, names):
        cv.render(atoms, ax, palette=args.palette, style=name, reduce_cell=args.reduce_cell)
        ax.set_title(name, fontsize=12)
    for ax in axes.flat[len(names):]:
        ax.set_axis_off()
    fig.suptitle(f"{atoms.get_chemical_formula()} — shade styles (palette={args.palette})",
                 fontsize=14)
    fig.savefig(args.output, bbox_inches="tight", dpi=130)
    print("wrote", args.output)


if __name__ == "__main__":
    main()
