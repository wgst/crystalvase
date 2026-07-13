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
#: Named atom-size presets (fraction of the covalent radius).
RADIUS_SCALES = {"small": 0.65, "medium": 0.85, "large": 1.05, "xlarge": 1.25}
#: Default atom size: preset name or fraction of the covalent radius.
DEFAULT_RADIUS_SCALE = "medium"


def _resolve_radius_scale(rs):
    """Resolve a preset name ("small"/"medium"/"large"/"xlarge") or number."""
    if isinstance(rs, str):
        if rs in RADIUS_SCALES:
            return RADIUS_SCALES[rs]
        try:
            return float(rs)
        except ValueError:
            raise ValueError(f"unknown radius scale {rs!r}; choose from "
                             f"{sorted(RADIUS_SCALES)} or pass a number")
    return float(rs)
#: Default number of nested circles per sphere (higher = smoother gradient,
#: larger vector files). Override per call with ``render(..., rings=N)``.
NR = 220


def _ring_ts(nr):
    """Ring shrink factors: just inside the rim -> focal point."""
    return np.linspace(0.985, 0.0, nr)


def _smoothstep(x, a, b):
    x = np.clip((x - a) / (b - a), 0, 1)
    return x * x * (3 - 2 * x)


def _curves(S, u):
    """Per-ring diffuse ramp (0..1) and specular blend, honouring ``posterize``."""
    if S["posterize"]:
        n = max(int(S["posterize"]), 2)          # cel shading: quantise into n bands
        u = np.minimum(np.floor(u * n) / (n - 1), 1.0)
    ramp = _smoothstep(u, 0.0, S["body_end"])
    soft = _smoothstep(u, S["soft_start"], 1.0) * S["soft_amt"]
    hot = _smoothstep(u, S["hot_start"], 1.0) * S["hot_amt"]
    white = np.clip(soft + hot, 0.0, 0.97)
    return ramp, white


def _tone(colors, S):
    if S["sat"] == 1.0 and S["bright"] == 1.0:
        return colors
    hsv = mcolors.rgb_to_hsv(np.clip(colors, 0, 1))
    hsv[:, 1] = np.clip(hsv[:, 1] * S["sat"], 0, 1)
    hsv[:, 2] = np.clip(hsv[:, 2] * S["bright"], 0, 1)
    return mcolors.hsv_to_rgb(hsv)


def _hue_shift(rgb, deg):
    if not deg:
        return np.asarray(rgb, float)
    hsv = mcolors.rgb_to_hsv(np.clip(np.asarray(rgb, float), 0, 1))
    hsv[0] = (hsv[0] + deg / 360.0) % 1.0
    return mcolors.hsv_to_rgb(hsv)


def _desaturate(rgb, amount):
    if amount <= 0:
        return rgb
    hsv = mcolors.rgb_to_hsv(np.clip(rgb, 0, 1))
    hsv[1] *= 1.0 - min(amount, 1.0)
    return mcolors.hsv_to_rgb(hsv)


def _outline_color(S, color, dim):
    if S["outline_color"] is not None:              # explicit rim (e.g. ASE black)
        return S["outline_color"]
    if S["outline"] is not None:                    # darkened-own-colour rim
        return np.clip(color * S["outline"] * dim, 0, 1)
    return "none"


