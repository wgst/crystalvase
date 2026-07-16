"""Core renderer: draw an :class:`ase.Atoms` onto a matplotlib Axes as lit,
fully-vector spheres (an offset radial gradient built from nested filled circles),
with an optional unit-cell wireframe. Crisp at any zoom; no rasterised atoms.
"""
import re
from itertools import product, combinations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Circle, Polygon
from matplotlib.collections import PatchCollection, PolyCollection
from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox
from ase.data import covalent_radii, atomic_numbers
from ase.formula import Formula
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


def _pick_label_font():
    """Prefer a clean Helvetica-like face over matplotlib's default DejaVu Sans."""
    from matplotlib import font_manager as fm
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Helvetica", "Arial", "Liberation Sans", "TeX Gyre Heros",
                 "Nimbus Sans", "DejaVu Sans"):
        if name in have:
            return name
    return "sans-serif"


#: Font used for the optional label (a clean sans available on this system).
DEFAULT_LABEL_FONT = _pick_label_font()

_BOLD_WEIGHTS = {"semibold", "demibold", "demi", "bold", "heavy", "extra bold", "black"}


def _is_bold(weight):
    if isinstance(weight, (int, float)):
        return weight >= 600
    return str(weight).lower() in _BOLD_WEIGHTS


def _formula_tokens(s):
    """Split a formula into runs of digits vs non-digits, e.g. Na2O24 -> Na,2,O,24."""
    return re.findall(r"[0-9]+|[^0-9]+", s)


def _add_formula_label(ax, formula, x, y, size, weight, font):
    """Formula label with the counts as true subscripts, in ``font`` (composed
    from separate glyph runs so it works in any font, unlike Unicode subscripts)."""
    kids = [TextArea(tok, textprops=dict(fontsize=size * (0.62 if tok.isdigit() else 1.0),
                                         fontweight=weight, fontfamily=font))
            for tok in _formula_tokens(formula)]
    box = HPacker(children=kids, align="bottom", pad=0, sep=0)
    ax.add_artist(AnnotationBbox(box, (x, y), xycoords="axes fraction",
                                 box_alignment=(0.5, 1.0), frameon=False))


def _mathtext_formula(formula, weight):
    """Formula as a mathtext string with subscripts (used for rotated labels)."""
    cmd = "mathbf" if _is_bold(weight) else "mathrm"
    body = "".join("_{%s}" % t if t.isdigit() else t for t in _formula_tokens(formula))
    return r"$\%s{%s}$" % (cmd, body)


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
        return base, None, None

    # shadow-end colour may lean towards a hue (tint and/or rotation)
    shadow = _hue_shift(color, S["shadow_hue"]) * np.asarray(S["shadow_tint"])
    dark = shadow * S["body0"]
    lit = color * (S["body0"] + S["body_gain"])
    spec = np.asarray(S["spec"])
    rim_col = spec if S["rim_color"] is None else np.asarray(S["rim_color"])
    fx, fy = cx + S["hx"] * r, cy + S["hy"] * r

    base = Circle((cx, cy), r, facecolor=np.clip(shadow * S["edge_dark"] * dim, 0, 1),
                  edgecolor=ec, linewidth=S["outline_lw"], antialiased=True, zorder=z0)

    # fresnel rim: the outer rings (large t) lift towards the environment/rim colour,
    # so the limb catches light instead of just going dark -> a lit, 3-D edge
    fres = _smoothstep(ts, S["rim_start"], 0.985) * S["rim_amt"] if S["rim_amt"] else None

    circles, facecolors = [], []
    for k, (t, ramp_k, white_k) in enumerate(zip(ts, ramp, white)):
        body = dark + (lit - dark) * ramp_k
        rgb = body * (1 - white_k) + spec * white_k
        if fres is not None:
            f = fres[k]
            rgb = rgb * (1 - f) + rim_col * f
        rgb = np.clip(rgb, 0, 1) * dim
        circles.append(Circle((cx * t + fx * (1 - t), cy * t + fy * (1 - t)), r * t))
        facecolors.append(rgb)
    pc = PatchCollection(circles, match_original=False)
    pc.set_facecolor(facecolors)
    pc.set_edgecolor("none")
    # smooth gradients: AA off so ring edges leave no seams; cel bands: AA on for
    # clean band boundaries (adjacent same-colour rings blend invisibly anyway)
    pc.set_antialiased(bool(S["posterize"]))
    pc.set_zorder(z0)

    # secondary "bounce" light: a soft glow away from the key light, built by stacking
    # many faint circles into a smooth radial falloff (kept as its own AA collection so
    # the opaque body rings stay seam-free). A colour-preserving fill, not a white dot.
    fill = None
    if S["fill_amt"] > 0:
        fx2, fy2 = cx + S["fill_hx"] * r, cy + S["fill_hy"] * r
        fc = (np.clip(color * 0.55 + 0.5, 0, 1) if S["fill_color"] is None
              else np.asarray(S["fill_color"])) * dim
        nf = 16
        a = 1.0 - (1.0 - min(S["fill_amt"], 0.95)) ** (1.0 / nf)   # per-layer alpha
        fcs, fcols = [], []
        for m in range(nf):
            rr = r * (0.46 * (1.0 - m / (nf - 1)) + 0.05)          # big -> small
            fcs.append(Circle((fx2, fy2), rr))
            fcols.append([fc[0], fc[1], fc[2], a])
        fill = PatchCollection(fcs, match_original=False)
        fill.set_facecolor(fcols)
        fill.set_edgecolor("none")
        fill.set_antialiased(True)
        fill.set_zorder(z0)
    return base, pc, fill


