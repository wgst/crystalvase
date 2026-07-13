"""Shade styles: how a sphere is lit and toned. Element colours come from the
palette; styles only change shading/tone (plus optional HSV ``sat``/``bright``).

Main styles, each with variants (pick with ``style="<name>"``):

- ``clean``     — bright matte spheres, no outline, black cell box: the classic
                  MD-snapshot look (e.g. water-box figures).
- ``cartoon``   — simple artistic 3D: flat "sticker" discs shaded only near the
                  edge, outlined. Variants: ``cartoon-dot`` (adds a gloss dot),
                  ``cartoon-soft`` (smooth matte pastel, colour-derived rim).
- ``realistic`` — studio-lit glossy spheres with deep shading (default).
                  Variants: ``realistic-warm``, ``realistic-cool``.
- ``ase``       — the classic flat ASE look (outlined discs), vector and
                  depth-dimmed. Variant: ``ase-shaded``.

All styles shade atoms by depth (position) so overlapping structure stays clear.
Build your own with :func:`make_style`, overriding keys of :data:`DEFAULT_STYLE`.
"""

# All knobs:
#   edge_dark    shadow-floor multiplier for the silhouette disk (limb darkness)
#   body0        diffuse body brightness at the shadow edge
#   body_gain    extra brightness added towards the lit side
#   body_end     where the diffuse ramp saturates (0..1 across the radius)
#   soft_amt     strength of the broad sheen
#   soft_start   where the broad sheen begins (0..1)
#   hot_amt      strength of the tight specular hotspot (gloss)
#   hot_start    where the hotspot begins (0..1; higher = tighter)
#   spec         specular colour (RGB 0-1); tints the light (warm/cool)
#   hx, hy       light direction: highlight offset as a fraction of the radius
#   depth_lo     brightness of the furthest-back atom (front atoms = 1.0)
#   depth_desat  extra desaturation of back atoms (0..1); atmospheric depth cue
#   sat, bright  HSV saturation / value multipliers applied to the base colour
#   shadow_tint  RGB multiplier at the shadow end — the hue shadows lean towards
#   shadow_hue   extra hue rotation of the shadow end, in degrees
#   posterize    None, or int N -> cel shading with N discrete bands
#   flat         True -> single flat disc (no gradient); the ASE look
#   outline      None, or multiplier -> rim colour = atom colour * outline
#   outline_color explicit RGB outline (e.g. black); overrides ``outline``
#   outline_lw   rim line width in points
#   cell_color   colour of the unit-cell wireframe
#   cell_lw      line width of the unit-cell wireframe
DEFAULT_STYLE = dict(
    edge_dark=0.70, body0=0.80, body_gain=0.34, body_end=0.80,
    soft_amt=0.40, soft_start=0.42, hot_amt=0.88, hot_start=0.88,
    spec=(1.0, 1.0, 1.0), hx=-0.28, hy=0.30, depth_lo=0.55, depth_desat=0.0,
    sat=1.0, bright=1.0, shadow_tint=(1.0, 1.0, 1.0), shadow_hue=0.0,
    posterize=None, flat=False, outline=None, outline_color=None, outline_lw=0.4,
    cell_color="0.55", cell_lw=0.6,
)


def make_style(**overrides):
    """Return a style dict = :data:`DEFAULT_STYLE` updated with ``overrides``."""
    unknown = set(overrides) - set(DEFAULT_STYLE)
    if unknown:
        raise ValueError(f"unknown style keys: {sorted(unknown)}")
    s = dict(DEFAULT_STYLE)
    s.update(overrides)
    return s


# family bases (numbers shared by the variants)
_STICKER = dict(                       # flat like ASE, but shaded near the edge -> 3D
    edge_dark=0.60, body0=0.68, body_gain=0.32, body_end=0.55,
    soft_amt=0.0, hot_amt=0.0, shadow_tint=(0.95, 0.94, 1.0),
    hx=-0.12, hy=0.14, depth_lo=0.55, depth_desat=0.25,
    outline_color=(0, 0, 0), outline_lw=1.0, sat=1.02, bright=1.04,
)
_REAL = dict(
    edge_dark=0.40, body0=0.54, body_gain=0.52, body_end=0.92,
    soft_amt=0.30, soft_start=0.30, hot_amt=0.95, hot_start=0.84,
    spec=(1.0, 0.98, 0.95), shadow_tint=(0.88, 0.90, 1.04),
    depth_lo=0.42, depth_desat=0.15, sat=1.02, hx=-0.30, hy=0.34,
)

STYLES = {
    # -- clean: bright matte spheres, no outline, black cell box (MD-snapshot look) --
    "clean":          make_style(edge_dark=0.74, body0=0.86, body_gain=0.16, body_end=0.70,
                                 soft_amt=0.15, soft_start=0.50, hot_amt=0.0,
                                 hx=-0.16, hy=0.24, depth_lo=0.72, depth_desat=0.10,
                                 sat=1.05, bright=1.02,
                                 cell_color=(0.0, 0.0, 0.0), cell_lw=1.1),
    # -- cartoon: flat "sticker" discs with an edge gradient (ASE-like but 3D) --
    "cartoon":        make_style(**_STICKER),                                # + black outline
    "cartoon-dot":    make_style(**{**_STICKER, "hot_amt": 0.85, "hot_start": 0.88,
                                    "hx": -0.20, "hy": 0.22}),               # + gloss dot
    "cartoon-soft":   make_style(edge_dark=0.72, body0=0.80, body_gain=0.28, body_end=0.90,
                                 soft_amt=0.16, soft_start=0.40, hot_amt=0.0,
                                 shadow_tint=(0.78, 0.75, 1.02), sat=0.88, bright=1.10,
                                 outline=0.50, outline_lw=0.7,
                                 depth_lo=0.55, depth_desat=0.40),           # smooth matte pastel
    # -- realistic: studio-lit glossy spheres --
    "realistic":      make_style(**_REAL),                                   # neutral studio light
    "realistic-warm": make_style(**{**_REAL, "spec": (1.0, 0.92, 0.78),      # warm key light
                                    "shadow_tint": (0.86, 0.88, 1.08),
                                    "sat": 1.06, "bright": 1.01}),
    "realistic-cool": make_style(**{**_REAL, "spec": (0.85, 0.93, 1.0),      # cool daylight
                                    "shadow_tint": (0.93, 0.93, 1.0),
                                    "bright": 0.99}),
    # -- ase: the classic flat ASE look, vector + depth-dimmed --
    "ase":            make_style(flat=True, body0=1.0, outline_color=(0, 0, 0),
                                 outline_lw=1.0, depth_lo=0.55),
    "ase-shaded":     make_style(edge_dark=0.80, body0=0.88, body_gain=0.16, body_end=0.85,
                                 soft_amt=0.12, soft_start=0.40, hot_amt=0.35, hot_start=0.92,
                                 outline_color=(0, 0, 0), outline_lw=0.8,
                                 depth_lo=0.50, depth_desat=0.15),
}


def get_style(style):
    """Resolve ``style`` (name in :data:`STYLES` or a style dict) to a dict."""
    if isinstance(style, str):
        try:
            return STYLES[style]
        except KeyError:
            raise ValueError(f"unknown style {style!r}; choose from {sorted(STYLES)}")
    if isinstance(style, dict):
        return make_style(**style)
    raise TypeError("style must be a name or a dict of overrides")
