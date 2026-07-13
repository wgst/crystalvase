"""Element colour palettes, each an ``(n_elements, 3)`` RGB-in-[0,1] array indexed
by atomic number (row 0 is a dummy for Z=0).

- ``jmol``  : ASE's native default element colours (``ase.data.colors.jmol_colors``).
- ``vesta`` : VESTA scheme, read from pymatgen if installed; otherwise falls back to Jmol.
- ``vmd``   : curated VMD-style palette (cyan carbon + saturated "pure" colours),
              built on top of Jmol. Exact for common elements; a few transition-metal
              shades are approximate.
"""
import warnings

import numpy as np
from ase.data import chemical_symbols
from ase.data.colors import jmol_colors as _ase_jmol

_L = len(chemical_symbols)          # 119 (covers Z up to 118 + dummy row 0)
_GREY = (0.5, 0.5, 0.5)


def _blank():
    arr = np.empty((_L, 3))
    arr[:] = _GREY
    return arr


def _from_ase(arr_like):
    arr = _blank()
    src = np.asarray(arr_like, dtype=float)
    n = min(_L, len(src))
    arr[:n] = src[:n]
    return arr


def _from_symbol_table(table, base):
    """Overlay a {symbol: (r,g,b in 0-255)} dict onto a copy of ``base``."""
    arr = base.copy()
    for sym, rgb in table.items():
        if sym in chemical_symbols:
            arr[chemical_symbols.index(sym)] = np.asarray(rgb, dtype=float) / 255.0
    return arr


# ---- jmol (ASE default) ----
jmol_colors = _from_ase(_ase_jmol)


# ---- vesta (optional, via pymatgen) ----
def _load_vesta():
    try:
        import os
        import yaml
        import pymatgen.vis as _pmgvis
    except Exception:
        return None
    try:
        path = os.path.join(os.path.dirname(_pmgvis.__file__), "ElementColorSchemes.yaml")
        with open(path) as fh:
            table = yaml.safe_load(fh)["VESTA"]
    except Exception:
        return None
    return _from_symbol_table(table, _blank())


_vesta = _load_vesta()
if _vesta is None:
    warnings.warn("pymatgen not available; 'vesta' palette falls back to 'jmol'. "
                  "Install the 'vesta' extra (pip install crystalvase[vesta]).")
    _vesta = jmol_colors.copy()
vesta_colors = _vesta


# ---- vmd (curated, no external data needed) ----
_VMD = {
    "H": (255, 255, 255), "C": (76, 204, 204), "N": (48, 80, 248), "O": (255, 13, 13),
    "F": (144, 224, 80), "Cl": (48, 224, 48), "Br": (166, 41, 41), "I": (148, 0, 211),
    "S": (255, 255, 48), "P": (255, 128, 0), "B": (255, 181, 181), "Si": (200, 165, 105),
    "Se": (255, 161, 0), "As": (189, 128, 227), "Te": (212, 122, 0), "Sb": (158, 99, 181),
    "Li": (128, 90, 250), "Na": (75, 90, 245), "K": (143, 64, 212), "Rb": (112, 46, 176),
    "Cs": (87, 23, 143), "Be": (194, 255, 0), "Mg": (138, 255, 0), "Ca": (61, 255, 0),
    "Sr": (0, 255, 0), "Ba": (0, 201, 0), "Al": (191, 166, 166), "Ga": (194, 143, 143),
    "In": (167, 117, 115), "Sn": (102, 128, 128), "Tl": (166, 84, 77), "Bi": (158, 79, 181),
    "Ge": (102, 143, 143), "Ti": (191, 194, 199), "V": (166, 166, 171), "Cr": (138, 153, 199),
    "Mn": (156, 122, 199), "Fe": (224, 102, 51), "Zn": (125, 128, 176), "Y": (148, 255, 255),
    "Zr": (148, 224, 224), "Nb": (115, 194, 201), "Mo": (84, 181, 181), "Cd": (255, 217, 143),
    "Hf": (77, 194, 255), "Ta": (77, 166, 255), "Re": (38, 125, 171), "La": (112, 212, 255),
    "Lu": (0, 171, 36), "Cu": (200, 128, 51), "Ag": (192, 192, 192), "Au": (255, 209, 35),
    "Pd": (0, 105, 133), "Pt": (208, 208, 224), "Rh": (10, 125, 140), "Ir": (23, 84, 135),
    "Ni": (80, 208, 80), "Co": (240, 144, 160), "Hg": (184, 184, 208), "Ar": (128, 209, 227),
}
vmd_colors = _from_symbol_table(_VMD, jmol_colors)


def adjust(palette, sat=1.0, bright=1.0, mix_white=0.0, hue=0.0):
    """Return an adjusted copy of ``palette``: optionally mix towards white
    (``mix_white`` in 0..1, pastelises), rotate all hues by ``hue`` degrees
    (a genuinely different colour scheme — element distinctions are kept but
    conventional colours like red oxygen change), then scale HSV saturation
    and value."""
    import matplotlib.colors as mcolors
    arr = np.clip(np.asarray(get_palette(palette), dtype=float).copy(), 0, 1)
    if mix_white:
        arr = arr * (1.0 - mix_white) + mix_white
    hsv = mcolors.rgb_to_hsv(arr)
    if hue:
        hsv[:, 0] = (hsv[:, 0] + hue / 360.0) % 1.0
    hsv[:, 1] = np.clip(hsv[:, 1] * sat, 0, 1)
    hsv[:, 2] = np.clip(hsv[:, 2] * bright, 0, 1)
    return mcolors.hsv_to_rgb(hsv)


PALETTES = {"jmol": jmol_colors, "vesta": vesta_colors, "vmd": vmd_colors}


def get_palette(palette):
    """Resolve ``palette`` (name in :data:`PALETTES` or an ``(n, 3)`` array) to an array."""
    if isinstance(palette, str):
        try:
            return PALETTES[palette]
        except KeyError:
            raise ValueError(f"unknown palette {palette!r}; choose from {sorted(PALETTES)}")
    arr = np.asarray(palette, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("a custom palette must be an (n_elements, 3) RGB array")
    return arr


# tone-adjusted takes on the ASE/Jmol colours (same element hues, prettier tones)
PALETTES.update(
    pastel=adjust(jmol_colors, sat=0.80, mix_white=0.30),   # soft, lifted towards white
    muted=adjust(jmol_colors, sat=0.60, bright=0.95),        # calm flat-design tones
    vivid=adjust(jmol_colors, sat=1.45, bright=1.03),        # punchy saturated
    deep=adjust(jmol_colors, sat=1.15, bright=0.80),         # rich darker jewel tones
)
