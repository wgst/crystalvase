# crystalvase

Fully-vector, publication-style **3D-looking** figures of [ASE](https://wiki.fysik.dtu.dk/ase/)
structures — using only matplotlib (no POV-Ray, no rasterised atoms).

Load a structure with ASE, then save it to **PDF / SVG** (vector) or **PNG / JPG / TIFF**
(raster) at any viewing angle. Atoms are drawn as lit spheres built from nested filled
circles (an offset radial gradient), so vector output stays crisp at any zoom.

![styles](docs/preview.png)

## Install

```bash
pip install -e .                 # core (ase, numpy, matplotlib)
pip install -e ".[vesta]"        # + VESTA colour palette (pymatgen)
pip install -e ".[raster]"       # + JPEG/TIFF/WebP output (pillow)
pip install -e ".[dev]"          # + everything, for tests
```

## Python API

```python
from ase.io import read
import crystalvase as cv

atoms = read("POSCAR")

# save straight to a file (format inferred from the extension)
cv.write(atoms, "struct.pdf")                                  # vector, default view
cv.write(atoms, "struct.jpg", rotation="45x,10y,0z", dpi=300)  # raster, custom angle
cv.write(atoms, "struct.svg", palette="vmd", style="05_vivid")

# or draw onto your own matplotlib Axes
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
cv.render(atoms, ax, style="04_high_contrast")
```

### `write(atoms, filename, ...)` / `render(atoms, ax=None, ...)`

| argument | default | meaning |
|---|---|---|
| `rotation` | `"-6x,-5y,0z"` | view angle, ASE [`rotate`](https://wiki.fysik.dtu.dk/ase/ase/utils.html) syntax (`"<a>x,<b>y,<c>z"`) |
| `palette` | `"jmol"` | `jmol` (ASE default), `vesta`, `vmd`, or an `(n, 3)` RGB array |
| `style` | `"01_glossy"` | shade style name (see below) or an overrides dict |
| `radius_scale` | `0.65` | atom size as a fraction of the covalent radius |
| `show_cell` | `True` | draw the unit-cell wireframe (periodic systems) |
| `reduce_cell` | `False` | Niggli-reduce first so oblique cells aren't drawn sheared |

`write` also takes `figsize` (inches), `dpi` (raster), `transparent`, `background`, `title`.

The **default rotation is the near-face-on view** the figures were tuned with; pass any
`rotation` string to change it.

## Command line

```bash
crystalvase POSCAR struct.pdf                        # default view
crystalvase traj.xyz out.png --index -1 --style 05_vivid --dpi 300
crystalvase big.extxyz frame.pdf --index ::10        # slice -> frame_000.pdf, frame_001.pdf, ...
crystalvase POSCAR s.jpg --rotation "45x,10y,0z" --palette vmd --background white
crystalvase --list-styles
crystalvase --list-palettes
```

Formats: vector `.pdf .svg .eps .ps`; raster `.png .jpg .jpeg .tif .tiff .bmp .webp`
(non-PNG raster needs Pillow).

## Colour palettes

- **`jmol`** — ASE's native element colours (`ase.data.colors.jmol_colors`). Default.
- **`vesta`** — VESTA scheme (needs `pymatgen`; falls back to Jmol if absent).
- **`vmd`** — curated VMD-style (cyan carbon, saturated colours); exact for common
  elements, approximate for some transition metals.

Element colours are identical across styles — swap `style` to change only the shading.

## Shade styles

`01_glossy` (default), `02_soft_rim`, `03_matte`, `04_high_contrast`, `05_vivid`,
`06_pastel`, `07_cel_flat`, `08_metallic`, `09_warm`, `10_cool`.

Roll your own:

```python
from crystalvase import make_style
mine = make_style(edge_dark=0.6, hot_amt=1.0, spec=(1.0, 0.9, 0.8))
cv.write(atoms, "warm.pdf", style=mine)
```

See `DEFAULT_STYLE` in [`styles.py`](src/crystalvase/styles.py) for every knob.

## Examples

- [`examples/batch_extxyz.py`](examples/batch_extxyz.py) — batch a trajectory to PDFs.
- [`examples/compare_palettes.py`](examples/compare_palettes.py) — palettes side by side.
- [`examples/compare_styles.py`](examples/compare_styles.py) — all 10 styles in a grid.

## Tests

```bash
pytest
```

## Roadmap / not yet implemented

Bonds, periodic-image replication, per-atom labels, atom selection / slabs, and an
orthographic-vs-perspective toggle are natural next features.

## License

MIT.
