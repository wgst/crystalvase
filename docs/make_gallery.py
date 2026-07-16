"""Regenerate the reference galleries in this folder (styles / palettes / sizes /
preview). Self-contained — uses crystalvase's built-in demo structures and the
three crystals in docs/demo/; the grid layout lives in the package (cv.grid).

    python docs/make_gallery.py
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
from ase import Atoms
from ase.io import read

import crystalvase as cv

HERE = os.path.dirname(os.path.abspath(__file__))
WROT = "8x,-14y,0z"                     # nice view for the water box
wb, cl = cv.demo.water_box(), cv.demo.cluster()

#: cubic SrTiO3 perovskite (used for the polyhedra hero panel)
_A = 3.905
perovskite = Atoms("SrTiO3", cell=[_A, _A, _A], pbc=True,
                   scaled_positions=[(0, 0, 0), (0.5, 0.5, 0.5),
                                     (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)])

# styles: the nine base styles plus three hyperrealistic ones, on the water box
# (classic jmol red/white, xlarge). Force a uniform grey cell so the panels differ
# only in shading (clean's own cell is black). cv.STYLES has the full set.
# the three hyperrealistic panels show off distinct key lights: a wide bar, none at
# all (rim-lit only), and a tight dot (cv.STYLES also has clay / pearl / metallic)
GALLERY_STYLES = ["clean", "cartoon", "cartoon-dot", "cartoon-soft",
                  "realistic", "realistic-warm", "realistic-cool",
                  "ase", "ase-shaded",
                  "studio", "velvet", "gloss"]
cv.grid([(wb, dict(style=s, label=s)) for s in GALLERY_STYLES], ncols=3,
        rotation=WROT, palette="jmol", radius_scale="xlarge", rings=160,
        cell_color="0.55", cell_width=cv.DEFAULT_STYLE["cell_lw"],
        suptitle="styles", save=f"{HERE}/styles.png")

# palettes: every palette on the diverse cluster (default style/size)
cv.grid([(cl, dict(palette=p, label=p)) for p in cv.PALETTES], ncols=6,
        rings=160, suptitle="palettes", save=f"{HERE}/palettes.png")

# sizes: the presets on the water box
cv.grid([(wb, dict(radius_scale=s, label=f"{s} ({cv.RADIUS_SCALES[s]})"))
         for s in ("small", "medium", "large", "xlarge")], ncols=4,
        rotation=WROT, palette="jmol", rings=160, save=f"{HERE}/sizes.png")

# hero preview: water + two crystals + a perovskite supercell, one style each,
# formula labels. B2I6 uses a plain grey cell; the ase panel takes the bold black
# cell; the last panel shows hyperrealistic shading with coordination polyhedra.
crystals = [read(f) for f in sorted(glob.glob(f"{HERE}/demo/*.xyz"))]
preview = [
    (wb, dict(style="realistic", palette="jmol", radius_scale="xlarge", rotation=WROT)),
    (crystals[0], dict(style="clean", cell_color="0.55", reduce_cell=True,
                       cell_width=cv.DEFAULT_STYLE["cell_lw"], rotation=WROT)),  # BI3
    (crystals[1], dict(style="ase", cell_color="black", cell_width=1.1,
                       reduce_cell=True, supercell=(3, 3, 1),
                       rotation=WROT)),                                      # Bi5Ga3Cl12
    # rings=60 here: the env shader tessellates every sphere, and at the default 140
    # this one panel alone is a 20 MB PDF -- 60 is visually identical for ~3x less
    (perovskite, dict(style="velvet", polyhedra="Ti", polyhedra_color="#5b8fd0",
                      supercell=(2, 2, 2), show_images=True, palette="jmol",
                      atom_radii={"Sr": 1.0, "O": 0.28, "Ti": 0.5},
                      show_cell=False, rotation="8x,-12y,0z", rings=60)),    # SrTiO3
]
cv.grid(preview, ncols=2, panel=4.0, label="reduced", rings=140,
        save=f"{HERE}/preview.png")

# a small true-vector sample to link from the README: 360 atoms, zoomable forever,
# ~0.1 MB. (The full preview as a PDF is ~6 MB -- shaded spheres cost thousands of
# vector shapes each -- too heavy to carry in git; regenerate it locally if wanted.)
cv.write(crystals[1], f"{HERE}/vector-sample.pdf", style="ase", cell_color="black",
         cell_width=1.1, reduce_cell=True, supercell=(3, 3, 1), rotation=WROT,
         label="reduced", figsize=4.4)

# features: bonds (ball-and-stick molecule), coordination polyhedra, and a supercell
from ase.build import molecule, bulk                                # noqa: E402
eth = molecule("CH3CH2OH")
phos = read(f"{HERE}/demo/struct_44_Na2O24P6Sn4.xyz")
cv.grid([
    (eth, dict(style="studio", bonds=True, radius_scale=0.5, bond_radius=0.14,
               show_cell=False, rotation="15x,-20y,0z", label="bonds")),
    (perovskite, dict(polyhedra="Ti", polyhedra_color="#5b8fd0", show_images=True,
                      show_cell=False, rotation="16x,-18y,0z", label="polyhedra",
                      atom_radii={"Sr": 1.10, "O": 0.30, "Ti": 0.55})),
    (bulk("NaCl", "rocksalt", a=5.64, cubic=True),
     dict(supercell=(2, 2, 2), label="supercell")),
], ncols=3, palette="jmol", rings=150, save=f"{HERE}/features.png")

# per-style sweeps (like styles.png) so bonds and polyhedra can be judged in every style
_styles = sorted(cv.STYLES)
cv.grid([(eth, dict(style=s, bonds=True, radius_scale=0.5, show_cell=False, label=s))
         for s in _styles], ncols=3, palette="jmol", rings=150,
        suptitle="bonds", save=f"{HERE}/bond-styles.png")
# one SrTiO3 cell: a single TiO6 octahedron in the Sr cage reads clearly in every style
cv.grid([(perovskite, dict(style=s, polyhedra="Ti", polyhedra_color="#5b8fd0",
                           show_images=True, show_cell=False, label=s,
                           atom_radii={"Sr": 1.10, "O": 0.30, "Ti": 0.55},
                           rotation="16x,-18y,0z"))
         for s in _styles], ncols=3, palette="jmol", rings=150,
        suptitle="coordination polyhedra", save=f"{HERE}/polyhedra-styles.png")

print("wrote styles / palettes / sizes / preview / vector-sample / features /"
      " bond-styles / polyhedra-styles")