def _env_rgb(nx, ny, nz, color, S, dim, bond_ao=()):
    """The env (hyperrealistic) shading pipeline for arbitrary surface normals:
    deep-contrast diffuse + ONE shaped softbox highlight + sky band + floor
    crescent + fresnel rim, with per-bond joint occlusion. Both the sphere patches
    AND the bond-junction colours evaluate THIS function, so a rod's end and the
    ball it meets can never disagree. Returns rgb with shape ``nx.shape + (3,)``."""
    color = np.asarray(color, float)
    shadow = _hue_shift(color, S["shadow_hue"]) * np.asarray(S["shadow_tint"])
    dark = shadow * S["body0"]
    lit = color * (S["body0"] + S["body_gain"])
    spec = np.asarray(S["spec"])
    rim_col = spec if S["rim_color"] is None else np.asarray(S["rim_color"])
    L = np.array([S["hx"] * 1.9, S["hy"] * 1.9, 0.62])       # well off-axis: offset highlight
    L = L / np.linalg.norm(L)
    H = L + np.array([0.0, 0.0, 1.0]); H = H / np.linalg.norm(H)
    up = np.array([0.0, 1.0, 0.0])                           # highlight tangent frame
    A = np.cross(H, up); A = A / (np.linalg.norm(A) + 1e-9)  # ~horizontal axis
    B = np.cross(A, H); B = B / (np.linalg.norm(B) + 1e-9)   # ~vertical axis

    ndl = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    diff = S["env_amb"] + (1.0 - S["env_amb"]) * ndl ** S["env_contrast"]  # deeper shadow
    # ONE shaped key highlight (a soft softbox), no nested glint. Footprint is a
    # superellipse in the highlight's tangent frame: env_soft_round 2 = oval, higher
    # = a rounded rectangle; env_soft_w / _h set its size and aspect (streak if w<<h).
    ndh_s = nx * H[0] + ny * H[1] + nz * H[2]                 # signed: front lobe only
    ta = (nx * A[0] + ny * A[1] + nz * A[2]) / S["env_soft_w"]
    tb = (nx * B[0] + ny * B[1] + nz * B[2]) / S["env_soft_h"]
    q = np.abs(ta) ** S["env_soft_round"] + np.abs(tb) ** S["env_soft_round"]
    softbox = (1.0 - _smoothstep(q, 0.10, 1.0)) * np.clip(ndh_s * 3.0, 0, 1) * S["soft_amt"]
    fres = np.clip(1.0 - nz, 0, 1) ** 3
    grz = 0.18 + 0.82 * fres                                  # reflections peak at the rim
    sky = np.exp(-((ny - 0.62) / 0.20) ** 2) * grz * S["env_sky"]      # upper sky band
    floor = np.exp(-((ny + 0.72) / 0.15) ** 2) * grz * S["env_floor"]  # lower floor crescent
    glow = np.clip(softbox + sky + floor, 0, 1)[..., None]
    rim = (fres * S["rim_amt"])[..., None]

    # joint occlusion, two scales with WIDE graded falloff (darkest at the joint,
    # easing out -- no bright arcs hugging a rod). Light: an attached rod blocks
    # the environment, so glow and fresnel rim die near the joint at full strength
    # regardless of ball size. Body: a milder contact shadow, scaled down on small
    # balls (H) so they never go wholesale dark.
    occ_l = np.zeros_like(nx)
    occ_b = np.zeros_like(nx)
    for u, sint in bond_ao:
        d = nx * u[0] + ny * u[1] + nz * u[2]
        ang = np.arcsin(min(sint, 0.999))
        w_l = _smoothstep(d, np.cos(min(ang + 0.40, 1.50)), 1.0)
        occ_l = occ_l + (1.0 - occ_l) * w_l
        w_b = _smoothstep(d, np.cos(min(ang + 0.28, 1.50)), 1.0) * (1.0 - 0.55 * sint)
        occ_b = occ_b + (1.0 - occ_b) * w_b
    glow = glow * (1.0 - 0.92 * occ_l[..., None])
    rim = rim * (1.0 - 0.92 * occ_l[..., None])

    body = dark + (lit - dark) * diff[..., None]
    rgb = body * (1 - glow) + spec * glow
    rgb = rgb * (1 - rim) + rim_col * rim
    rgb = rgb * (1.0 - 0.35 * occ_b)[..., None]
    return np.clip(rgb, 0, 1) * dim


def _sphere_env_patches(cx, cy, r, color, dim, z0, S, nrho, nphi, bond_ao=()):
    """A sphere shaded per surface-normal (not per ring), for the hyperrealistic
    styles: the :func:`_env_rgb` studio environment evaluated on a polar grid over
    the visible hemisphere. Tessellated into filled polygons -> still fully vector."""
    color = np.asarray(color, float)
    ec = _outline_color(S, color, dim)
    shadow = _hue_shift(color, S["shadow_hue"]) * np.asarray(S["shadow_tint"])

    # Polar grid over the visible hemisphere; rho = screen radius (even bands). The
    # angular step is matched to ARC LENGTH -- an inner band spans a shorter circle,
    # so it needs proportionally fewer segments for the same resolution. A uniform
    # grid spends as many patches on the tiny centre band as on the rim; this halves
    # the patch count (and the vector file) at identical fidelity.
    rho_e = np.linspace(0.0, 1.0, nrho + 1)
    rho_c = 0.5 * (rho_e[:-1] + rho_e[1:])
    quads, NX, NY = [], [], []
    for i in range(nrho):
        m = max(8, int(round(nphi * rho_c[i])))
        pe = np.linspace(0.0, 2 * np.pi, m + 1)
        c0, s0, c1, s1 = np.cos(pe[:-1]), np.sin(pe[:-1]), np.cos(pe[1:]), np.sin(pe[1:])
        r0, r1 = r * rho_e[i], r * rho_e[i + 1]
        quads.append(np.stack([np.c_[cx + r0 * c0, cy + r0 * s0],
                               np.c_[cx + r1 * c0, cy + r1 * s0],
                               np.c_[cx + r1 * c1, cy + r1 * s1],
                               np.c_[cx + r0 * c1, cy + r0 * s1]], axis=1))
        pc_ = 0.5 * (pe[:-1] + pe[1:])
        NX.append(rho_c[i] * np.cos(pc_))
        NY.append(rho_c[i] * np.sin(pc_))
    polys = np.concatenate(quads, axis=0)
    nx, ny = np.concatenate(NX), np.concatenate(NY)
    nz = np.sqrt(np.clip(1.0 - nx * nx - ny * ny, 0, 1))

    rgb = _env_rgb(nx, ny, nz, color, S, dim, bond_ao)

    base = Circle((cx, cy), r, facecolor=np.clip(shadow * S["edge_dark"] * dim, 0, 1),
                  edgecolor=ec, linewidth=S["outline_lw"], antialiased=True, zorder=z0)
    pc = PolyCollection(polys, closed=True)
    pc.set_facecolor(rgb)
    pc.set_edgecolor(rgb)                                    # edge=face hides seams
    pc.set_linewidth(0.3)
    pc.set_antialiased(True)
    pc.set_zorder(z0)
    return base, pc, None


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


