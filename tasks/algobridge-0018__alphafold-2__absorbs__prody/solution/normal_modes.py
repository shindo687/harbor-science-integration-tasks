"""Bounded elastic-network normal modes for AlphaFold protein structures."""

from __future__ import annotations

import math
from numbers import Integral, Real

import numpy as np

from alphafold.common import protein as protein_module
from alphafold.common import residue_constants


_ZERO_THRESHOLD = 1e-6
_CA_INDEX = residue_constants.atom_order["CA"]


def _finite_real(name, value):
    if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _chain_selection(chain_indices):
    if chain_indices is None:
        return None
    if isinstance(chain_indices, Integral) and not isinstance(
            chain_indices, (bool, np.bool_)):
        return np.asarray([int(chain_indices)], dtype=int)
    if isinstance(chain_indices, (str, bytes)):
        raise TypeError("chain_indices must contain integers")
    try:
        values = list(chain_indices)
    except TypeError as exc:
        raise TypeError("chain_indices must be an integer or iterable") from exc
    if not values:
        raise ValueError("chain_indices must not be empty")
    if any(not isinstance(value, Integral) or isinstance(value, (bool, np.bool_))
           for value in values):
        raise TypeError("chain_indices must contain integers")
    return np.asarray(sorted(set(int(value) for value in values)), dtype=int)


def _select_residues(protein, chains, plddt_threshold):
    mask = np.asarray(protein.atom_mask[:, _CA_INDEX] >= 0.5, dtype=bool)
    if chains is not None:
        mask &= np.isin(protein.chain_index, chains)
    if plddt_threshold is not None:
        mask &= protein.b_factors[:, _CA_INDEX] >= plddt_threshold
    indices = np.flatnonzero(mask)
    if len(indices) < 4:
        raise ValueError("at least four selected C-alpha residues are required")
    coordinates = np.asarray(
        protein.atom_positions[indices, _CA_INDEX], dtype=float
    )
    if coordinates.shape != (len(indices), 3) or not np.all(np.isfinite(coordinates)):
        raise ValueError("selected C-alpha coordinates must be finite")
    mapping = [
        {
            "source_index": int(index),
            "chain_index": int(protein.chain_index[index]),
            "residue_index": int(protein.residue_index[index]),
            "aatype": int(protein.aatype[index]),
        }
        for index in indices
    ]
    return coordinates, mapping


def _kirchhoff(coordinates, cutoff, gamma):
    count = len(coordinates)
    matrix = np.zeros((count, count), dtype=float)
    cutoff_squared = cutoff * cutoff
    for first in range(count - 1):
        for second in range(first + 1, count):
            displacement = coordinates[second] - coordinates[first]
            distance_squared = float(displacement @ displacement)
            if distance_squared > cutoff_squared:
                continue
            matrix[first, second] = -gamma
            matrix[second, first] = -gamma
            matrix[first, first] += gamma
            matrix[second, second] += gamma
    return matrix


def _hessian(coordinates, cutoff, gamma):
    count = len(coordinates)
    matrix = np.zeros((3 * count, 3 * count), dtype=float)
    cutoff_squared = cutoff * cutoff
    for first in range(count - 1):
        first_slice = slice(3 * first, 3 * first + 3)
        for second in range(first + 1, count):
            displacement = coordinates[second] - coordinates[first]
            distance_squared = float(displacement @ displacement)
            if distance_squared > cutoff_squared:
                continue
            if distance_squared <= 0.0:
                raise ValueError("selected C-alpha coordinates must be distinct")
            second_slice = slice(3 * second, 3 * second + 3)
            block = -gamma * np.outer(displacement, displacement) / distance_squared
            matrix[first_slice, second_slice] = block
            matrix[second_slice, first_slice] = block
            matrix[first_slice, first_slice] -= block
            matrix[second_slice, second_slice] -= block
    return matrix


def _mode_statistics(model, modes, eigenvalues, residue_count):
    covariance = (modes * (1.0 / eigenvalues)[None, :]) @ modes.T
    if model == "gnm":
        residue_covariance = covariance
    else:
        blocks = covariance.reshape(residue_count, 3, residue_count, 3)
        residue_covariance = np.trace(blocks, axis1=1, axis2=3)
    msf = np.diag(residue_covariance).copy()
    denominator = np.sqrt(np.outer(msf, msf))
    correlation = np.divide(
        residue_covariance, denominator,
        out=np.zeros_like(residue_covariance), where=denominator > 0,
    )
    return msf, correlation


def analyze_normal_modes(protein, *, model="gnm", chain_indices=None,
                         cutoff=10.0, gamma=1.0, plddt_threshold=None,
                         n_modes=5):
    """Build a selected C-alpha elastic network and return its soft modes."""
    if not isinstance(protein, protein_module.Protein):
        raise TypeError("protein must be an alphafold.common.protein.Protein")
    if not isinstance(model, str):
        raise TypeError("model must be 'gnm' or 'anm'")
    model = model.lower()
    if model not in {"gnm", "anm"}:
        raise ValueError("model must be 'gnm' or 'anm'")
    chains = _chain_selection(chain_indices)
    cutoff = _finite_real("cutoff", cutoff)
    gamma = _finite_real("gamma", gamma)
    if cutoff < 4.0:
        raise ValueError("cutoff must be at least 4.0 angstrom")
    if gamma <= 0.0:
        raise ValueError("gamma must be positive")
    if plddt_threshold is not None:
        plddt_threshold = _finite_real("plddt_threshold", plddt_threshold)
    if not isinstance(n_modes, Integral) or isinstance(n_modes, (bool, np.bool_)):
        raise TypeError("n_modes must be an integer")
    n_modes = int(n_modes)
    if n_modes <= 0:
        raise ValueError("n_modes must be positive")

    coordinates, mapping = _select_residues(
        protein, chains, plddt_threshold
    )
    network = (
        _kirchhoff(coordinates, cutoff, gamma)
        if model == "gnm"
        else _hessian(coordinates, cutoff, gamma)
    )
    all_eigenvalues, all_modes = np.linalg.eigh(network)
    zero_count = int(np.sum(all_eigenvalues < _ZERO_THRESHOLD))
    positive = np.flatnonzero(all_eigenvalues >= _ZERO_THRESHOLD)
    if len(positive) == 0:
        raise ValueError("elastic network has no positive mode")
    selected = positive[:n_modes]
    eigenvalues = all_eigenvalues[selected]
    modes = all_modes[:, selected]
    msf, correlation = _mode_statistics(
        model, modes, eigenvalues, len(mapping)
    )
    return {
        "model": model,
        "residue_mapping": mapping,
        "network_matrix": network,
        "zero_mode_count": zero_count,
        "eigenvalues": eigenvalues,
        "modes": modes,
        "msf": msf,
        "cross_correlation": correlation,
    }


__all__ = ["analyze_normal_modes"]

