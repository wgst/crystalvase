"""Render one structure under every colour palette, side by side, to compare.

Usage:
    python compare_palettes.py INPUT OUT.png [--index I] [--style S]
"""
import argparse

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
    p.add_argument("--style", default="realistic")
    p.add_argument("--reduce-cell", action="store_true")
    args = p.parse_args()

    atoms = read(args.input, index=args.index)
    names = list(cv.PALETTES)

    fig, axes = plt.subplots(1, len(names), figsize=(3.6 * len(names), 3.6), squeeze=False)
    for ax, name in zip(axes.flat, names):
        cv.render(atoms, ax, palette=name, style=args.style, reduce_cell=args.reduce_cell)
        ax.set_title(name, fontsize=12)
    fig.suptitle(f"{atoms.get_chemical_formula()} — palettes (style={args.style})")
    fig.savefig(args.output, bbox_inches="tight", dpi=140)
    print("wrote", args.output)


if __name__ == "__main__":
    main()