def _as_tuple3(v):
    if isinstance(v, (int, np.integer)):
        return (int(v), int(v), int(v))
    t = tuple(int(x) for x in v)
    if len(t) != 3:
        raise ValueError("supercell must be an int or a 3-tuple (nx, ny, nz)")
    return t


def _add_boundary_images(atoms, tol=0.02):
    """Add periodic images of atoms lying on/near a cell face, so boundary atoms
    appear on every shared face/edge/corner (VESTA-style cell completion)."""
    from ase import Atoms
    frac = atoms.get_scaled_positions(wrap=True)
    numbers = atoms.numbers
    fr, nu = [], []
    for s in product((-1, 0, 1), repeat=3):
        g = frac + np.array(s)
        m = np.all((g >= -tol) & (g <= 1 + tol), axis=1)
        fr.append(g[m])
        nu.append(numbers[m])
    F = np.vstack(fr)
    N = np.concatenate(nu)
    _, idx = np.unique(np.round(F, 4), axis=0, return_index=True)   # dedupe
    idx = np.sort(idx)
    return Atoms(numbers=N[idx], scaled_positions=F[idx], cell=atoms.cell[:],
                 pbc=atoms.pbc)


def _expand(atoms, supercell, show_images):
    """Optional supercell replication and/or periodic-image (boundary) completion."""
    a = atoms
    if supercell:
        a = a.repeat(_as_tuple3(supercell))
    if show_images and a.cell.rank == 3:
        a = _add_boundary_images(a)
    return a


def _pair_bonds(pos3d, numbers, scale):
    """Bonds between atoms whose separation < (r_i + r_j) * scale (covalent radii).
    Pairwise on the drawn atoms (no PBC) so bonds never dangle; combine with
    ``supercell``/``show_images`` to complete bonding across cell boundaries."""
    n = len(pos3d)
    if n < 2:
        return np.empty((0, 2), int)
    r = covalent_radii[numbers] * scale
    d = pos3d[:, None, :] - pos3d[None, :, :]
    dist = np.sqrt((d * d).sum(-1))
    cutoff = r[:, None] + r[None, :]
    mask = np.triu((dist < cutoff) & (dist > 1e-3), 1)
    ii, jj = np.where(mask)
    return np.column_stack([ii, jj])


#: light direction in screen space (x right, y up, z towards viewer) for the
#: flat-shaded faces of bonds and polyhedra.
_LIGHT = np.array([-0.3, 0.4, 0.86])
_LIGHT = _LIGHT / np.linalg.norm(_LIGHT)


def _hull_faces(V, tol=1e-3):
    """Triangular faces of the 3-D convex hull of vertices ``V`` (small point sets:
    tetrahedra, octahedra, …). Each face is (i, j, k) with an outward normal."""
    faces = []
    for a, b, c in combinations(range(len(V)), 3):
        normal = np.cross(V[b] - V[a], V[c] - V[a])
        nn = np.linalg.norm(normal)
        if nn < 1e-9:
            continue
        normal = normal / nn
        d = (V - V[a]) @ normal                     # signed distance of every vertex
        if d.max() > tol and d.min() < -tol:
            continue                                # not a hull face (points both sides)
        if d.max() > tol:                           # body lies on +normal side, so
            normal = -normal                        # flip to point outward (away from it)
        faces.append(((a, b, c), normal))
    return faces


#: a bond is drawn as longitudinal strips across its width; each strip is shaded
#: as a cylinder surface so the highlight follows the light (not the bond direction).
_BOND_NSTRIP = 21
_BOND_EDGES = np.linspace(-1.0, 1.0, _BOND_NSTRIP + 1)
_BOND_S = 0.5 * (_BOND_EDGES[:-1] + _BOND_EDGES[1:])       # strip centres in [-1, 1]
_BOND_NZ = np.sqrt(np.clip(1 - _BOND_S ** 2, 0, 1))        # normal z (towards viewer)


def _facet_color(color, u, S, dim):
    """Shade a facet / cylinder-strip at illumination ``u`` in [0, 1] with the SAME
    recipe as the spheres, so bonds and polyhedra match the atom style (glossy for
    ``realistic``, matte for cartoon, banded for cel, flat for ``ase``). ``u`` may be
    a scalar or array; returns an ``(len(u), 3)`` array."""
    color = np.asarray(color, float)
    u = np.atleast_1d(np.asarray(u, float))
    if S["flat"]:
        return np.tile(np.clip(color * S["body0"], 0, 1), (len(u), 1)) * dim
    if S["posterize"]:
        nlev = max(int(S["posterize"]), 2)
        u = np.clip(np.floor(u * nlev) / (nlev - 1), 0, 1)
    ramp = _smoothstep(u, 0.0, S["body_end"])[:, None]
    white = np.clip(_smoothstep(u, S["soft_start"], 1.0) * S["soft_amt"]
                    + _smoothstep(u, S["hot_start"], 1.0) * S["hot_amt"], 0, 0.97)[:, None]
    dark = color * np.asarray(S["shadow_tint"]) * S["edge_dark"]
    lit = color * (S["body0"] + S["body_gain"])
    body = dark[None, :] + (lit - dark)[None, :] * ramp
    rgb = body * (1 - white) + np.asarray(S["spec"])[None, :] * white
    return np.clip(rgb, 0, 1) * dim


