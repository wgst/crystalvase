"""Smoke tests: rendering works for periodic and molecular inputs, the API surface
holds, and vector PDFs contain no rasterised image XObjects.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np
import pytest
from ase.build import bulk, molecule

import crystalvase as cv


def test_palettes_and_styles_present():
    assert {"jmol", "vesta", "vmd"} <= set(cv.PALETTES)          # base palettes
    assert {"blossom", "emerald", "midnight"} <= set(cv.PALETTES)  # tone schemes
    assert {"clean", "cartoon", "realistic", "ase"} <= set(cv.STYLES)
    for arr in cv.PALETTES.values():
        assert arr.ndim == 2 and arr.shape[1] == 3


def test_render_each_family():
    for name in ("cartoon", "realistic", "ase"):
        ax = cv.render(molecule("H2O"), style=name, show_cell=False)
        assert ax is not None
        plt.close(ax.figure)


def test_render_returns_axes():
    ax = cv.render(bulk("Si", "diamond", a=5.43))
    assert ax.get_aspect() in (1.0, "equal")


def test_write_pdf_is_vector(tmp_path):
    out = tmp_path / "si.pdf"
    cv.write(bulk("NaCl", "rocksalt", a=5.64), str(out), style="realistic")
    data = out.read_bytes()
    assert data[:4] == b"%PDF"
    assert data.count(b"/Subtype /Image") == 0     # no rasterised atoms


def test_write_png_molecule(tmp_path):
    out = tmp_path / "h2o.png"
    cv.write(molecule("H2O"), str(out), palette="vmd", show_cell=False, dpi=80)
    assert out.stat().st_size > 0


def test_custom_rotation_and_palette_array(tmp_path):
    pal = np.tile([0.4, 0.6, 0.8], (120, 1))
    out = tmp_path / "rot.svg"
    cv.write(bulk("Cu", "fcc", a=3.6), str(out), rotation="30x,15y,0z", palette=pal)
    assert out.stat().st_size > 0


def test_unknown_names_raise():
    with pytest.raises(ValueError):
        cv.get_palette("nope")
    with pytest.raises(ValueError):
        cv.get_style("nope")


def test_bonds_vector(tmp_path):
    out = tmp_path / "eth.pdf"
    cv.write(molecule("CH3CH2OH"), str(out), bonds=True, show_cell=False)
    data = out.read_bytes()
    assert data[:4] == b"%PDF"
    assert data.count(b"/Subtype /Image") == 0     # bonds stay vector too


def test_formula_labels(tmp_path):
    """`formula` counts the drawn supercell; `reduced` gives the empirical unit.
    Periodic images are duplicates and must never inflate either."""
    from ase import Atoms
    a = 3.905
    sto = Atoms("SrTiO3", cell=[a, a, a], pbc=True,
                scaled_positions=[(0, 0, 0), (0.5, 0.5, 0.5),
                                  (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)])
    for lab in ("formula", "reduced"):
        for images in (False, True):
            ax = cv.render(sto, label=lab, supercell=(2, 2, 2), show_images=images)
            texts = [t.get_text() for t in ax.figure.findobj(plt.Text)]
            joined = "".join(texts)
            if lab == "formula":
                assert "54" not in joined            # 24 O, not the image-inflated count
                assert "24" in joined
            else:
                assert "Sr" in joined and "Ti" in joined and "3" in joined
                assert "24" not in joined and "8" not in joined   # reduced to SrTiO3
            plt.close(ax.figure)


def test_supercell_images_polyhedra():
    nacl = bulk("NaCl", "rocksalt", a=5.64)
    for ax in (
        cv.render(nacl, supercell=2),                       # int form
        cv.render(nacl, supercell=(2, 2, 1)),               # tuple form
        cv.render(nacl, show_images=True, bonds=True),      # boundary completion + bonds
        cv.render(nacl, supercell=(2, 2, 2), polyhedra="Na", bonds=True),
    ):
        assert ax is not None
        plt.close(ax.figure)
