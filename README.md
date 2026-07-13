# crystalvase

Tool for generating true **vector** figures of [ASE](https://wiki.fysik.dtu.dk/ase/) structures with
matplotlib — no POV-Ray.

![styles](docs/preview.png)

## Install

```bash
pip install -e .              # core; add [vesta] for the VESTA palette, [raster] for JPG/TIFF
```

## Use

```python
from ase.io import read
import crystalvase as cv

atoms = read("POSCAR")
cv.write(atoms, "struct.pdf")                                 # default near-face-on view
cv.write(atoms, "struct.jpg", rotation="45x,10y,0z", style="cartoon", dpi=300)
cv.render(atoms, ax)                                          # or draw onto your own Axes
```

```bash
crystalvase POSCAR out.pdf
crystalvase traj.xyz out.png --index ::10 --style cartoon     # slice -> one file per frame
```

Format is taken from the extension. Main options (API kwargs = CLI flags): `rotation`
(ASE `"<a>x,<b>y,<c>z"` syntax), `palette`, `style`, `radius_scale`, `show_cell`,
`reduce_cell`, plus `figsize`/`dpi`/`background` for saving.

## Palettes & styles

- **Palettes:** `jmol` (ASE default), `vesta`, `vmd`; tone variants of the ASE colours
  (`pastel`, `muted`, `vivid`, `deep`); and shade schemes that keep every element in its
  colour family but shift the shade — `coral`, `cherry`, `sea`, `spring`, `dusk`, `ink`,
  `candy`, `autumn`, `ice`, `neon`. Roll your own with
  `cv.adjust("jmol", sat=..., bright=..., mix_white=..., hue=...)`.
- **Styles** (shading only), all depth-shaded so structure stays clear:
  `clean` — bright matte spheres, no outline, black cell box (MD-snapshot look);
  `cartoon` — flat "sticker" discs shaded at the edges, outlined (`cartoon-dot` adds a
  gloss dot, `cartoon-soft` is smooth matte pastel);
  `realistic` — studio-lit gloss, the default (`realistic-warm`, `realistic-cool`);
  `ase` — classic flat ASE look, outlined + depth-dimmed (`ase-shaded`).
  Custom: `cv.make_style(edge_dark=0.6, hot_amt=1.0, ...)` — see `styles.py`.

`crystalvase --list-palettes` / `--list-styles` print the choices; `examples/` compares
them. Run the tests with `pytest`. MIT licensed.
