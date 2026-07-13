"""Small, self-contained demo structures (built with ASE, no data files) for
galleries, examples and tests."""
import numpy as np
from ase import Atoms
from ase.build import molecule


def water_box(n=3, spacing=3.1, seed=7):
    """``n**3`` randomly oriented water molecules on a jittered grid (O + H)."""
    rng = np.random.default_rng(seed)
    L = n * spacing
    box = Atoms(cell=[L, L, L], pbc=True)
    for ix in range(n):
        for iy in range(n):
            for iz in range(n):
                m = molecule("H2O")
                m.rotate(rng.uniform(0, 360), rng.standard_normal(3) + 1e-6)
                c = (np.array([ix, iy, iz]) + 0.5) * spacing + rng.uniform(-0.5, 0.5, 3)
                m.translate(c - m.get_positions().mean(0))
                box += m
    return box


def cluster(seed=3):
    """A small jittered box of chemically diverse atoms, so every palette shows a
    good spread of element colours (illustrative, not a physical structure)."""
    syms = ["O", "N", "S", "F", "Cl", "C", "H", "P", "Na", "K", "Ti", "Fe", "Cu", "Br"]
    rng = np.random.default_rng(seed)
    L, n = 12.0, 3
    grid = [(x, y, z) for x in range(n) for y in range(n) for z in range(n)]
    pts = [(np.array(g) + 0.5) * (L / n) + rng.uniform(-0.7, 0.7, 3)
           for g in grid[:len(syms)]]
    return Atoms(syms, positions=pts, cell=[L, L, L], pbc=True)