def _bond_strip_colors(color, perp_hat, S, dim):
    """Per-strip RGB for a bond, shaded with the SAME model as the spheres: each
    strip across the tube's width is lit by an *offset* Lambert cross-section (the
    bright zone sits toward the light, the rim goes dark) and gets the style's soft/
    hot specular via :func:`_curves`. So a bond matches its atoms in every style —
    glossy for realistic, matte for cartoon, flat for ase — with no fake centre line."""
    color = np.asarray(color, float)
    if S["flat"]:
        return np.tile(np.clip(color * S["body0"], 0, 1), (_BOND_NSTRIP, 1)) * dim
    hl = float(perp_hat @ _LIGHT[:2])                    # light component across the width
    u = np.clip(hl * _BOND_S + _LIGHT[2] * _BOND_NZ, 0.0, 1.0)   # offset-lit cross-section
    if S["posterize"]:
        n = max(int(S["posterize"]), 2)
        u = np.clip(np.floor(u * n) / (n - 1), 0, 1)
    ramp, white = _curves(S, u)
    white = white * 0.85                                 # a touch softer than the balls
    shadow = _hue_shift(color, S["shadow_hue"]) * np.asarray(S["shadow_tint"])
    dark = shadow * S["body0"]
    lit = color * (S["body0"] + S["body_gain"])
    body = dark[None, :] + (lit - dark)[None, :] * ramp[:, None]
    rgb = body * (1 - white[:, None]) + np.asarray(S["spec"])[None, :] * white[:, None]
    return np.clip(rgb, 0, 1) * dim


def _bond_env_strip_colors(color, perp_hat, S, dim):
    """Per-strip RGB for a bond under the env (hyperrealistic) styles: the cylinder
    cross-section normals get the SAME studio lighting as the spheres — deep-contrast
    diffuse, ONE soft key-light stripe (the softbox reflected in a rod is a stripe
    along it, offset towards the light), sky/floor bands and a fresnel rim — so rods
    and balls read as the same material under the same light.

    Returns ``(full, contact)``: the lit strip colours, and the same strips at a
    CONTACT — glow and rim suppressed and the body shadowed exactly as the ball
    suppresses its own lighting at a joint — so where rod meets ball both surfaces
    respond to the contact identically and their shades match."""
    color = np.asarray(color, float)
    # cross-section normals (bond treated as screen-parallel): n = s*p + nz*z
    n = np.stack([_BOND_S * perp_hat[0], _BOND_S * perp_hat[1], _BOND_NZ], axis=1)
    L = np.array([S["hx"] * 1.9, S["hy"] * 1.9, 0.62]); L = L / np.linalg.norm(L)
    H = L + np.array([0.0, 0.0, 1.0]); H = H / np.linalg.norm(H)

    shadow = _hue_shift(color, S["shadow_hue"]) * np.asarray(S["shadow_tint"])
    dark = shadow * S["body0"]
    lit = color * (S["body0"] + S["body_gain"])
    spec = np.asarray(S["spec"])
    rim_col = spec if S["rim_color"] is None else np.asarray(S["rim_color"])

    # normalised shading: a cylinder's normals never point straight at the light, so
    # raw Lambert/Blinn would leave every rod dimmer and flatter than the balls. Use
    # the rod's own dark->bright range at full swing (with a small physical residual)
    # so rods carry the same deep-contrast light play as the spheres.
    ndl = np.clip(n @ L, 0, 1)
    ndl_max = max(float(ndl.max()), 1e-6)
    shade = (ndl / ndl_max) ** S["env_contrast"] * (0.82 + 0.18 * ndl_max)
    diff = 0.8 * S["env_amb"] + (1.0 - 0.8 * S["env_amb"]) * shade
    # key stripe: brightest where the cross-normal points at H; sized like the
    # ball's softbox patch (wide + soft) so rods read just as glossy
    hp, hz = float(H @ np.array([perp_hat[0], perp_hat[1], 0.0])), float(H[2])
    s_pk = hp / max(np.hypot(hp, hz), 1e-9)              # strip where n·H peaks
    w = max(S["env_soft_w"], 0.12) * 1.4
    q = np.abs((_BOND_S - s_pk) / w) ** S["env_soft_round"]
    ndh = n @ H
    gate = np.clip(ndh / max(float(ndh.max()), 1e-6), 0, 1) ** 1.2
    stripe = (1.0 - _smoothstep(q, 0.10, 1.0)) * gate * S["soft_amt"]
    ny, nz = n[:, 1], n[:, 2]
    fres = np.clip(1.0 - nz, 0, 1) ** 3
    grz = 0.18 + 0.82 * fres
    sky = np.exp(-((ny - 0.62) / 0.20) ** 2) * grz * 0.60 * S["env_sky"]
    floor = np.exp(-((ny + 0.72) / 0.15) ** 2) * grz * 0.65 * S["env_floor"]
    glow = np.clip(stripe + sky + floor, 0, 1)[:, None]
    rim = (fres * 0.45 * S["rim_amt"])[:, None]          # edges must keep a dark side

    body = dark[None, :] + (lit - dark)[None, :] * diff[:, None]
    rgb = body * (1 - glow) + spec[None, :] * glow
    rgb = rgb * (1 - rim) + rim_col[None, :] * rim
    full = np.clip(rgb, 0, 1) * dim
    # at a contact: glow and rim die (0.92, like the ball's occ_l) and the body
    # shadows by the ball's own contact depth -- computed per ball in the caller
    contact = body * (1 - 0.08 * glow) + spec[None, :] * (0.08 * glow)
    contact = contact * (1 - 0.08 * rim) + rim_col[None, :] * (0.08 * rim)
    contact = np.clip(contact, 0, 1) * dim
    return full, contact


def _bite_corners(tri3, rs, nseg=9):
    """3-D triangle ``tri3`` (n, 3) with every corner cut back to its atom's SPHERE
    surface; returns the projected (x, y) polygon.

    Along an in-plane direction ``v`` (3-D unit) out of corner A, the face leaves
    the ball at 3-D distance r, which projects to ``A_xy + r*v_xy`` — a distance of
    only ``r*|v_xy|``. So where the face tilts towards the viewer the cut lands
    *inside* the ball's disk and the plane correctly overlaps the ball a little (it
    is in front of the surface there); where the face is screen-parallel the cut
    falls on the silhouette. Done as geometry rather than a matplotlib clip path --
    a clip masks a fill but leaks strokes and slivers through its holes -- and it is
    local, so a face merely passing in front of another atom still paints over it."""
    tri3 = np.asarray(tri3, float)
    n = len(tri3)
    out = []
    for i in range(n):
        A, B, C = tri3[i], tri3[(i + 1) % n], tri3[(i - 1) % n]
        dB, dC = B - A, C - A
        lB, lC = float(np.linalg.norm(dB)), float(np.linalg.norm(dC))
        if lB < 1e-9 or lC < 1e-9:
            return None
        r = min(rs[i], 0.45 * lB, 0.45 * lC)          # keep bites from meeting
        vB, vC = dB / lB, dC / lC                     # both lie in the face's plane
        pts = []
        for s in np.linspace(0.0, 1.0, nseg):         # sweep the interior angle:
            v = vC * (1.0 - s) + vB * s               # any blend stays in the plane
            ln = float(np.linalg.norm(v))
            if ln < 1e-9:
                continue
            pts.append(A[:2] + r * (v / ln)[:2])
        if len(pts) < 2:
            return None
        out.append(np.array(pts))
    return np.vstack(out)


