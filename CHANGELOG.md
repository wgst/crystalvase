# Changelog

## 0.2.0

- **Bonds** — `bonds=True` draws ball-and-stick bonds from covalent-radius cutoffs
  (`bond_scale`, `bond_radius`, `bond_color`), split at the midpoint and coloured by
  each atom, fully vector and depth-composited. Rods are anchored in true 3-D: each
  half is depth-segmented against the sphere surfaces, so a bond pointing at the
  camera emerges across its atom's face, with a rounded junction, a contact shadow,
  and shading matched to the balls. (#1)
- **Supercells & periodic images** — `supercell=(nx, ny, nz)` replicates a periodic
  cell; `show_images=True` completes the cell with periodic images of boundary atoms
  (VESTA-style). (#2)
- **Coordination polyhedra** — `polyhedra=["Si", "Ti"]` draws VESTA-style filled
  polyhedra around the chosen elements (`polyhedra_color`, `polyhedra_alpha`,
  `polyhedra_scale`). Partly transparent by default (`polyhedra_alpha=0.6`) so the
  centre atom shows through, shadowed as if enclosed; `1.0` gives a solid hull that
  hides it. Faces are cut at their vertex atoms and carry per-face depth, and only
  complete coordination shells are drawn (boundary atoms with partial shells are
  skipped — add `show_images=True` to complete them). (#4)
- **Hyperrealistic styles** — `studio`, `gloss`, `pearl`, `metallic`, `clay`, `velvet`:
  a per-surface-normal studio shader (one shaped key light, sky/floor reflections,
  fresnel rim, deep shadows) with a neutral rod material for bonds. Still fully vector.
- **`atom_radii`** — per-element radii in Angstrom, e.g. `{"Sr": 1.1, "O": 0.3}`
  (CLI: `--atom-radii Sr:1.1,O:0.3`); other elements keep `radius_scale`.
- `write()` now forwards any render option via `**kwargs`; `python -m crystalvase`
  works alongside the `crystalvase` command.

### Fixed

- Convex-hull face normals were inverted, so polyhedra were drawn from their **back**
  faces: the front vertex lost all its faces and rear faces converged on a point that
  projects elsewhere. Facet lighting was flipped by the same bug.
- `label="formula"` counted periodic-image duplicates as stoichiometry; the formula is
  now taken from the supercell before boundary images are added.

## 0.1.0

- First release: vector 3D-looking figures of ASE structures (styles, palettes,
  sizes, labels, depth-composited unit cell, `render`/`write`/`grid`/`demo`).
