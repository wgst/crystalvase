"""Regenerate the reference galleries in this folder (styles / palettes / sizes /
preview). Self-contained: builds its demo structures with ASE, so it needs only
crystalvase + ase installed (no external data files).

    python docs/make_gallery.py
"""
import os

import glob

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from ase import Atoms
from ase.build import molecule
from ase.io import read

import crystalvase as cv

HERE = os.path.dirname(os.path.abspath(__file__))

STYLES = ["clean", "cartoon", "cartoon-dot", "cartoon-soft",
          "realistic", "realistic-warm", "realistic-cool", "ase", "ase-shaded"]
PALETTES = ["jmol", "vesta", "vmd", "pastel", "muted", "vivid", "deep",
            "forest", "wine", "emerald", "olive", "mint", "blossom",
            "tropical", "neon", "sage", "midnight"]
SIZES = ["small", "medium", "large", "xlarge"]


def water_box(n=3, spacing=3.1, seed=7):
    """n^3 randomly oriented water molecules on a jittered grid (O + H only)."""
    rng = np.random.default_rng(seed)
    L = n * spacing
    box = Atoms(cell=[L, L, L], pbc=True)
    for ix in range(n):
        for iy in range(n):
            for iz in range(n):
                m = molecule("H2O")
                m.rotate(rng.uniform(0, 360), rng.standard_normal(3) + 1e-6)
                c = (np.array([ix, iy, iz]) + 0.5) * spacing + rng.uniform(-0.5, 0.5, 3)
                m.translate(c - m.get_positions().mean(0))
                box += m
    return box


def demo_cluster(seed=3):
    """A small jittered box of chemically diverse atoms, so every palette shows a
    good spread of element colours (illustrative, not a physical structure)."""
    syms = ["O", "N", "S", "F", "Cl", "C", "H", "P",
            "Na", "K", "Ti", "Fe", "Cu", "Br"]
    rng = np.random.default_rng(seed)
    L, n = 12.0, 3
    pts, chosen = [], []
    for i, (ix, iy, iz) in enumerate([(x, y, z) for x in range(n)
                                      for y in range(n) for z in range(n)]):
        if i >= len(syms):
            break
        pts.append((np.array([ix, iy, iz]) + 0.5) * (L / n) + rng.uniform(-0.7, 0.7, 3))
        chosen.append(syms[i])
    return Atoms(chosen, positions=pts, cell=[L, L, L], pbc=True)


def _grid(items, render_one, ncol, title_fn, path, panel=3.4, dpi=200, suptitle=None):
    nrow = int(np.ceil(len(items) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(panel * ncol, panel * nrow),
                             squeeze=False)
    for ax, item in zip(axes.flat, items):
        render_one(item, ax)
        ax.set_title(title_fn(item), fontsize=12)
    for ax in axes.flat[len(items):]:
        ax.set_axis_off()
    if suptitle:
        fig.suptitle(suptitle, fontsize=14)
    fig.savefig(path, bbox_inches="tight", dpi=dpi)
    plt.close(fig)
    print("wrote", os.path.relpath(path, HERE))


def main():
    wb = water_box()
    cl = demo_cluster()

    # water renders read best in classic jmol red/white at xlarge
    WPAL, WSIZE, WROT = "jmol", "xlarge", "8x,-14y,0z"

    # styles: every style on the water box
    _grid(STYLES, lambda s, ax: cv.render(wb, ax, style=s, palette=WPAL,
                                          radius_scale=WSIZE, rotation=WROT, rings=160),
          ncol=3, title_fn=str, path=f"{HERE}/styles.png",
          suptitle=f"styles  (palette={WPAL}, size={WSIZE})")

    # palettes: every palette on the diverse cluster, default style/size
    _grid(PALETTES, lambda p, ax: cv.render(cl, ax, palette=p, rings=160),
          ncol=6, title_fn=str, path=f"{HERE}/palettes.png",
          suptitle=f"palettes  (style={cv.DEFAULT_STYLE_NAME})")

    # sizes: the presets on the water box (palette fixed so only size varies)
    _grid(SIZES, lambda s, ax: cv.render(wb, ax, radius_scale=s, palette=WPAL,
                                        rotation=WROT, rings=160),
          ncol=4, title_fn=lambda s: f"{s}  ({cv.RADIUS_SCALES[s]})",
          path=f"{HERE}/sizes.png", suptitle=f"sizes  (palette={WPAL})")

    # hero preview: a 2x2 showcase, each panel in a different style — the water
    # box (realistic, jmol/xlarge) plus three crystals from docs/demo/ (default
    # palette/size). Saved as a high-res PNG (README) and a true-vector PDF.
    demo = [read(f) for f in sorted(glob.glob(f"{HERE}/demo/*.xyz"))]
    demo_styles = ["clean", "cartoon-dot", "cartoon-soft"]
    fig, axes = plt.subplots(2, 2, figsize=(8, 8))
    cv.render(wb, axes.flat[0], style="realistic", palette=WPAL, radius_scale=WSIZE,
              rotation=WROT, rings=140)
    for ax, atoms, st in zip(axes.flat[1:], demo, demo_styles):
        cv.render(atoms, ax, style=st, reduce_cell=True, rings=140)
    for ax in axes.flat[1 + len(demo):]:
        ax.set_axis_off()
    fig.savefig(f"{HERE}/preview.png", bbox_inches="tight", dpi=200)
    fig.savefig(f"{HERE}/preview.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote preview.png + preview.pdf")


if __name__ == "__main__":
    main()
