"""Verifier-owned bounded polynomial-force model utilities."""

from __future__ import annotations

from itertools import combinations_with_replacement, permutations

import numpy as np
from phonopy.structure.symmetry import Symmetry


RCOND = 1e-12


def relative_map(n_atoms):
    """Map Cartesian displacements to differences from the final atom."""
    matrix = np.zeros((3 * (n_atoms - 1), 3 * n_atoms), dtype=float)
    for atom in range(n_atoms - 1):
        for axis in range(3):
            row = 3 * atom + axis
            matrix[row, row] = 1.0
            matrix[row, 3 * (n_atoms - 1) + axis] = -1.0
    return matrix


def monomial_indices(n_relative):
    pairs = list(combinations_with_replacement(range(n_relative), 2))
    triples = list(combinations_with_replacement(range(n_relative), 3))
    return pairs, triples


def polynomial_design(displacements):
    """Return the deterministic force-design matrix before SG augmentation."""
    values = np.asarray(displacements, dtype=float)
    n_snapshots, n_atoms, _ = values.shape
    transform = relative_map(n_atoms)
    pairs, triples = monomial_indices(transform.shape[0])
    terms = pairs + triples
    design = np.zeros((n_snapshots * 3 * n_atoms, len(terms)), dtype=float)
    for snapshot in range(n_snapshots):
        relative = transform @ values[snapshot].reshape(-1)
        rows = slice(snapshot * 3 * n_atoms, (snapshot + 1) * 3 * n_atoms)
        for column, indices in enumerate(terms):
            gradient = np.zeros(len(relative), dtype=float)
            for coordinate in set(indices):
                remainder = list(indices)
                remainder.remove(coordinate)
                gradient[coordinate] = (
                    indices.count(coordinate) * np.prod(relative[remainder])
                )
            design[rows, column] = -(transform.T @ gradient)
    return design


def symmetry_operations(supercell, is_symmetry, symprec):
    symmetry = Symmetry(
        supercell, symprec=symprec, is_symmetry=is_symmetry, lang="Rust"
    )
    rotations = symmetry.symmetry_operations["rotations"]
    permutations_ = symmetry.atomic_permutations
    lattice = np.asarray(supercell.cell, dtype=float).T
    inverse_lattice = np.linalg.inv(lattice)
    cartesian = np.asarray(
        [lattice @ rotation @ inverse_lattice for rotation in rotations],
        dtype=float,
    )
    return cartesian, np.asarray(permutations_, dtype=int)


def augment_by_symmetry(supercell, displacements, forces, is_symmetry, symprec):
    rotations, permutations_ = symmetry_operations(
        supercell, is_symmetry, symprec
    )
    source_u = np.asarray(displacements, dtype=float)
    source_f = np.asarray(forces, dtype=float)
    all_u = []
    all_f = []
    for rotation, permutation in zip(rotations, permutations_, strict=True):
        transformed_u = np.zeros_like(source_u)
        transformed_f = np.zeros_like(source_f)
        for source, target in enumerate(permutation):
            transformed_u[:, target] = source_u[:, source] @ rotation.T
            transformed_f[:, target] = source_f[:, source] @ rotation.T
        all_u.append(transformed_u)
        all_f.append(transformed_f)
    return np.concatenate(all_u), np.concatenate(all_f), len(rotations)


def constrained_design(supercell, displacements, forces, is_symmetry, symprec):
    augmented_u, augmented_f, operation_count = augment_by_symmetry(
        supercell, displacements, forces, is_symmetry, symprec
    )
    return polynomial_design(augmented_u), augmented_f, operation_count


def coefficients_to_force_constants(coefficients, n_atoms):
    """Convert unique relative-coordinate energy terms to full FC2/FC3."""
    transform = relative_map(n_atoms)
    n_relative = transform.shape[0]
    pairs, triples = monomial_indices(n_relative)
    fc2_relative = np.zeros((n_relative, n_relative), dtype=float)
    fc3_relative = np.zeros((n_relative,) * 3, dtype=float)
    pair_count = len(pairs)
    for value, indices in zip(coefficients[:pair_count], pairs, strict=True):
        unique = set(permutations(indices))
        for ordered in unique:
            fc2_relative[ordered] = 2.0 * value / len(unique)
    for value, indices in zip(coefficients[pair_count:], triples, strict=True):
        unique = set(permutations(indices))
        for ordered in unique:
            fc3_relative[ordered] = 6.0 * value / len(unique)
    full_fc2 = np.einsum(
        "ia,jb,ij->ab", transform, transform, fc2_relative, optimize=True
    )
    full_fc3 = np.einsum(
        "ia,jb,kc,ijk->abc",
        transform,
        transform,
        transform,
        fc3_relative,
        optimize=True,
    )
    fc2 = full_fc2.reshape(n_atoms, 3, n_atoms, 3).transpose(0, 2, 1, 3)
    fc3 = full_fc3.reshape(
        n_atoms, 3, n_atoms, 3, n_atoms, 3
    ).transpose(0, 2, 4, 1, 3, 5)
    return fc2, fc3


def predict_forces(displacements, fc2, fc3):
    values = np.asarray(displacements, dtype=float)
    harmonic = -np.einsum("ijab,sjb->sia", fc2, values, optimize=True)
    cubic = -0.5 * np.einsum(
        "ijkabc,sjb,skc->sia", fc3, values, values, optimize=True
    )
    return harmonic + cubic


def design_diagnostics(design):
    singular_values = np.linalg.svd(design, compute_uv=False)
    if len(singular_values) == 0 or singular_values[0] == 0:
        return 0, singular_values, 0.0
    rank = int(np.sum(singular_values > RCOND * singular_values[0]))
    condition = (
        float(singular_values[0] / singular_values[rank - 1])
        if rank
        else 0.0
    )
    return rank, singular_values, condition
