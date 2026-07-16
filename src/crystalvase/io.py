"""Save an :class:`ase.Atoms` straight to an image file, or lay several out in a
grid. Format is inferred from the extension: vector (``.pdf .svg .eps .ps``) or
raster (``.png .jpg .jpeg .tif .tiff .bmp .webp``). Raster formats other than PNG
require Pillow.
"""
import os

import numpy as np
import matplotlib.pyplot as plt

from .render import render

VECTOR_EXTS = {".pdf", ".svg", ".eps", ".ps"}
RASTER_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
_NO_ALPHA = {".jpg", ".jpeg", ".bmp"}      # formats without transparency


def _savefig(fig, path, dpi=200, transparent=True, background=None):
    """Save ``fig`` to ``path`` (format from the extension), handling transparency,
    opaque-format backgrounds, and a friendly error if Pillow is missing."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in VECTOR_EXTS and ext not in RASTER_EXTS:
        raise ValueError(f"unsupported output extension {ext!r}; "
                         f"use one of {sorted(VECTOR_EXTS | RASTER_EXTS)}")
    save_kw = dict(bbox_inches="tight", dpi=dpi)
    if background is not None:
        fig.patch.set_facecolor(background)
        save_kw.update(facecolor=background, transparent=False)
    elif ext in _NO_ALPHA:
        save_kw.update(facecolor="white", transparent=False)
    else:
        save_kw.update(transparent=transparent)
    try:
        fig.savefig(path, **save_kw)
    except (ValueError, RuntimeError, ImportError) as exc:
        if ext in RASTER_EXTS and ext != ".png":
            raise RuntimeError(
                f"saving {ext} requires Pillow (pip install pillow) — {exc}") from exc
        raise
    return path


def write(atoms, filename, *, figsize=4.0, dpi=200, transparent=True,
          background=None, title=None, **render_kwargs):
    """Render ``atoms`` and save to ``filename`` (format from the extension).

    Parameters
    ----------
    atoms : ase.Atoms
    filename : str
        Output path; extension selects the format (see module docstring).
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
    **render_kwargs
        Everything else is forwarded to :func:`crystalvase.render` — e.g.
        ``rotation``, ``palette``, ``style``, ``radius_scale``, ``show_cell``,
        ``reduce_cell``, ``cell_color``, ``bonds``, ``supercell``, ``show_images``,
        ``polyhedra``, ``label``, …

    Returns
    -------
    str
        ``filename``.
    """
    if isinstance(figsize, (int, float)):
        figsize = (figsize, figsize)

    fig, ax = plt.subplots(figsize=figsize)
    try:
        render(atoms, ax, **render_kwargs)
        if title:
            ax.set_title(title, fontsize=9)
        _savefig(fig, filename, dpi=dpi, transparent=transparent, background=background)
    finally:
        plt.close(fig)
    return filename


def grid(entries, *, ncols=3, panel=3.6, suptitle=None, save=None, dpi=200,
         transparent=True, background=None, **common):
    """Render several structures into one figure of panels.

    Parameters
    ----------
    entries : list
        Each item is an :class:`ase.Atoms`, or a ``(atoms, kwargs)`` tuple whose
        kwargs override the shared options for that panel.
    ncols : int
        Number of columns; rows are filled left-to-right, top-to-bottom.
    panel : float
        Size of each panel in inches.
    suptitle : str, optional
        Figure-level title.
    save : str or list of str, optional
        Output path(s); the format of each is taken from its extension. The same
        figure can be saved to several (e.g. ``["fig.png", "fig.pdf"]``).
    dpi, transparent, background
        Saving options (see :func:`write`).
    **common
        Any :func:`crystalvase.render` options applied to every panel (e.g.
        ``style=``, ``palette=``, ``label="formula"``).

    Returns
    -------
    (fig, axes)
        The matplotlib Figure and 2-D array of Axes.
    """
    entries = list(entries)
    n = len(entries)
    nrows = max(1, -(-n // ncols))          # ceil division
    fig, axes = plt.subplots(nrows, ncols, figsize=(panel * ncols, panel * nrows),
                             squeeze=False)
    flat = list(axes.flat)
    for ax, entry in zip(flat, entries):
        atoms, kw = entry if isinstance(entry, tuple) else (entry, {})
        render(atoms, ax, **{**common, **kw})
    for ax in flat[n:]:
        ax.set_axis_off()
    if suptitle:
        fig.suptitle(suptitle, fontsize=14)
    if save is not None:
        for path in ([save] if isinstance(save, str) else save):
            _savefig(fig, path, dpi=dpi, transparent=transparent, background=background)
    return fig, axes
