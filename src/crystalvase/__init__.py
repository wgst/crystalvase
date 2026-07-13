"""crystalvase — fully-vector, publication-style 3D-looking figures of ASE structures.

Load a structure with ASE, then draw or save it::

    from ase.io import read
    import crystalvase as cv

    atoms = read("POSCAR")
    cv.write(atoms, "struct.pdf")                       # vector, default view
    cv.write(atoms, "struct.jpg", rotation="45x,10y,0z", style="cartoon")

    ax = cv.render(atoms)                                # draw onto a matplotlib Axes

Atoms are drawn as lit spheres (an offset radial gradient made of nested filled
circles), so vector output (PDF/SVG) stays crisp at any zoom. See :func:`render`
and :func:`write` for options; :data:`PALETTES` and :data:`STYLES` list the choices.
"""
__version__ = "0.1.0"

from .render import (render, DEFAULT_ROTATION, DEFAULT_RADIUS_SCALE,
                     RADIUS_SCALES, NR)
from .io import write, VECTOR_EXTS, RASTER_EXTS
from .palettes import (PALETTES, adjust, retone, get_palette, jmol_colors,
                       vesta_colors, vmd_colors)
from .styles import STYLES, DEFAULT_STYLE, make_style, get_style

#: Alias — :func:`render` draws onto an Axes, mirroring ``ase.visualize.plot.plot_atoms``.
plot = render

__all__ = [
    "render", "plot", "write",
    "PALETTES", "adjust", "retone", "get_palette", "jmol_colors", "vesta_colors",
    "vmd_colors",
    "STYLES", "DEFAULT_STYLE", "make_style", "get_style",
    "DEFAULT_ROTATION", "DEFAULT_RADIUS_SCALE", "RADIUS_SCALES", "NR",
    "VECTOR_EXTS", "RASTER_EXTS", "__version__",
]
