"""Save an :class:`ase.Atoms` straight to an image file. Format is inferred from the
extension: vector (``.pdf .svg .eps .ps``) or raster (``.png .jpg .jpeg .tif .tiff
.bmp .webp``). Raster formats other than PNG require Pillow.
"""
import os

import matplotlib.pyplot as plt

from .render import (render, DEFAULT_ROTATION, DEFAULT_RADIUS_SCALE,
                     DEFAULT_PALETTE, DEFAULT_STYLE_NAME)

VECTOR_EXTS = {".pdf", ".svg", ".eps", ".ps"}
RASTER_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
_NO_ALPHA = {".jpg", ".jpeg", ".bmp"}      # formats without transparency


def write(atoms, filename, *, rotation=DEFAULT_ROTATION, palette=DEFAULT_PALETTE,
          style=DEFAULT_STYLE_NAME, radius_scale=DEFAULT_RADIUS_SCALE, show_cell=True,
          reduce_cell=False, rings=None, cell_color=None, cell_width=None,
          figsize=4.0, dpi=200, transparent=True, background=None, title=None):
    """Render ``atoms`` and save to ``filename`` (format from the extension).

    Parameters
    ----------
    atoms : ase.Atoms
    filename : str
        Output path; extension selects the format (see module docstring).
    rotation, palette, style, radius_scale, show_cell, reduce_cell, rings, cell_color, cell_width
        Passed through to :func:`crystalvase.render` (``rings``: fewer gradient
        rings -> much smaller vector files; ``cell_color``/``cell_width``: unit-cell
        wireframe appearance, defaulting to the style's values).
    figsize : float or (w, h)
        Figure size in inches (a scalar means a square).
    dpi : int
        Resolution for raster formats (ignored for vector output).
    transparent : bool
        Transparent background where the format supports alpha. Ignored for
        JPEG/BMP (opaque; see ``background``).
    background : matplotlib colour, optional
        Fill the background with this colour instead of leaving it transparent.
        Forced to white for opaque formats if not given.
    title : str, optional
        Small title drawn above the figure.

    Returns
    -------
    str
        ``filename``.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in VECTOR_EXTS and ext not in RASTER_EXTS:
        raise ValueError(f"unsupported output extension {ext!r}; "
                         f"use one of {sorted(VECTOR_EXTS | RASTER_EXTS)}")
    if isinstance(figsize, (int, float)):
        figsize = (figsize, figsize)

    fig, ax = plt.subplots(figsize=figsize)
    try:
        render(atoms, ax, rotation=rotation, palette=palette, style=style,
               radius_scale=radius_scale, show_cell=show_cell, reduce_cell=reduce_cell,
               rings=rings, cell_color=cell_color, cell_width=cell_width)
        if title:
            ax.set_title(title, fontsize=9)

        save_kw = dict(bbox_inches="tight", dpi=dpi)
        if background is not None:
            fig.patch.set_facecolor(background)
            save_kw.update(facecolor=background, transparent=False)
        elif ext in _NO_ALPHA:
            save_kw.update(facecolor="white", transparent=False)
        else:
            save_kw.update(transparent=transparent)

        try:
            fig.savefig(filename, **save_kw)
        except (ValueError, RuntimeError, ImportError) as exc:
            if ext in RASTER_EXTS and ext != ".png":
                raise RuntimeError(
                    f"saving {ext} requires Pillow (pip install pillow) — {exc}") from exc
            raise
    finally:
        plt.close(fig)
    return filename
