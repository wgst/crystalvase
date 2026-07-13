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
#: Default element colour palette (name in :data:`crystalvase.PALETTES`).
DEFAULT_PALETTE = "blossom"
#: Default shade style (name in :data:`crystalvase.STYLES`).
DEFAULT_STYLE_NAME = "realistic"
#: Named atom-size presets (fraction of the covalent radius).
RADIUS_SCALES = {"small": 0.65, "medium": 0.85, "large": 1.05, "xlarge": 1.25}
#: Default atom size: preset name or fraction of the covalent radius.
DEFAULT_RADIUS_SCALE = "large"


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


_CELL_CORNERS = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
                          [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1]], float)
_CELL_EDGES = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (2, 4),
               (2, 6), (3, 5), (3, 6), (4, 7), (5, 7), (6, 7)]


def _cell_corners(cell, R, pos_offset):
    """Projected unit-cell corners, shape (8, 3) with a depth (z) column."""
    return (_CELL_CORNERS @ cell) @ R - pos_offset


def _draw_cell(corners, ax, zof, color="0.55", lw=0.6, nseg=24):
    """Draw the wireframe box as short segments, each z-ordered by its own depth
    so the box passes through the structure — partly in front, partly behind."""
    ts = np.linspace(0.0, 1.0, nseg + 1)
    for a, b in _CELL_EDGES:
        pa, pb = corners[a], corners[b]
        seg = pa[None, :] + ts[:, None] * (pb - pa)[None, :]     # (nseg+1, 3)
        for k in range(nseg):
            p0, p1 = seg[k], seg[k + 1]
            ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=color, lw=lw,
                    solid_capstyle="round", zorder=zof(0.5 * (p0[2] + p1[2])))


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


def render(atoms, ax=None, *, rotation=DEFAULT_ROTATION, palette=DEFAULT_PALETTE,
           style=DEFAULT_STYLE_NAME, radius_scale=DEFAULT_RADIUS_SCALE,
           show_cell=True, reduce_cell=False, rings=None,
           cell_color=None, cell_width=None,
           label=None, label_size=13, label_weight="extra bold", label_rotation=0):
    """Draw ``atoms`` onto ``ax`` (created if ``None``); returns the Axes.

    Parameters
    ----------
    atoms : ase.Atoms
    ax : matplotlib Axes, optional
    rotation : str
        Viewing rotation in ASE ``rotate`` syntax, e.g. ``"-6x,-5y,0z"``.
    palette : str or (n, 3) array
        Element colours: a name in :data:`crystalvase.PALETTES` (default
        ``"blossom"``) or an ``(n, 3)`` array. ``"jmol"`` is the ASE palette.
    style : str or dict
        Shade style name (see :data:`crystalvase.styles.STYLES`) or overrides dict.
        Default ``"realistic"``; families ``clean``, ``cartoon*``, ``realistic*``, ``ase*``.
    radius_scale : str or float
        Atom size: preset ``"small"`` (0.65), ``"medium"`` (0.85),
        ``"large"`` (1.05), ``"xlarge"`` (1.25, default), or a fraction of the
        covalent radius.
    show_cell : bool
        Draw the unit-cell wireframe (ignored for non-periodic systems).
    reduce_cell : bool
        Niggli-reduce the cell before drawing so oblique boxes are not heavily
        sheared. Changes which periodic images are shown; off by default.
    rings : int, optional
        Gradient rings per sphere (default :data:`NR` = 220). Fewer rings give
        much smaller vector files at slightly coarser gradients — useful for
        many-panel figures or large systems.
    cell_color : matplotlib colour, optional
        Colour of the unit-cell wireframe (e.g. ``"black"``, ``"lightgray"``,
        ``"dimgray"``, ``"0.3"``, a hex string or RGB tuple). Defaults to the
        style's ``cell_color`` (black for ``clean``, mid-grey otherwise).
    cell_width : float, optional
        Line width of the unit-cell wireframe; defaults to the style's value.
    label : str, optional
        Text drawn below the figure (e.g. a chemical formula). Pass ``"formula"``
        for the structure's chemical formula. No label if ``None``.
    label_size : float
        Label font size (default 13).
    label_weight : matplotlib font weight
        Label boldness — ``"normal"``, ``"bold"``, ``"extra bold"`` (default),
        ``"black"`` or a number 0-1000.
    label_rotation : float
        Label orientation in degrees (0 = horizontal, default).
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
        cell_pts = _cell_corners(atoms.cell[:], R, pos_offset=center)

    # unified depth -> zorder for atoms AND cell segments, so the box composites
    # by depth (front edges over atoms, back edges behind them)
    zall = z if cell_pts is None else np.concatenate([z, cell_pts[:, 2]])
    zlo, zspan = zall.min(), (np.ptp(zall) + 1e-9)

    def zof(zv):
        return 20.0 + (zv - zlo) / zspan * 200.0

    if cell_pts is not None:
        ccolor = S["cell_color"] if cell_color is None else cell_color
        clw = S["cell_lw"] if cell_width is None else cell_width
        if not mcolors.is_color_like(ccolor):
            raise ValueError(f"cell_color {ccolor!r} is not a valid matplotlib colour")
        _draw_cell(cell_pts, ax, zof, color=ccolor, lw=clw)

    for i in np.argsort(z):          # back to front (insertion order breaks zorder ties)
        col = colors[i]
        if S["depth_desat"]:
            col = _desaturate(col, S["depth_desat"] * (1.0 - znorm[i]))
        base, pc = _sphere_patches(x[i], y[i], radii[i], col, dim[i],
                                   zof(z[i]), S, ts, ramp, white)
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

    if label:
        if label == "formula":
            label = atoms.get_chemical_formula()
        ax.text(0.5, -0.02, label, transform=ax.transAxes, ha="center", va="top",
                fontsize=label_size, fontweight=label_weight, rotation=label_rotation)
    return ax
