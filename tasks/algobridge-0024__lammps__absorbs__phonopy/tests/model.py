"""Result validation, differential comparison, and scientific invariants."""

from __future__ import annotations

import math

import numpy as np


FC_ATOL = 2e-8
DM_ATOL = 2e-8
EIGENVALUE_ATOL = 2e-8
FREQUENCY_ATOL = 1e-6
PROJECTOR_ATOL = 2e-6


def _finite_array(value, shape, name):
    array = np.asarray(value, dtype=float)
    if array.shape != shape:
        raise ValueError(f"{name}: expected shape {shape}, got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name}: values must be finite")
    return array


def parse_result(data, candidate_input):
    if not isinstance(data, dict) or data.get("format") != "algobridge-fc2-result-v1":
        raise ValueError("invalid result format")
    n_atoms = int(candidate_input["supercell"]["n_atoms"])
    n_primitive = int(candidate_input["supercell"]["n_primitive"])
    dim = 3 * n_primitive
    fc = _finite_array(data.get("force_constants"), (n_atoms, n_atoms, 3, 3), "force_constants")
    scalars = {}
    for key in ("fit_residual_rms", "asr_max", "permutation_max"):
        try:
            value = float(data[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid {key}") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid {key}")
        scalars[key] = value
    qresults = data.get("qpoint_results")
    if not isinstance(qresults, list) or len(qresults) != len(candidate_input["qpoints"]):
        raise ValueError("wrong number of qpoint_results")
    parsed_q = []
    for index, (item, expected_q) in enumerate(zip(qresults, candidate_input["qpoints"], strict=True)):
        if not isinstance(item, dict):
            raise ValueError(f"qpoint_results[{index}] is not an object")
        qpoint = _finite_array(item.get("qpoint"), (3,), f"qpoint[{index}]")
        if not np.allclose(qpoint, expected_q, rtol=0, atol=1e-14):
            raise ValueError(f"qpoint_results[{index}] does not preserve input order/value")
        dm = _finite_array(item.get("dynamical_matrix_real"), (dim, dim), "dm.real") + 1j * _finite_array(
            item.get("dynamical_matrix_imag"), (dim, dim), "dm.imag"
        )
        eigenvalues = _finite_array(item.get("eigenvalues"), (dim,), "eigenvalues")
        frequencies = _finite_array(item.get("frequencies"), (dim,), "frequencies")
        eigenvectors = _finite_array(item.get("eigenvectors_real"), (dim, dim), "eigenvectors.real") + 1j * _finite_array(
            item.get("eigenvectors_imag"), (dim, dim), "eigenvectors.imag"
        )
        parsed_q.append(
            {
                "qpoint": qpoint,
                "dm": dm,
                "eigenvalues": eigenvalues,
                "frequencies": frequencies,
                "eigenvectors": eigenvectors,
            }
        )
    return {"fc": fc, "qresults": parsed_q, **scalars}


def _clusters(values):
    start = 0
    for index in range(1, len(values) + 1):
        if index == len(values) or abs(values[index] - values[start]) > 1e-7 * max(
            1.0, abs(values[start]), abs(values[index])
        ):
            yield start, index
            start = index


def scientific_errors(parsed, candidate_input):
    errors = []
    fc = parsed["fc"]
    permutation = np.max(np.abs(fc - fc.transpose(1, 0, 3, 2)))
    drift_first = np.max(np.abs(fc.sum(axis=0)))
    drift_second = np.max(np.abs(fc.sum(axis=1)))
    if permutation > 1e-9:
        errors.append(f"permutation symmetry residual {permutation:.3g}")
    if max(drift_first, drift_second) > 1e-9:
        errors.append(f"acoustic sum-rule residual {max(drift_first, drift_second):.3g}")
    if abs(parsed["permutation_max"] - permutation) > 1e-9:
        errors.append("reported permutation_max is inconsistent with FC2")
    if abs(parsed["asr_max"] - max(drift_first, drift_second)) > 1e-9:
        errors.append("reported asr_max is inconsistent with FC2")

    factor = float(candidate_input["frequency_factor"])
    masses = np.asarray(candidate_input["supercell"]["masses"], dtype=float)
    for index, item in enumerate(parsed["qresults"]):
        dm = item["dm"]
        values = item["eigenvalues"]
        vectors = item["eigenvectors"]
        if np.max(np.abs(dm - dm.conj().T)) > 1e-10:
            errors.append(f"q[{index}] dynamical matrix is not Hermitian")
        if np.any(np.diff(values) < -1e-10):
            errors.append(f"q[{index}] eigenvalues are not ascending")
        orthogonality = np.linalg.norm(vectors.conj().T @ vectors - np.eye(len(values)), ord="fro")
        residual = np.linalg.norm(dm @ vectors - vectors * values[None, :], ord="fro")
        if orthogonality > 2e-7:
            errors.append(f"q[{index}] eigenvectors are not orthonormal")
        if residual > 2e-7 * max(1.0, np.linalg.norm(dm, ord="fro")):
            errors.append(f"q[{index}] eigenpair residual is too large")
        expected_frequencies = np.sign(values) * np.sqrt(np.abs(values)) * factor
        if not np.allclose(item["frequencies"], expected_frequencies, rtol=2e-8, atol=2e-7):
            errors.append(f"q[{index}] signed frequency law is violated")
        if np.linalg.norm(item["qpoint"]) < 1e-13:
            translation_vectors = []
            for axis in range(3):
                vector = np.zeros(3 * len(masses), dtype=complex)
                for atom, mass in enumerate(masses):
                    vector[3 * atom + axis] = math.sqrt(float(mass))
                vector /= np.linalg.norm(vector)
                translation_vectors.append(vector)
            acoustic_residual = max(np.linalg.norm(dm @ vector) for vector in translation_vectors)
            # The locked pristine finite-displacement pipeline reaches about
            # 9.7e-8 for the most extreme 18:1 mass-contrast fixture.
            if acoustic_residual > 2e-7 * max(1.0, np.linalg.norm(dm, ord=2)):
                errors.append(f"q[{index}] Gamma translation subspace is not acoustic")
    return errors


def compare_results(reference_data, candidate_data, candidate_input):
    reference = parse_result(reference_data, candidate_input)
    candidate = parse_result(candidate_data, candidate_input)
    errors = scientific_errors(candidate, candidate_input)
    metrics = {}

    fc_error = float(np.max(np.abs(candidate["fc"] - reference["fc"])))
    metrics["fc_max_abs"] = fc_error
    if not np.allclose(candidate["fc"], reference["fc"], rtol=2e-8, atol=FC_ATOL):
        errors.append(f"FC2 differential mismatch {fc_error:.3g}")
    for key, atol in (("fit_residual_rms", 2e-10), ("asr_max", 1e-9), ("permutation_max", 1e-9)):
        difference = abs(candidate[key] - reference[key])
        metrics[f"{key}_abs"] = difference
        if difference > atol + 2e-7 * abs(reference[key]):
            errors.append(f"{key} differential mismatch {difference:.3g}")

    projector_worst = 0.0
    dm_worst = 0.0
    eigenvalue_worst = 0.0
    frequency_worst = 0.0
    for index, (ref_item, got_item) in enumerate(zip(reference["qresults"], candidate["qresults"], strict=True)):
        dm_error = float(np.max(np.abs(got_item["dm"] - ref_item["dm"])))
        eigenvalue_error = float(np.max(np.abs(got_item["eigenvalues"] - ref_item["eigenvalues"])))
        frequency_error = float(np.max(np.abs(got_item["frequencies"] - ref_item["frequencies"])))
        dm_worst = max(dm_worst, dm_error)
        eigenvalue_worst = max(eigenvalue_worst, eigenvalue_error)
        frequency_worst = max(frequency_worst, frequency_error)
        if not np.allclose(got_item["dm"], ref_item["dm"], rtol=2e-8, atol=DM_ATOL):
            errors.append(f"q[{index}] dynamical-matrix mismatch {dm_error:.3g}")
        if not np.allclose(
            got_item["eigenvalues"], ref_item["eigenvalues"], rtol=2e-8, atol=EIGENVALUE_ATOL
        ):
            errors.append(f"q[{index}] eigenvalue mismatch {eigenvalue_error:.3g}")
        if not np.allclose(
            got_item["frequencies"], ref_item["frequencies"], rtol=2e-7, atol=FREQUENCY_ATOL
        ):
            errors.append(f"q[{index}] frequency mismatch {frequency_error:.3g}")
        for start, end in _clusters(ref_item["eigenvalues"]):
            ref_vectors = ref_item["eigenvectors"][:, start:end]
            got_vectors = got_item["eigenvectors"][:, start:end]
            ref_projector = ref_vectors @ ref_vectors.conj().T
            got_projector = got_vectors @ got_vectors.conj().T
            projector_error = float(np.linalg.norm(ref_projector - got_projector, ord="fro"))
            projector_worst = max(projector_worst, projector_error)
            if projector_error > PROJECTOR_ATOL:
                errors.append(f"q[{index}] eigenspace[{start}:{end}] mismatch {projector_error:.3g}")
    metrics.update(
        {
            "dm_max_abs": dm_worst,
            "eigenvalue_max_abs": eigenvalue_worst,
            "frequency_max_abs": frequency_worst,
            "projector_fro": projector_worst,
        }
    )
    return not errors, errors, metrics
