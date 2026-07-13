# crystalvase

Vector, 3D-looking figures of [ASE](https://wiki.fysik.dtu.dk/ase/) structures with
matplotlib — no POV-Ray. Atoms are drawn as lit spheres that stay crisp at any zoom,
so **PDF/SVG output is true vector** (also PNG/JPG/TIFF).

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
cv.write(atoms, "struct.jpg", rotation="45x,10y,0z", style="05_vivid", dpi=300)
cv.render(atoms, ax)                                          # or draw onto your own Axes
```

```bash
crystalvase POSCAR out.pdf
crystalvase traj.xyz out.png --index ::10 --style 05_vivid    # slice -> one file per frame
```

Format is taken from the extension. Main options (API kwargs = CLI flags): `rotation`
(ASE `"<a>x,<b>y,<c>z"` syntax), `palette`, `style`, `radius_scale`, `show_cell`,
`reduce_cell`, plus `figsize`/`dpi`/`background` for saving.

## Palettes & styles

- **Palettes:** `jmol` (ASE default), `vesta`, `vmd`. Same colours across every style.
- **Styles** (shading only): `01_glossy` `02_soft_rim` `03_matte` `04_high_contrast`
  `05_vivid` `06_pastel` `07_cel_flat` `08_metallic` `09_warm` `10_cool`.
  Custom: `cv.make_style(edge_dark=0.6, hot_amt=1.0, ...)` — see `styles.py`.

`crystalvase --list-palettes` / `--list-styles` print the choices; `examples/` compares
them. Run the tests with `pytest`. MIT licensed.
