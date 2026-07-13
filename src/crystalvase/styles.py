"""Shade styles: how a sphere is lit and toned. Element colours come from the
palette; styles only change shading/tone (plus optional HSV ``sat``/``bright``).

Three families, each with variants (pick with ``style="<name>"``):

- ``cartoon``   — simple artistic 3D: cel-shaded bands, tinted shadows, no gloss.
                  Variants: ``cartoon-warm``, ``cartoon-shift``, ``cartoon-soft``.
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
DEFAULT_STYLE = dict(
    edge_dark=0.70, body0=0.80, body_gain=0.34, body_end=0.80,
    soft_amt=0.40, soft_start=0.42, hot_amt=0.88, hot_start=0.88,
    spec=(1.0, 1.0, 1.0), hx=-0.28, hy=0.30, depth_lo=0.55, depth_desat=0.0,
    sat=1.0, bright=1.0, shadow_tint=(1.0, 1.0, 1.0), shadow_hue=0.0,
    posterize=None, flat=False, outline=None, outline_color=None, outline_lw=0.4,
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
_TOON = dict(
    posterize=3, edge_dark=0.55, body0=0.70, body_gain=0.40, body_end=0.95,
    soft_amt=0.0, hot_amt=0.45, hot_start=0.90, spec=(1.0, 0.97, 0.86),
    depth_lo=0.55, depth_desat=0.45, outline=0.35, outline_lw=1.1,
    sat=1.08, bright=1.06, hx=-0.26, hy=0.28,
)
_REAL = dict(
    edge_dark=0.40, body0=0.54, body_gain=0.52, body_end=0.92,
    soft_amt=0.30, soft_start=0.30, hot_amt=0.95, hot_start=0.84,
    spec=(1.0, 0.98, 0.95), shadow_tint=(0.88, 0.90, 1.04),
    depth_lo=0.42, depth_desat=0.15, sat=1.02, hx=-0.30, hy=0.34,
)

STYLES = {
    # -- cartoon: simple artistic 3D, cel bands, tinted shadows, no high gloss --
    "cartoon":        make_style(**_TOON, shadow_tint=(0.62, 0.58, 1.04)),   # violet shadows
    "cartoon-warm":   make_style(**{**_TOON, "spec": (1.0, 0.99, 0.92)},
                                 shadow_tint=(1.06, 0.66, 0.45)),            # amber shadows
    "cartoon-shift":  make_style(**_TOON, shadow_hue=45.0,
                                 shadow_tint=(0.74, 0.72, 0.94)),            # hue-rotated shadows
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