def _sphere_patches(cx, cy, r, color, dim, z0, S, ts, ramp, white):
    """Return (base disk, PatchCollection of rings | None) for one atom."""
    color = np.asarray(color)
    ec = _outline_color(S, color, dim)

    if S["flat"]:                                   # single outlined disc (ASE look)
        base = Circle((cx, cy), r, facecolor=np.clip(color * S["body0"] * dim, 0, 1),
                      edgecolor=ec, linewidth=S["outline_lw"], antialiased=True,
                      zorder=z0)
        return base, None

    # shadow-end colour may lean towards a hue (tint and/or rotation)
    shadow = _hue_shift(color, S["shadow_hue"]) * np.asarray(S["shadow_tint"])
    dark = shadow * S["body0"]
    lit = color * (S["body0"] + S["body_gain"])
    spec = np.asarray(S["spec"])
    fx, fy = cx + S["hx"] * r, cy + S["hy"] * r

    base = Circle((cx, cy), r, facecolor=np.clip(shadow * S["edge_dark"] * dim, 0, 1),
                  edgecolor=ec, linewidth=S["outline_lw"], antialiased=True, zorder=z0)

    circles, facecolors = [], []
    for t, ramp_k, white_k in zip(ts, ramp, white):
        body = np.clip(dark + (lit - dark) * ramp_k, 0, 1)
        rgb = np.clip(body * (1 - white_k) + spec * white_k, 0, 1) * dim
        circles.append(Circle((cx * t + fx * (1 - t), cy * t + fy * (1 - t)), r * t))
        facecolors.append(rgb)
    pc = PatchCollection(circles, match_original=False)
    pc.set_facecolor(facecolors)
    pc.set_edgecolor("none")
    # smooth gradients: AA off so ring edges leave no seams; cel bands: AA on for
    # clean band boundaries (adjacent same-colour rings blend invisibly anyway)
    pc.set_antialiased(bool(S["posterize"]))
    pc.set_zorder(z0)
    return base, pc


def _draw_cell(cell, R, ax, pos_offset, color="0.55", lw=0.6):
    corners = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
                        [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1]], float)
    pts = (corners @ cell) @ R - pos_offset
    edges = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (2, 4),
             (2, 6), (3, 5), (3, 6), (4, 7), (5, 7), (6, 7)]
    for a, b in edges:
        ax.plot([pts[a, 0], pts[b, 0]], [pts[a, 1], pts[b, 1]],
                color=color, lw=lw, zorder=1)
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
           style="realistic", radius_scale=DEFAULT_RADIUS_SCALE,
           show_cell=True, reduce_cell=False, rings=None):
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
        Families: ``cartoon*``, ``realistic*`` (default), ``ase*``.
    radius_scale : str or float
        Atom size: preset ``"small"`` (0.65), ``"medium"`` (0.85, default),
        ``"large"`` (1.05), ``"xlarge"`` (1.25), or a fraction of the covalent
        radius.
    show_cell : bool
        Draw the unit-cell wireframe (ignored for non-periodic systems).
    reduce_cell : bool
        Niggli-reduce the cell before drawing so oblique boxes are not heavily
        sheared. Changes which periodic images are shown; off by default.
    rings : int, optional
        Gradient rings per sphere (default :data:`NR` = 220). Fewer rings give
        much smaller vector files at slightly coarser gradients — useful for
        many-panel figures or large systems.
    """
    palette = get_palette(palette)
    S = get_style(style)
    radius_scale = _resolve_radius_scale(radius_scale)
    if reduce_cell:
        atoms = _maybe_reduce(atoms)
    if ax is None:
        _, ax = plt.subplots(figsize=(4, 4))

    ts = _ring_ts(int(rings) if rings else NR)
    ramp, white = _curves(S, 1.0 - ts)
    R = rotate(rotation)
    pos = atoms.positions @ R
    center = pos.mean(0)
    pos = pos - center
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]

    radii = covalent_radii[atoms.numbers] * radius_scale
    colors = _tone(palette[atoms.numbers].copy(), S)

    # depth cue: back atoms dimmer (and optionally desaturated) so structure is clear
    if len(z) > 1:
        znorm = (z - z.min()) / (np.ptp(z) + 1e-9)
    else:
        znorm = np.ones_like(z)
    dim = S["depth_lo"] + (1.0 - S["depth_lo"]) * znorm

    cell_pts = None
    if show_cell and atoms.cell.rank == 3:
        cell_pts = _draw_cell(atoms.cell[:], R, ax, pos_offset=center,
                              color=S["cell_color"], lw=S["cell_lw"])

    for zi, i in enumerate(np.argsort(z)):          # back to front
        col = colors[i]
        if S["depth_desat"]:
            col = _desaturate(col, S["depth_desat"] * (1.0 - znorm[i]))
        base, pc = _sphere_patches(x[i], y[i], radii[i], col, dim[i],
                                   10 + 2 * zi, S, ts, ramp, white)
        ax.add_patch(base)
        if pc is not None:
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
