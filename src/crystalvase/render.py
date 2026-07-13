"""Core renderer: draw an :class:`ase.Atoms` onto a matplotlib Axes as lit,
fully-vector spheres (an offset radial gradient built from nested filled circles),
with an optional unit-cell wireframe. Crisp at any zoom; no rasterised atoms.
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Circle
from matplotlib.collections import PatchCollection
from ase.data import covalent_radii
from ase.utils import rotate

from .palettes import get_palette
from .styles import get_style

#: Default viewing rotation (ASE ``rotate`` syntax): a very slight, nearly face-on tilt.
DEFAULT_ROTATION = "-6x,-5y,0z"
#: Default atom size as a fraction of the covalent radius.
DEFAULT_RADIUS_SCALE = 0.65
#: Number of nested circles per sphere (higher = smoother gradient, larger files).
NR = 220

_t = np.linspace(0.985, 0.0, NR)     # just inside the rim -> focal point
_u = 1.0 - _t                        # ~0 at edge, 1 at focal


def _smoothstep(x, a, b):
    x = np.clip((x - a) / (b - a), 0, 1)
    return x * x * (3 - 2 * x)


def _curves(S):
    mult = S["body0"] + S["body_gain"] * _smoothstep(_u, 0.0, S["body_end"])
    soft = _smoothstep(_u, S["soft_start"], 1.0) * S["soft_amt"]
    hot = _smoothstep(_u, S["hot_start"], 1.0) * S["hot_amt"]
    white = np.clip(soft + hot, 0.0, 0.97)
    return mult, white


def _tone(colors, S):
    if S["sat"] == 1.0 and S["bright"] == 1.0:
        return colors
    hsv = mcolors.rgb_to_hsv(np.clip(colors, 0, 1))
    hsv[:, 1] = np.clip(hsv[:, 1] * S["sat"], 0, 1)
    hsv[:, 2] = np.clip(hsv[:, 2] * S["bright"], 0, 1)
    return mcolors.hsv_to_rgb(hsv)


def _sphere_patches(cx, cy, r, color, dim, z0, S, mult, white):
    """Return (base disk, PatchCollection of rings) approximating a lit sphere."""
    color = np.asarray(color)
    spec = np.asarray(S["spec"])
    fx, fy = cx + S["hx"] * r, cy + S["hy"] * r

    ec = "none"
    if S["outline"] is not None:                    # optional darkened-own-colour rim
        ec = np.clip(color * S["outline"] * dim, 0, 1)
    base = Circle((cx, cy), r, facecolor=np.clip(color * S["edge_dark"] * dim, 0, 1),
                  edgecolor=ec, linewidth=S["outline_lw"], antialiased=True, zorder=z0)

    circles, facecolors = [], []
    for k in range(NR):
        t = _t[k]
        rgb = np.clip((color * mult[k]) * (1 - white[k]) + spec * white[k], 0, 1) * dim
        circles.append(Circle((cx * t + fx * (1 - t), cy * t + fy * (1 - t)), r * t))
        facecolors.append(rgb)
    pc = PatchCollection(circles, match_original=False)
    pc.set_facecolor(facecolors)
    pc.set_edgecolor("none")
    pc.set_antialiased(False)     # no inter-ring AA seams -> smooth gradient
    pc.set_zorder(z0)
    return base, pc


def _draw_cell(cell, R, ax, pos_offset):
    corners = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
                        [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1]], float)
    pts = (corners @ cell) @ R - pos_offset
    edges = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (2, 4),
             (2, 6), (3, 5), (3, 6), (4, 7), (5, 7), (6, 7)]
    for a, b in edges:
        ax.plot([pts[a, 0], pts[b, 0]], [pts[a, 1], pts[b, 1]],
                color="0.55", lw=0.6, zorder=1)
    return pts


def _maybe_reduce(atoms):
    """Return a Niggli-reduced copy (more orthogonal box) or the original on failure."""
    if atoms.cell.rank != 3:
        return atoms
    from ase.build import niggli_reduce
    a = atoms.copy()
    try:
        niggli_reduce(a)
        a.wrap()
        return a
    except Exception:
        return atoms


def render(atoms, ax=None, *, rotation=DEFAULT_ROTATION, palette="jmol",
           style="01_glossy", radius_scale=DEFAULT_RADIUS_SCALE,
           show_cell=True, reduce_cell=False):
    """Draw ``atoms`` onto ``ax`` (created if ``None``); returns the Axes.

    Parameters
    ----------
    atoms : ase.Atoms
    ax : matplotlib Axes, optional
    rotation : str
        Viewing rotation in ASE ``rotate`` syntax, e.g. ``"-6x,-5y,0z"``.
    palette : str or (n, 3) array
        Element colours: ``"jmol"`` (ASE default), ``"vesta"``, ``"vmd"``, or an array.
    style : str or dict
        Shade style name (see :data:`crystalvase.styles.STYLES`) or overrides dict.
    radius_scale : float
        Atom radius as a fraction of the covalent radius.
    show_cell : bool
        Draw the unit-cell wireframe (ignored for non-periodic systems).
    reduce_cell : bool
        Niggli-reduce the cell before drawing so oblique boxes are not heavily
        sheared. Changes which periodic images are shown; off by default.
    """
    palette = get_palette(palette)
    S = get_style(style)
    if reduce_cell:
        atoms = _maybe_reduce(atoms)
    if ax is None:
        _, ax = plt.subplots(figsize=(4, 4))

    mult, white = _curves(S)
    R = rotate(rotation)
    pos = atoms.positions @ R
    center = pos.mean(0)
    pos = pos - center
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]

    radii = covalent_radii[atoms.numbers] * radius_scale
    colors = _tone(palette[atoms.numbers].copy(), S)

    if len(z) > 1:
        znorm = (z - z.min()) / (np.ptp(z) + 1e-9)
    else:
        znorm = np.ones_like(z)
    dim = S["depth_lo"] + (1.0 - S["depth_lo"]) * znorm

    cell_pts = None
    if show_cell and atoms.cell.rank == 3:
        cell_pts = _draw_cell(atoms.cell[:], R, ax, pos_offset=center)

    for zi, i in enumerate(np.argsort(z)):          # back to front
        base, pc = _sphere_patches(x[i], y[i], radii[i], colors[i], dim[i],
                                   10 + 2 * zi, S, mult, white)
        ax.add_patch(base)
        ax.add_collection(pc)

    # limits enclose the atoms (with radii) and the whole cell box
    pad = (radii.max() if len(radii) else 1.0) + 0.4
    xs = [x.min() - pad, x.max() + pad]
    ys = [y.min() - pad, y.max() + pad]
    if cell_pts is not None:
        m = 0.3
        xs += [cell_pts[:, 0].min() - m, cell_pts[:, 0].max() + m]
        ys += [cell_pts[:, 1].min() - m, cell_pts[:, 1].max() + m]
    ax.set_xlim(min(xs), max(xs))
    ax.set_ylim(min(ys), max(ys))
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.patch.set_alpha(0.0)
    return ax
