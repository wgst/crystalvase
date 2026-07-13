"""Regenerate the reference galleries in this folder (styles / palettes / sizes /
preview). Self-contained — uses crystalvase's built-in demo structures and the
three crystals in docs/demo/; the grid layout lives in the package (cv.grid).

    python docs/make_gallery.py
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
from ase.io import read

import crystalvase as cv

HERE = os.path.dirname(os.path.abspath(__file__))
WROT = "8x,-14y,0z"                     # nice view for the water box
wb, cl = cv.demo.water_box(), cv.demo.cluster()

# styles: every style on the water box (classic jmol red/white, xlarge)
cv.grid([(wb, dict(style=s, label=s)) for s in cv.STYLES], ncols=3,
        rotation=WROT, palette="jmol", radius_scale="xlarge", rings=160,
        suptitle="styles", save=f"{HERE}/styles.png")

# palettes: every palette on the diverse cluster (default style/size)
cv.grid([(cl, dict(palette=p, label=p)) for p in cv.PALETTES], ncols=6,
        rings=160, suptitle="palettes", save=f"{HERE}/palettes.png")

# sizes: the presets on the water box
cv.grid([(wb, dict(radius_scale=s, label=f"{s} ({cv.RADIUS_SCALES[s]})"))
         for s in ("small", "medium", "large", "xlarge")], ncols=4,
        rotation=WROT, palette="jmol", rings=160, save=f"{HERE}/sizes.png")

# hero preview: water + three crystals, one style each, formula labels.
# B2I6 uses a plain grey cell; the ase panel takes the bold black cell.
crystals = [read(f) for f in sorted(glob.glob(f"{HERE}/demo/*.xyz"))]
preview = [
    (wb, dict(style="realistic", palette="jmol", radius_scale="xlarge", rotation=WROT)),
    (crystals[0], dict(style="clean", cell_color="0.55", cell_width=0.6)),   # B2I6
    (crystals[1], dict(style="ase", cell_color="black", cell_width=1.1)),    # Bi10Cl24Ga6
    (crystals[2], dict(style="cartoon-soft")),                              # Na2O24P6Sn4
]
for atoms, kw in preview[1:]:
    kw["reduce_cell"] = True
cv.grid(preview, ncols=2, panel=4.0, label="formula", rings=140,
        save=[f"{HERE}/preview.png", f"{HERE}/preview.pdf"])
print("wrote styles / palettes / sizes / preview")
