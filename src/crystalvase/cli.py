"""Command-line interface: ``crystalvase INPUT OUTPUT [options]``.

Loads a structure with ASE (any format ASE can read) and saves a vector/raster
figure. With a multi-frame ``--index`` slice, writes one file per frame.
"""
import argparse
import os
import sys

from ase.io import read

from . import __version__
from .io import write, VECTOR_EXTS, RASTER_EXTS
from .palettes import PALETTES
from .styles import STYLES
from .render import (DEFAULT_ROTATION, DEFAULT_RADIUS_SCALE, DEFAULT_PALETTE,
                     DEFAULT_STYLE_NAME)


def _numbered(path, i):
    """Insert ``i`` into ``path``: honour a ``{i}`` field, else append before ext."""
    if "{i}" in path:
        return path.format(i=i)
    root, ext = os.path.splitext(path)
    return f"{root}_{i:03d}{ext}"


def build_parser():
    p = argparse.ArgumentParser(
        prog="crystalvase",
        description="Draw an ASE-readable structure as a vector/raster figure.")
    p.add_argument("input", nargs="?", help="structure file (any format ASE can read)")
    p.add_argument("output", nargs="?", help="output image; extension picks the format "
                   f"({', '.join(sorted(VECTOR_EXTS | RASTER_EXTS))})")
    p.add_argument("--index", default="0",
                   help="ASE frame index/slice, e.g. 0, -1, ':', '0:10' (default: 0). "
                        "A slice writes one file per frame.")
    p.add_argument("--rotation", default=DEFAULT_ROTATION,
                   help=f"view rotation, ASE syntax (default: {DEFAULT_ROTATION!r})")
    p.add_argument("--palette", default=DEFAULT_PALETTE,
                   help=f"palette name; see --list-palettes (default: {DEFAULT_PALETTE})")
    p.add_argument("--style", default=DEFAULT_STYLE_NAME,
                   help=f"shade style name; see --list-styles (default: {DEFAULT_STYLE_NAME})")
    p.add_argument("--radius-scale", default=DEFAULT_RADIUS_SCALE,
                   help="atom size: small | medium | large | xlarge, or a number "
                        f"(fraction of covalent radius; default: {DEFAULT_RADIUS_SCALE})")
    p.add_argument("--no-cell", action="store_true", help="do not draw the unit cell")
    p.add_argument("--cell-color", default=None,
                   help="unit-cell colour, e.g. black | lightgray | dimgray | '0.3' | "
                        "'#444' (default: from the style)")
    p.add_argument("--cell-width", type=float, default=None,
                   help="unit-cell line width (default: from the style)")
    p.add_argument("--reduce-cell", action="store_true",
                   help="Niggli-reduce the cell so oblique boxes aren't sheared")
    p.add_argument("--rings", type=int, default=None,
                   help="gradient rings per sphere (default 220; fewer -> smaller "
                        "vector files)")
    p.add_argument("--figsize", type=float, default=4.0,
                   help="square figure size in inches (default: 4)")
    p.add_argument("--dpi", type=int, default=200, help="raster resolution (default: 200)")
    p.add_argument("--background", default=None,
                   help="background colour (default: transparent where supported)")
    p.add_argument("--title", default=None,
                   help="title text above the figure; use 'formula' for the chemical formula")
    p.add_argument("--label", default=None,
                   help="label below the figure; use 'formula' for the chemical formula")
    p.add_argument("--label-size", type=float, default=13, help="label font size")
    p.add_argument("--label-weight", default="extra bold",
                   help="label boldness: normal | bold | 'extra bold' | black")
    p.add_argument("--label-rotation", type=float, default=0,
                   help="label orientation in degrees (0 = horizontal)")
    p.add_argument("--list-palettes", action="store_true", help="list palettes and exit")
    p.add_argument("--list-styles", action="store_true", help="list shade styles and exit")
    p.add_argument("--version", action="version", version=f"crystalvase {__version__}")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_palettes:
        print("palettes:", ", ".join(sorted(PALETTES)))
        return 0
    if args.list_styles:
        print("styles:", ", ".join(sorted(STYLES)))
        return 0

    if not args.input or not args.output:
        parser.error("the following arguments are required: input, output")

    frames = read(args.input, index=args.index)
    if not isinstance(frames, list):
        frames = [frames]

    multi = len(frames) > 1
    for n, atoms in enumerate(frames):
        out = _numbered(args.output, n) if multi else args.output
        title = atoms.get_chemical_formula() if args.title == "formula" else args.title
        write(atoms, out, rotation=args.rotation, palette=args.palette, style=args.style,
              radius_scale=args.radius_scale, show_cell=not args.no_cell,
              reduce_cell=args.reduce_cell, rings=args.rings, cell_color=args.cell_color,
              cell_width=args.cell_width, label=args.label, label_size=args.label_size,
              label_weight=args.label_weight, label_rotation=args.label_rotation,
              figsize=args.figsize, dpi=args.dpi, background=args.background, title=title)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
