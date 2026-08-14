"""Bounded third-order force-constant reconstruction for phonopy."""

from __future__ import annotations

from itertools import combinations_with_replacement, permutations
import math
from numbers import Real

import numpy as np

from phonopy.structure.atoms import PhonopyAtoms
from phonopy.structure.symmetry import Symmetry


_RCOND = 1e-12


def _validate(supercell, displacements, forces, is_symmetry, symprec):
    if not isinstance(supercell, PhonopyAtoms):
        raise TypeError("supercell must be a PhonopyAtoms")
    if not isinstance(is_symmetry, (bool, np.bool_)):
        raise TypeError("is_symmetry must be boolean")
    if not isinstance(symprec, Real) or isinstance(symprec, (bool, np.bool_)):
        raise TypeError("symprec must be a real number")
    symprec = float(symprec)
    if not math.isfinite(symprec) or symprec <= 0.0:
        raise ValueError("symprec must be finite and positive")
    try:
        displacement_array = np.asarray(displacements, dtype=float)
        force_array = np.asarray(forces, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError("displacements and forces must be numeric arrays") from exc
    if displacement_array.ndim != 3 or displacement_array.shape[-1:] != (3,):
        raise ValueError("displacements must have shape (snapshots, atoms, 3)")
    if force_array.shape != displacement_array.shape:
        raise ValueError("forces must have the same shape as displacements")
    snapshots, n_atoms, _ = displacement_array.shape
    if n_atoms != len(supercell):
        raise ValueError("array atom count must match supercell")
    if not 2 <= n_atoms <= 4:
        raise ValueError("bounded fitting requires two to four atoms")
    if not 2 <= snapshots <= 512:
        raise ValueError("bounded fitting requires two to 512 snapshots")
    if not np.all(np.isfinite(displacement_array)):
        raise ValueError("displacements must be finite")
    if not np.all(np.isfinite(force_array)):
        raise ValueError("forces must be finite")
    return displacement_array, force_array, bool(is_symmetry), symprec


def _relative_map(n_atoms):
    matrix = np.zeros((3 * (n_atoms - 1), 3 * n_atoms), dtype=float)
    for atom in range(n_atoms - 1):
        for axis in range(3):
            row = 3 * atom + axis
            matrix[row, row] = 1.0
            matrix[row, 3 * (n_atoms - 1) + axis] = -1.0
    return matrix


def _monomials(n_relative):
    pairs = list(combinations_with_replacement(range(n_relative), 2))
    triples = list(combinations_with_replacement(range(n_relative), 3))
    return pairs, triples


def _design(displacements):
    snapshots, n_atoms, _ = displacements.shape
    transform = _relative_map(n_atoms)
    pairs, triples = _monomials(transform.shape[0])
    terms = pairs + triples
    design = np.zeros((snapshots * 3 * n_atoms, len(terms)), dtype=float)
    for snapshot in range(snapshots):
        relative = transform @ displacements[snapshot].reshape(-1)
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


def _operations(supercell, is_symmetry, symprec):
    symmetry = Symmetry(
        supercell,
        symprec=symprec,
        is_symmetry=is_symmetry,
        lang="Rust",
    )
    rotations = symmetry.symmetry_operations["rotations"]
    atom_permutations = symmetry.atomic_permutations
    lattice = np.asarray(supercell.cell, dtype=float).T
    inverse_lattice = np.linalg.inv(lattice)
    cartesian = np.asarray(
        [lattice @ rotation @ inverse_lattice for rotation in rotations],
        dtype=float,
    )
    return cartesian, np.asarray(atom_permutations, dtype=int)


def _augment(supercell, displacements, forces, is_symmetry, symprec):
    rotations, atom_permutations = _operations(
        supercell, is_symmetry, symprec
    )
    all_displacements = []
    all_forces = []
    for rotation, atom_permutation in zip(
            rotations, atom_permutations, strict=True):
        transformed_displacements = np.zeros_like(displacements)
        transformed_forces = np.zeros_like(forces)
        for source, target in enumerate(atom_permutation):
            transformed_displacements[:, target] = (
                displacements[:, source] @ rotation.T
            )
            transformed_forces[:, target] = forces[:, source] @ rotation.T
        all_displacements.append(transformed_displacements)
        all_forces.append(transformed_forces)
    return (
        np.concatenate(all_displacements),
        np.concatenate(all_forces),
        len(rotations),
    )


def _force_constants(coefficients, n_atoms):
    transform = _relative_map(n_atoms)
    n_relative = transform.shape[0]
    pairs, triples = _monomials(n_relative)
    fc2_relative = np.zeros((n_relative, n_relative), dtype=float)
    fc3_relative = np.zeros((n_relative,) * 3, dtype=float)
    pair_count = len(pairs)
    for value, indices in zip(coefficients[:pair_count], pairs, strict=True):
        ordered_indices = set(permutations(indices))
        for ordered in ordered_indices:
            fc2_relative[ordered] = 2.0 * value / len(ordered_indices)
    for value, indices in zip(coefficients[pair_count:], triples, strict=True):
        ordered_indices = set(permutations(indices))
        for ordered in ordered_indices:
            fc3_relative[ordered] = 6.0 * value / len(ordered_indices)
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


def _predict(displacements, fc2, fc3):
    harmonic = -np.einsum(
        "ijab,sjb->sia", fc2, displacements, optimize=True
    )
    cubic = -0.5 * np.einsum(
        "ijkabc,sjb,skc->sia",
        fc3,
        displacements,
        displacements,
        optimize=True,
    )
    return harmonic + cubic


def fit_fc3(supercell, displacements, forces, *, is_symmetry=True,
            symprec=1e-5):
    """Fit full harmonic and third-order force constants jointly."""
    displacements, forces, is_symmetry, symprec = _validate(
        supercell, displacements, forces, is_symmetry, symprec
    )
    augmented_u, augmented_f, operation_count = _augment(
        supercell, displacements, forces, is_symmetry, symprec
    )
    design = _design(augmented_u)
    coefficients, _, rank, singular_values = np.linalg.lstsq(
        design, augmented_f.reshape(-1), rcond=_RCOND
    )
    rank = int(rank)
    if rank == 0:
        raise ValueError("force-constant design has zero rank")
    fc2, fc3 = _force_constants(coefficients, len(supercell))
    predicted = _predict(displacements, fc2, fc3)
    condition = float(singular_values[0] / singular_values[rank - 1])
    return {
        "fc2": fc2,
        "fc3": fc3,
        "predicted_forces": predicted,
        "residual_norm": float(np.linalg.norm(predicted - forces)),
        "rank": rank,
        "singular_values": singular_values,
        "condition_number": condition,
        "n_parameters": int(design.shape[1]),
        "symmetry_operation_count": operation_count,
    }


__all__ = ["fit_fc3"]
