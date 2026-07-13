"""Shade styles: how a sphere is lit and toned. Colours themselves come from the
palette and are unchanged (except optional HSV ``sat``/``bright`` tweaks).

A style is a plain dict; :data:`STYLES` holds 10 named presets. Build your own with
:func:`make_style` overriding any of the keys documented in :data:`DEFAULT_STYLE`.
"""

# All knobs, with the "01_glossy" default values:
#   edge_dark   shadow-floor multiplier for the silhouette disk
#   body0       diffuse body brightness at the shadow edge
#   body_gain   extra brightness added towards the lit side
#   body_end    where the diffuse ramp saturates (0..1 across the radius)
#   soft_amt    strength of the broad sheen
#   soft_start  where the broad sheen begins (0..1)
#   hot_amt     strength of the tight specular hotspot (gloss)
#   hot_start   where the hotspot begins (0..1; higher = tighter)
#   spec        specular colour (tuple, RGB 0-1); tint for warm/cool looks
#   hx, hy      light direction: highlight offset as a fraction of the radius
#   depth_lo    brightness of the furthest-back atom (front atoms = 1.0)
#   sat, bright HSV saturation / value multipliers applied to the base colour
#   outline     None, or a multiplier -> rim = base colour * outline (a soft edge)
#   outline_lw  rim line width in points
DEFAULT_STYLE = dict(
    edge_dark=0.70, body0=0.80, body_gain=0.34, body_end=0.80,
    soft_amt=0.40, soft_start=0.42, hot_amt=0.88, hot_start=0.88,
    spec=(1.0, 1.0, 1.0), hx=-0.28, hy=0.30, depth_lo=0.55,
    sat=1.0, bright=1.0, outline=None, outline_lw=0.4,
)


def make_style(**overrides):
    """Return a style dict = :data:`DEFAULT_STYLE` updated with ``overrides``."""
    unknown = set(overrides) - set(DEFAULT_STYLE)
    if unknown:
        raise ValueError(f"unknown style keys: {sorted(unknown)}")
    s = dict(DEFAULT_STYLE)
    s.update(overrides)
    return s


STYLES = {
    "01_glossy":        make_style(),
    "02_soft_rim":      make_style(outline=0.62, outline_lw=0.3),
    "03_matte":         make_style(edge_dark=0.82, body0=0.86, body_gain=0.18, body_end=0.9,
                                   soft_amt=0.22, soft_start=0.35, hot_amt=0.0),
    "04_high_contrast": make_style(edge_dark=0.50, body0=0.74, body_gain=0.40,
                                   hot_amt=0.95, hot_start=0.90, depth_lo=0.40),
    "05_vivid":         make_style(sat=1.40, bright=1.02, edge_dark=0.66),
    "06_pastel":        make_style(sat=0.52, bright=1.18, edge_dark=0.86,
                                   hot_amt=0.55, hot_start=0.90, soft_amt=0.30),
    "07_cel_flat":      make_style(body0=0.90, body_gain=0.12, body_end=0.6,
                                   soft_amt=0.08, soft_start=0.5, hot_amt=0.70,
                                   hot_start=0.90, edge_dark=0.75, outline=0.40, outline_lw=0.7),
    "08_metallic":      make_style(sat=0.85, bright=0.97, edge_dark=0.52,
                                   hot_amt=1.0, hot_start=0.80, soft_amt=0.35,
                                   spec=(0.90, 0.94, 1.0)),
    "09_warm":          make_style(sat=1.12, bright=1.03, spec=(1.0, 0.92, 0.80),
                                   edge_dark=0.68),
    "10_cool":          make_style(sat=1.06, spec=(0.84, 0.92, 1.0), edge_dark=0.66,
                                   hot_amt=0.90),
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
