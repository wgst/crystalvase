<p align="center">
  <img src="https://raw.githubusercontent.com/wgst/crystalvase/main/docs/logo.png" width="200" alt="crystalvase logo">
</p>

# crystalvase

Tool for generating true **vector** figures of [ASE](https://wiki.fysik.dtu.dk/ase/) structures with
matplotlib, ideal for high-quality journal publications and conference presentations.

<img src="https://raw.githubusercontent.com/wgst/crystalvase/main/docs/preview.png" width="520" alt="crystalvase preview">

*(true vector — zoom in as far as you like: [docs/vector-sample.pdf](https://github.com/wgst/crystalvase/blob/main/docs/vector-sample.pdf), 360 atoms, ~0.1 MB)*

## Install

```bash
pip install crystalvase
```

Or from a clone, for development:

```bash
pip install -e .              # deps: ase, numpy, matplotlib, pillow
```

## Use

```python
from ase.io import read
import crystalvase as cv

atoms = read("POSCAR")
cv.write(atoms, "struct.pdf")                                 # defaults (below)
cv.write(atoms, "struct.jpg", rotation="45x,10y,0z", style="cartoon", dpi=300)
cv.write(atoms, "labelled.pdf", label="formula")             # formula below the figure
cv.render(atoms, ax)                                          # or draw onto your own Axes

# several structures in one figure (per-panel overrides), saved to png + pdf
cv.grid([(a1, dict(style="clean")), (a2, dict(palette="emerald"))],
        ncols=2, label="formula", save=["fig.png", "fig.pdf"])
```

```bash
crystalvase POSCAR out.pdf
crystalvase traj.xyz out.png --index ::10 --style cartoon     # slice -> one file per frame
```

Defaults: palette `blossom`, style `realistic`, size `large`, near-face-on view.
Format is taken from the extension. Main options (API kwargs = CLI flags): `rotation`
(ASE `"<a>x,<b>y,<c>z"` syntax), `palette`, `style`, `radius_scale` (`"small"` /
`"medium"` / `"large"` / `"xlarge"` or a number), `atom_radii` (per-element radii in Å,
e.g. `{"Sr": 1.1, "O": 0.3}` — big cations + small anions keep polyhedra readable),
`show_cell`, `reduce_cell`, `rings`
(gradient rings per sphere, default 220 — fewer gives much smaller vector files, e.g.
`rings=40` for many-panel figures), `cell_color` / `cell_width` (unit-cell wireframe —
any matplotlib colour: `black`, `lightgray`, `dimgray`, `"0.3"`, `#444`, …), `label`
(text below the figure — `label="formula"` for the chemical formula — with
`label_size` / `label_weight` / `label_rotation`; default extra-bold), plus
`figsize`/`dpi`/`background` for saving.

## Bonds, supercells & polyhedra

![features](https://raw.githubusercontent.com/wgst/crystalvase/main/docs/features.png)

```python
cv.write(mol,  "ballstick.pdf", bonds=True)                  # bonds from covalent-radius cutoffs
cv.write(xtal, "cell.pdf",  supercell=(2, 2, 2))             # replicate a periodic cell
cv.write(xtal, "poly.pdf",  polyhedra=["Si", "Ti"])          # VESTA-style coordination polyhedra
cv.write(xtal, "full.pdf",  show_images=True, bonds=True)    # complete boundary atoms, then bond them
```

Bonds connect only atoms that are drawn, so for crystals combine `bonds=True` with
`supercell` or `show_images` to complete bonding across cell faces. Polyhedra are drawn
only where the coordination shell is **complete** (the centre must be enclosed), so
`show_images=True` is worth adding for crystals — boundary atoms otherwise have partial
shells and are skipped. They are partly transparent by default (`polyhedra_alpha=0.6`,
so the centre atom shows through; `1.0` gives a solid hull that hides it) and are cut
at their vertex atoms. Tunables: `bond_scale` / `bond_radius` / `bond_color`, and
`polyhedra_color` / `polyhedra_alpha` / `polyhedra_scale`. CLI: `--bonds`,
`--supercell 2,2,2`, `--show-images`, `--polyhedra Si,Ti`, `--atom-radii Sr:1.1,O:0.3`.

Both are shaded to match the atoms in every style — see the per-style sweeps
([bonds](https://raw.githubusercontent.com/wgst/crystalvase/main/docs/bond-styles.png),
[polyhedra](https://raw.githubusercontent.com/wgst/crystalvase/main/docs/polyhedra-styles.png)).

## Palettes & styles

- **Palettes:** `jmol` (ASE default), `vesta`, `vmd`; tone variants of the ASE colours
  (`pastel`, `muted`, `vivid`, `deep`); and tone schemes where every element keeps its
  hue family but converges on a common tone (the way forest/mint/olive/neon are all
  greens) — `forest`, `wine`, `emerald`, `olive`, `mint`, `blossom` (**default**),
  `tropical`, `neon`, `sage`, `midnight`. Roll your own with `cv.adjust(...)`
  (multiplicative tweaks) or `cv.retone("jmol", hue=..., sat=..., value=...)` (pull towards a tone).
- **Styles** (shading only), all depth-shaded so structure stays clear:
  `clean` — bright matte spheres, no outline, black cell box (MD-snapshot look);
  `cartoon` — flat "sticker" discs shaded at the edges, outlined (`cartoon-dot` adds a
  gloss dot, `cartoon-soft` is smooth matte pastel);
  `realistic` — studio-lit gloss, the default (`realistic-warm`, `realistic-cool`);
  `ase` — classic flat ASE look, outlined + depth-dimmed (`ase-shaded`).
  Custom: `cv.make_style(edge_dark=0.6, hot_amt=1.0, ...)` — see `styles.py`.
- **Hyperrealistic styles** — a per-normal studio shader (one shaped key light, sky and
  floor reflections, a fresnel rim, deep shadows) rather than a radial gradient. They
  differ mainly in material and key-light shape: `studio` (glossy plastic, wide bar),
  `gloss` (lacquered, tight dot), `pearl` (high-gloss, big soft box), `metallic` (satin
  metal, streak), `clay` (soft matte), `velvet` (no highlight, rim-lit only). Bonds take
  a neutral rod material in these, for the model-kit look. They are tuned for **no
  background**; heavier to draw, so pass a lower `rings` for big cells.

`crystalvase --list-palettes` / `--list-styles` print the choices; `examples/` compares
them. Run the tests with `pytest`. MIT licensed.

## Reference galleries

Pick a `style`, `palette` and `radius_scale` by eye. Regenerate with
`python docs/make_gallery.py` (self-contained — builds its own demo structures).

**Styles** (water box, `jmol`) — the last row is hyperrealistic (`cv.STYLES` has the
rest: `clay`, `pearl`, `metallic`):

![styles](https://raw.githubusercontent.com/wgst/crystalvase/main/docs/styles.png)

**Palettes** (default style):

![palettes](https://raw.githubusercontent.com/wgst/crystalvase/main/docs/palettes.png)

**Sizes** (`radius_scale`):

![sizes](https://raw.githubusercontent.com/wgst/crystalvase/main/docs/sizes.png)