def _coordination(pos3d, numbers, center_znums, scale):
    """For each atom whose element is in ``center_znums``, the indices of its
    coordinating neighbours: within (r_center + r_nb) * scale AND belonging to the
    nearest shell (<= 1.25x the closest neighbour distance) — so e.g. a perovskite
    B site keeps its six O and never sweeps in the A-site cations behind them.
    Yields (center_index, [nb_idx])."""
    r = covalent_radii[numbers] * scale
    out = []
    for c in np.where(np.isin(numbers, list(center_znums)))[0]:
        d = pos3d - pos3d[c]
        dist = np.sqrt((d * d).sum(-1))
        nb = np.where((dist < r[c] + r) & (dist > 1e-3))[0]
        if len(nb) >= 3:
            nb = nb[dist[nb] <= 1.25 * dist[nb].min()]   # nearest shell only
        if len(nb) >= 3:
            out.append((c, nb))
    return out


def render(atoms, ax=None, *, rotation=DEFAULT_ROTATION, palette=DEFAULT_PALETTE,
           style=DEFAULT_STYLE_NAME, radius_scale=DEFAULT_RADIUS_SCALE,
           atom_radii=None,
           show_cell=True, reduce_cell=False, rings=None,
           cell_color=None, cell_width=None,
           supercell=None, show_images=False,
           bonds=False, bond_scale=1.2, bond_radius=0.15, bond_color=None,
           polyhedra=None, polyhedra_color=None, polyhedra_alpha=0.6,
           polyhedra_scale=1.2,
           label=None, label_size=13, label_weight="extra bold", label_rotation=0,
           label_font=None):
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
    atom_radii : dict, optional
        Per-element radius overrides in Angstrom, e.g. ``{"Sr": 1.15, "O": 0.3}``
        (other elements keep ``radius_scale``). Classic use: big cations + small
        anions so coordination polyhedra stay readable.
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
    supercell : int or (nx, ny, nz), optional
        Replicate a periodic cell this many times along each axis before drawing.
    show_images : bool
        Complete the cell with periodic images of boundary atoms (VESTA-style),
        so atoms shared across faces/edges/corners appear on all of them.
    bonds : bool
        Draw bonds between atoms closer than ``(r_i + r_j) * bond_scale`` (covalent
        radii), split at the midpoint and coloured by the two atoms. Bonds connect
        only atoms that are actually drawn, so for crystals combine with
        ``supercell`` / ``show_images`` to complete bonding across cell boundaries.
    bond_scale : float
        Covalent-radius multiplier for the bond cutoff (default 1.2).
    bond_radius : float
        Bond half-thickness in Angstrom (default 0.15).
    bond_color : matplotlib colour, optional
        Single colour for all bonds. Default (``None``): the style's ``bond_tone``
        if set (the hyperrealistic styles use a neutral silver rod material, like
        studio renders of model kits), otherwise each half takes its atom's colour.
    polyhedra : str or list of str, optional
        Element symbol(s) whose atoms get VESTA-style filled coordination polyhedra
        (e.g. ``"Si"`` or ``["Si", "Ti"]``); the centre atom is hidden inside.
    polyhedra_color : matplotlib colour, optional
        Polyhedron fill colour; default (``None``) uses the centre element's colour.
    polyhedra_alpha : float
        Polyhedron opacity: partly transparent by default (0.6) so the centre atom
        and the structure behind stay visible; 1.0 gives a solid hull that hides its
        centre. Faces are cut at their vertex atoms either way.
    polyhedra_scale : float
        Covalent-radius multiplier for finding the coordinating vertices (default 1.2).
    label : str, optional
        Text drawn below the figure (e.g. a chemical formula), with any counts as
        subscripts. Pass ``"formula"`` for the drawn structure's full formula
        (``H54O27``), or ``"reduced"`` for the empirical one (``H2O``) — handy for
        supercells and boxes of molecules. Boundary images (``show_images``) are
        duplicates and never counted. No label if ``None``.
    label_size : float
        Label font size (default 13).
    label_weight : matplotlib font weight
        Label boldness — ``"normal"``, ``"bold"``, ``"extra bold"`` (default),
        ``"black"`` or a number 0-1000.
    label_rotation : float
        Label orientation in degrees (0 = horizontal, default).
    label_font : str, optional
        Label font family (default: a clean sans available on the system, see
        :data:`DEFAULT_LABEL_FONT`).
    """
    palette = get_palette(palette)
    S = get_style(style)
    radius_scale = _resolve_radius_scale(radius_scale)
    if reduce_cell:
        atoms = _maybe_reduce(atoms)
    # a supercell genuinely multiplies the contents, but boundary images are just
    # duplicates completing the view -- so take the formula before adding them
    atoms = _expand(atoms, supercell, False)
    label_formula = atoms.get_chemical_formula()
    atoms = _expand(atoms, None, show_images)
    if ax is None:
        _, ax = plt.subplots(figsize=(4, 4))

    ts = _ring_ts(int(rings) if rings else NR)
    ramp, white = _curves(S, 1.0 - ts)
    nring = int(rings) if rings else NR                     # env-shader patch resolution
    nphi, nrho = int(np.clip(nring, 72, 168)), int(np.clip(nring // 3, 30, 72))
    R = rotate(rotation)
    pos3d = atoms.positions                          # unrotated, for bond/polyhedra cutoffs
    pos = pos3d @ R
    center = pos.mean(0)
    pos = pos - center
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]

    numbers = atoms.numbers
    radii = covalent_radii[numbers] * radius_scale
    if atom_radii:                                   # per-element overrides (Angstrom),
        for sym, rv in atom_radii.items():           # e.g. small O so polyhedra read
            radii = np.where(numbers == atomic_numbers[sym], float(rv), radii)
    colors = _tone(palette[numbers].copy(), S)

    # depth cue: back atoms dimmer (and optionally desaturated) so structure is clear
    if len(z) > 1:
        znorm = (z - z.min()) / (np.ptp(z) + 1e-9)
    else:
        znorm = np.ones_like(z)
    dim = S["depth_lo"] + (1.0 - S["depth_lo"]) * znorm

    # per-atom displayed colour (with depth desaturation) — shared by spheres and bonds
    disp = colors
    if S["depth_desat"]:
        hsv = mcolors.rgb_to_hsv(np.clip(colors, 0, 1))
        hsv[:, 1] *= 1.0 - np.clip(S["depth_desat"] * (1.0 - znorm), 0, 1)
        disp = mcolors.hsv_to_rgb(hsv)

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

    # coordination polyhedra: the front (viewer-facing) hull faces, studio-shaded.
    # Opaque -> the hull hides its centre atom; translucent -> centre shows through.
    poly_centers = set()
    poly_shade = {}                  # atom -> dim factor for atoms inside a hull
    if polyhedra is not None:
        syms = [polyhedra] if isinstance(polyhedra, str) else list(polyhedra)
        znums = {atomic_numbers[s] for s in syms}
        translucent = polyhedra_alpha < 0.99
        for c, nb in _coordination(pos3d, numbers, znums, polyhedra_scale):
            V = pos[nb]                                  # rotated vertices (x, y, z=depth)
            raw = disp[c] if polyhedra_color is None else np.asarray(mcolors.to_rgb(polyhedra_color))

            def facet_rgb(normal):
                if S["env"]:
                    # the studio environment shades each facet at its normal -- same
                    # lights as the balls, with a lifted diffuse floor and gentler
                    # contrast: flat crystal faces catch bounced light, and adjacent
                    # faces must stay recognisably the same colour
                    Sf = {**S, "env_amb": max(S["env_amb"], 0.30), "env_contrast": 1.15}
                    return _env_rgb(np.array([normal[0]]), np.array([normal[1]]),
                                    np.array([normal[2]]), raw, Sf, dim[c])[0]
                u = max(0.0, float(normal @ _LIGHT))     # how much the face meets the light
                fcol = _facet_color(raw, u, S, dim[c])[0]
                if not S["flat"]:                        # extra gloss on light-facing faces
                    g = u ** 6 * min(S["soft_amt"] + S["hot_amt"], 1.0) * 0.5
                    fcol = np.clip(fcol * (1 - g) + np.asarray(S["spec"]) * g, 0, 1)
                return fcol

            faces = _hull_faces(V)
            # draw only a COMPLETE coordination shell: the neighbours must span a
            # volume and the centre must sit well inside every hull face. This skips
            # boundary/partial coordination (flat or one-sided fans, e.g. surface
            # atoms of a supercell) that would otherwise make meaningless polyhedra.
            # Use supercell/show_images to complete more shells at the boundary.
            if len(faces) < 4 or np.linalg.matrix_rank(V - V.mean(0), tol=1e-3) < 3:
                continue
            rmean = float(np.linalg.norm(V - pos[c], axis=1).mean())
            if any((pos[c] - V[fa[0]]) @ n > -0.15 * rmean for fa, n in faces):
                continue                                # centre not enclosed -> skip
            front = [(f, n) for f, n in faces if n[2] > 0.0]
            if not front:
                continue
            # A convex hull's FRONT faces tile its silhouette exactly, with no
            # overlap -- so drawing just them, each at the full alpha with its own
            # shading, gives one uniform layer (no phantom internal boundaries from
            # stacking back faces). Each face sits at ITS OWN depth, so faces and
            # their edges composite against every atom by depth: an edge in front of
            # a ball paints over it, one behind it does not.
            for f, n in front:                           # face fills, cut at the atoms
                poly = _bite_corners(V[list(f)], [radii[nb[k]] for k in f])
                if poly is None:
                    continue
                ax.add_patch(Polygon(poly, closed=True, facecolor=facet_rgb(n),
                                     edgecolor="none", alpha=polyhedra_alpha,
                                     antialiased=True,
                                     zorder=zof(float(V[list(f), 2].mean()))))
            # Hull edges: EVERY edge of the hull, so each vertex keeps its full set of
            # bonds (an edge belongs to two faces, so taking only front faces would
            # drop the rear vertex's edges entirely and leave others short). Rear
            # edges sit at their own low depth: through a translucent hull they show
            # tinted, and an opaque one hides them.
            # Each is drawn once and trimmed at the SPHERE surfaces (3-D, as in
            # _bite_corners): an edge leaving a vertex towards the viewer exits its
            # ball at projected r*|u_xy| -- inside the disk -- and is genuinely in
            # front of the ball beyond that, so its own depth carries it OVER the
            # ball; one heading away stays behind, and its ball paints over it.
            ecol = (S["outline_color"] if (S["flat"] and S["outline_color"] is not None)
                    else np.clip(raw * 0.45 * dim[c], 0, 1))
            drawn = set()
            for f, n in faces:                           # ALL faces, not just front:
                for p, q in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
                    key = (min(p, q), max(p, q))
                    if key in drawn:
                        continue
                    drawn.add(key)
                    A, B = V[key[0]], V[key[1]]
                    d3 = B - A
                    L3 = float(np.linalg.norm(d3))
                    rA, rB = radii[nb[key[0]]], radii[nb[key[1]]]
                    if L3 < 1e-9 or L3 <= rA + rB:
                        continue                         # balls meet: no edge to show
                    u3 = d3 / L3
                    P0, P1 = A[:2] + rA * u3[:2], B[:2] - rB * u3[:2]
                    ax.plot([P0[0], P1[0]], [P0[1], P1[1]], color=ecol, linewidth=0.55,
                            alpha=min(1.0, polyhedra_alpha + 0.25), solid_capstyle="butt",
                            antialiased=True, zorder=zof(0.5 * float(A[2] + B[2])))
            if translucent:
                poly_shade[int(c)] = 0.62                # in shadow inside the cage
            else:
                poly_centers.add(int(c))                 # opaque hull hides its centre

    # bonds: tubes anchored in TRUE 3-D. Each half is cut into short segments along
    # its length; a segment's depth comes from its 3-D position, tested against the
    # SPHERE SURFACES (not centres): inside a ball's disk it hides behind the ball
    # while beneath its surface, but a bond tilted towards the viewer rises above
    # that surface and correctly emerges across the ball's face -- so out-of-plane
    # bonds (e.g. a -CH3 hydrogen pointing at the camera) actually read as such.
    pairs = _pair_bonds(pos3d, numbers, bond_scale) if bonds else []
    bond_ao = {}                       # atom -> [(3D unit dir to its bonds, sin(rod angle))]
    for i, j in pairs:
        u = pos[j] - pos[i]
        un = float(np.linalg.norm(u))
        if un < 1e-9:
            continue
        u = u / un
        bp = min(bond_radius, 0.75 * min(radii[i], radii[j]))
        bond_ao.setdefault(int(i), []).append((u, min(0.92, 1.12 * bp / radii[i])))
        bond_ao.setdefault(int(j), []).append((-u, min(0.92, 1.12 * bp / radii[j])))
    if bonds:
        for i, j in pairs:
            P0, P1 = pos[i], pos[j]
            mid3 = 0.5 * (P0 + P1)
            # a stick must stay thinner than the balls it plugs into, or its flat cap
            # pokes out past the smaller sphere and the joint looks broken
            br = min(bond_radius, 0.75 * min(radii[i], radii[j]))
            for A3, B3, a, ball_at in ((P0, mid3, i, 0), (mid3, P1, j, 1)):
                d3 = B3 - A3
                L3 = float(np.linalg.norm(d3))
                v = d3[:2]
                L = float(np.hypot(*v))
                if L < 1e-9 or L3 < 1e-9:
                    continue                             # points straight at the viewer
                vhat = v / L
                perp_hat = np.array([-v[1], v[0]]) / L
                perp = perp_hat * br
                az = float(d3[2] / L3)                   # towards-viewer tilt of this half
                if bond_color is not None:
                    raw = np.asarray(mcolors.to_rgb(bond_color))
                elif S["bond_tone"] is not None:         # single neutral rod material
                    raw = np.asarray(S["bond_tone"], float)   # (the model-kit look)
                else:
                    raw = disp[a]                        # VESTA-like: per-atom halves
                if S["flat"]:                            # single flat rod (ase look)
                    fc = np.clip(np.asarray(raw) * S["body0"] * dim[a], 0, 1)
                    ax.add_patch(Polygon([A3[:2] - perp, A3[:2] + perp,
                                          B3[:2] + perp, B3[:2] - perp],
                                         closed=True, facecolor=fc, edgecolor="none",
                                         antialiased=True, zorder=zof(z[a]) - 1.0))
                    continue
                # where a rod crosses its ball's FACE the junction is visible: trim the
                # rod at the exact surface point and round that end with the projected
                # junction ellipse + a soft contact shadow, so it reads as socketed
                # into the sphere. Two visible cases: this half's ball sits at its
                # START and the rod tilts towards the viewer (emerges across the face),
                # or the ball sits at its END and the rod tilts away (plunges into it).
                # trim only when the junction lands clearly ON the face: the trimmed
                # end (rod half-width br) must stay inside the ball's silhouette, i.e.
                # |az| > br/r -- otherwise the end corners poke past the ball's edge
                # and leave background wedges. Glancing bonds keep the run-to-centre
                # path (hidden by the surface test), which cannot gap.
                cap0 = cap1 = 0.0
                tE = radii[a] / L3
                thr = max(0.05, min(0.9, 1.15 * br / radii[a]))
                if ball_at == 0 and az > thr:            # exits its ball towards us
                    if tE >= 1.0:
                        continue                         # never clears its own ball
                    A3 = A3 + tE * d3
                    cap0 = az
                elif ball_at == 1 and az < -thr:         # dives into its ball's face
                    if tE >= 1.0:
                        continue
                    B3 = B3 - tE * d3
                    cap1 = -az
                rim = np.clip(_hue_shift(raw, S["shadow_hue"]) * np.asarray(S["shadow_tint"])
                              * S["edge_dark"] * dim[a], 0, 1)
                if S["env"]:                             # same studio light as the balls
                    strip_full, strip_ct = _bond_env_strip_colors(raw, perp_hat, S, dim[a])
                    # longitudinal light play: the rod end facing the key light sits a
                    # little brighter, fading towards the far end (t_glob 0..1 spans the
                    # WHOLE bond so the two colour-halves shade continuously)
                    lxy = np.array([S["hx"], S["hy"]])
                    lxy = lxy / max(np.linalg.norm(lxy), 1e-9)
                    lgrad = 0.16 * float(vhat @ lxy)
                    # the ball's contact response, mirrored on the rod: near the joint
                    # the rod's glow/rim die like the ball's (in strip_ct) and its body
                    # shadows by the SAME depth the ball uses -- both surfaces react to
                    # the contact identically, so their shades match at the junction
                    sint_a = min(0.92, 1.12 * br / radii[a])
                    ct_body = 0.35 * (1.0 - 0.55 * sint_a)
                    # a finite softbox reflects on a rod as a bright WINDOW of finite
                    # length (not an endless uniform stripe): the glow peaks where the
                    # box's mirror direction lands -- towards the light end -- and
                    # relaxes to the matte body elsewhere. This light play along the
                    # length is what makes a rod read as glossy like the balls.
                    t_pk = 0.5 + 0.33 * float(vhat @ lxy)
                else:
                    strip_full = _bond_strip_colors(raw, perp_hat, S, dim[a])
                    strip_ct = None
                    lgrad = 0.0
                pin = perp_hat * br * 0.92
                L = float(np.hypot(*(B3 - A3)[:2]))
                if L < 1e-9:
                    continue
                nseg = max(3, min(26, int(np.ceil(L / 0.05))))
                tseg = np.linspace(0.0, 1.0, nseg + 1)
                pts = A3[None, :] + tseg[:, None] * (B3 - A3)[None, :]   # (nseg+1, 3)
                for k in range(nseg):
                    q0, q1 = pts[k], pts[k + 1]
                    pm = 0.5 * (q0 + q1)
                    zo = zof(pm[2])
                    for b in (i, j):                     # behind a ball only while the
                        rho = float(np.hypot(pm[0] - x[b], pm[1] - y[b]))
                        if rho < radii[b]:               # rod is beneath its surface
                            surf = z[b] + np.sqrt(radii[b] ** 2 - rho ** 2)
                            if pm[2] < surf:
                                zo = min(zo, zof(z[b]) - 1.0)
                    # tiny lengthwise overlap so transverse seams never show
                    ov = (q1 - q0)[:2] * 0.08
                    a0 = q0[:2] - (ov if k > 0 else 0.0)
                    a1 = q1[:2] + (ov if k < nseg - 1 else 0.0)
                    tg = 0.5 * ball_at + 0.25 * (tseg[k] + tseg[k + 1])  # 0..1 whole bond
                    lfac = 1.0 + lgrad * (1.0 - 2.0 * tg)
                    # contact response, mirrored from the ball: over the last ~rod-width
                    # (3-D distance from the sphere SURFACE, so foreshortened stubs keep
                    # their own shading along their length) the rod's glow/rim die and
                    # its body shadows by the ball's own contact depth
                    jd = float(np.linalg.norm(pm - pos[a])) - radii[a]
                    wf = float(np.clip(1.0 - jd / (1.5 * br), 0, 1))
                    wf = wf * wf * (3.0 - 2.0 * wf)                # smooth onset
                    if strip_ct is not None:
                        win = 0.55 + 0.45 * float(np.exp(-((tg - t_pk) / 0.50) ** 2))
                        base = strip_ct + (strip_full - strip_ct) * win
                        seg_cols = (base * (1 - wf) + strip_ct * wf) * lfac
                        # depth falls off CONTINUOUSLY along the rod (interpolating the
                        # two atoms' depth dims), like the balls it spans between
                        df = (dim[i] + (dim[j] - dim[i]) * tg) / max(dim[a], 1e-6)
                        seg_cols = np.clip(seg_cols * (1.0 - ct_body * wf) * df, 0, 1)
                        rim_k = np.clip(rim * (1.0 - ct_body * wf) * df, 0, 1)
                    else:
                        cf = 1.0 - 0.26 * wf                       # non-env: simple dip
                        seg_cols = np.clip(strip_full * lfac * cf, 0, 1)
                        rim_k = rim * cf
                    # smooth AA silhouette (same dark rim as the spheres), then AA-off
                    # shaded strips inset within it; a junction end bulges into the
                    # ball by the projected ellipse: e(s) = br*cap*sqrt(1-s^2)
                    r0 = cap0 if k == 0 else 0.0
                    r1 = cap1 if k == nseg - 1 else 0.0
                    if r0 > 0 or r1 > 0:
                        u = np.linspace(1.0, -1.0, 9)
                        head = ([a0 + uu * perp - br * r0 * np.sqrt(1 - uu * uu) * vhat
                                 for uu in u] if r0 > 0 else [a0 + perp, a0 - perp])
                        tail = ([a1 - uu * perp + br * r1 * np.sqrt(1 - uu * uu) * vhat
                                 for uu in u] if r1 > 0 else [a1 - perp, a1 + perp])
                        ax.add_patch(Polygon(tail + head, closed=True, facecolor=rim_k,
                                             edgecolor="none", antialiased=True, zorder=zo))
                    else:
                        ax.add_patch(Polygon([a0 - perp, a0 + perp, a1 + perp, a1 - perp],
                                             closed=True, facecolor=rim_k, edgecolor="none",
                                             antialiased=True, zorder=zo))
                    for m in range(_BOND_NSTRIP):
                        s0, s1 = _BOND_EDGES[m], _BOND_EDGES[m + 1]
                        b0, b1 = a0 + s0 * pin, a0 + s1 * pin
                        c1, c0 = a1 + s1 * pin, a1 + s0 * pin
                        if r0 > 0:
                            b0 = b0 - 0.92 * br * r0 * np.sqrt(1 - s0 * s0) * vhat
                            b1 = b1 - 0.92 * br * r0 * np.sqrt(1 - s1 * s1) * vhat
                        if r1 > 0:
                            c1 = c1 + 0.92 * br * r1 * np.sqrt(1 - s1 * s1) * vhat
                            c0 = c0 + 0.92 * br * r1 * np.sqrt(1 - s0 * s0) * vhat
                        ax.add_patch(Polygon(np.array([b0, b1, c1, c0]), closed=True,
                                             facecolor=seg_cols[m], edgecolor="none",
                                             antialiased=False, zorder=zo))

    for i in np.argsort(z):          # back to front (insertion order breaks zorder ties)
        if int(i) in poly_centers:                   # hidden inside its polyhedron
            continue
        # an atom walled in by its coordination polyhedron sits in shadow: little
        # light reaches inside the cage, so it reads as enclosed rather than pasted
        dimv = dim[i] * poly_shade.get(int(i), 1.0)
        zo_i = zof(z[i])
        if S["env"] and not S["flat"]:
            base, pc, fill = _sphere_env_patches(x[i], y[i], radii[i], disp[i], dimv,
                                                 zo_i, S, nrho, nphi,
                                                 bond_ao.get(int(i), ()))
        else:
            base, pc, fill = _sphere_patches(x[i], y[i], radii[i], disp[i], dimv,
                                             zo_i, S, ts, ramp, white)
        ax.add_patch(base)
        if pc is not None:
            ax.add_collection(pc)
        if fill is not None:
            ax.add_collection(fill)

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
        font = label_font or DEFAULT_LABEL_FONT
        if label in ("formula", "reduced"):
            formula = label_formula
            if label == "reduced":
                # the empirical formula, in the order a chemist writes it: "metal"
                # puts metals first (SrTiO3, not Hill's O3SrTi)
                formula = Formula(formula).reduce()[0].format("metal")
            if label_rotation == 0:                      # composed subscripts, any font
                _add_formula_label(ax, formula, 0.5, -0.02, label_size,
                                   label_weight, font)
            else:                                        # rotated: mathtext subscripts
                ax.text(0.5, -0.02, _mathtext_formula(formula, label_weight),
                        transform=ax.transAxes, ha="center", va="top",
                        fontsize=label_size, rotation=label_rotation)
        else:
            ax.text(0.5, -0.02, label, transform=ax.transAxes, ha="center", va="top",
                    fontsize=label_size, fontweight=label_weight,
                    rotation=label_rotation, fontfamily=font)
    return ax
