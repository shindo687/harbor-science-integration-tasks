"""Native AlphaFold 2 implementation of bounded DockQ 2.1.3 semantics.

The equations and thresholds are derived from DockQ at commit
75db7ab4f6b824c70d120c5f620582e164ed5479 (MIT).  This module is an
independent implementation and does not import, invoke, or vendor DockQ.
"""

import itertools
import math
from typing import Any

import numpy as np

BACKBONE = ("N", "CA", "C", "O")


def _sequence(chain: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(residue["name"]) for residue in chain)


def _atoms(residue: dict[str, Any]) -> list[np.ndarray]:
    # DockQ's PDB parser drops hydrogens before computing residue distances.
    return [
        np.asarray(value, dtype=float)
        for name, value in residue["atoms"].items()
        if not name.strip().upper().lstrip("0123456789").startswith(("H", "D"))
    ]


def _matched_backbone(
    model_residue: dict[str, Any], native_residue: dict[str, Any]
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    model_atoms = []
    native_atoms = []
    for name in BACKBONE:
        if name in model_residue["atoms"] and name in native_residue["atoms"]:
            model_atoms.append(np.asarray(model_residue["atoms"][name], dtype=float))
            native_atoms.append(np.asarray(native_residue["atoms"][name], dtype=float))
    return model_atoms, native_atoms


def _minimum_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_atoms = _atoms(left)
    right_atoms = _atoms(right)
    if not left_atoms or not right_atoms:
        return math.inf
    return min(float(np.linalg.norm(a - b)) for a in left_atoms for b in right_atoms)


def _pairs(left: list[dict[str, Any]], right: list[dict[str, Any]], cutoff: float) -> set[tuple[int, int]]:
    return {(i, j) for i, a in enumerate(left) for j, b in enumerate(right) if _minimum_distance(a, b) < cutoff}


def _kabsch_rmsd(mobile: list[np.ndarray], target: list[np.ndarray]) -> float:
    p = np.asarray(mobile, dtype=float)
    q = np.asarray(target, dtype=float)
    if p.shape != q.shape or not len(p):
        raise ValueError("coordinate sets must be non-empty and have identical shape")
    pc = p - p.mean(axis=0)
    qc = q - q.mean(axis=0)
    u, _, vt = np.linalg.svd(pc.T @ qc)
    correction = np.eye(3)
    correction[-1, -1] = np.sign(np.linalg.det(u @ vt)) or 1.0
    rotation = u @ correction @ vt
    fitted = pc @ rotation
    return float(np.sqrt(np.mean(np.sum((fitted - qc) ** 2, axis=1))))


def _fit_transform(mobile: list[np.ndarray], target: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(mobile, dtype=float)
    q = np.asarray(target, dtype=float)
    pc = p - p.mean(axis=0)
    qc = q - q.mean(axis=0)
    u, _, vt = np.linalg.svd(pc.T @ qc)
    correction = np.eye(3)
    correction[-1, -1] = np.sign(np.linalg.det(u @ vt)) or 1.0
    rotation = u @ correction @ vt
    translation = q.mean(axis=0) - p.mean(axis=0) @ rotation
    return rotation, translation


def _rmsd_after_transform(mobile: list[np.ndarray], target: list[np.ndarray], rotation: np.ndarray, translation: np.ndarray) -> float:
    p = np.asarray(mobile, dtype=float) @ rotation + translation
    q = np.asarray(target, dtype=float)
    return float(np.sqrt(np.mean(np.sum((p - q) ** 2, axis=1))))


def quality_label(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.49:
        return "medium"
    if score >= 0.23:
        return "acceptable"
    return "incorrect"


def pair_metrics(model_left: list[dict[str, Any]], model_right: list[dict[str, Any]], native_left: list[dict[str, Any]], native_right: list[dict[str, Any]], contact_cutoff: float = 5.0, interface_cutoff: float = 10.0) -> dict[str, Any]:
    if _sequence(model_left) != _sequence(native_left) or _sequence(model_right) != _sequence(native_right):
        raise ValueError("mapped chains must have identical residue sequences")
    native_contacts = _pairs(native_left, native_right, contact_cutoff)
    if not native_contacts:
        raise ValueError("native chain pair has no contacts")
    model_contacts = _pairs(model_left, model_right, contact_cutoff)
    fnat = len(native_contacts & model_contacts) / len(native_contacts)
    native_interface = _pairs(native_left, native_right, interface_cutoff)
    left_ids = sorted({i for i, _ in native_interface})
    right_ids = sorted({j for _, j in native_interface})
    model_interface: list[np.ndarray] = []
    native_interface_atoms: list[np.ndarray] = []
    for model_chain, native_chain, indices in ((model_left, native_left, left_ids), (model_right, native_right, right_ids)):
        for index in indices:
            ma, na = _matched_backbone(model_chain[index], native_chain[index])
            model_interface.extend(ma)
            native_interface_atoms.extend(na)
    irmsd = _kabsch_rmsd(model_interface, native_interface_atoms)
    if len(native_left) > len(native_right):
        model_receptor, native_receptor = model_left, native_left
        model_ligand, native_ligand = model_right, native_right
    else:
        model_receptor, native_receptor = model_right, native_right
        model_ligand, native_ligand = model_left, native_left
    model_receptor_atoms: list[np.ndarray] = []
    native_receptor_atoms: list[np.ndarray] = []
    for model_residue, native_residue in zip(model_receptor, native_receptor):
        ma, na = _matched_backbone(model_residue, native_residue)
        model_receptor_atoms.extend(ma)
        native_receptor_atoms.extend(na)
    model_ligand_atoms: list[np.ndarray] = []
    native_ligand_atoms: list[np.ndarray] = []
    for model_residue, native_residue in zip(model_ligand, native_ligand):
        ma, na = _matched_backbone(model_residue, native_residue)
        model_ligand_atoms.extend(ma)
        native_ligand_atoms.extend(na)
    rotation, translation = _fit_transform(model_receptor_atoms, native_receptor_atoms)
    lrmsd = _rmsd_after_transform(model_ligand_atoms, native_ligand_atoms, rotation, translation)
    dockq = (fnat + 1.0 / (1.0 + (irmsd / 1.5) ** 2) + 1.0 / (1.0 + (lrmsd / 8.5) ** 2)) / 3.0
    return {
        "fnat": float(fnat), "iRMSD": irmsd, "LRMSD": lrmsd,
        "DockQ": float(dockq), "CAPRI": quality_label(dockq),
        "native_contacts": len(native_contacts), "preserved_contacts": len(native_contacts & model_contacts),
    }


def score_complex(model: dict[str, Any], native: dict[str, Any], mapping: dict[str, str] | None = None, contact_cutoff: float = 5.0, interface_cutoff: float = 10.0) -> dict[str, Any]:
    model_chains = model["chains"]
    native_chains = native["chains"]
    if len(model_chains) != 2 or len(native_chains) != 2:
        raise ValueError("this bounded implementation requires exactly two chains")
    if mapping is None:
        native_ids = sorted(native_chains)
        candidates = []
        for permutation in itertools.permutations(native_ids):
            current = dict(zip(sorted(model_chains), permutation))
            if all(_sequence(model_chains[m]) == _sequence(native_chains[n]) for m, n in current.items()):
                candidates.append(current)
    else:
        supplied = dict(mapping)
        if set(supplied) != set(model_chains):
            raise ValueError("mapping must cover both model chains exactly")
        if len(set(supplied.values())) != 2 or set(supplied.values()) != set(native_chains):
            raise ValueError("mapping must be a bijection onto both native chains")
        if not all(
            _sequence(model_chains[model_id]) == _sequence(native_chains[native_id])
            for model_id, native_id in supplied.items()
        ):
            raise ValueError("mapping is not sequence-compatible")
        candidates = [supplied]
    if not candidates:
        raise ValueError("no sequence-compatible chain mapping")
    scored = []
    for current in candidates:
        model_ids = sorted(current)
        native_ids = [current[mid] for mid in model_ids]
        metrics = pair_metrics(model_chains[model_ids[0]], model_chains[model_ids[1]], native_chains[native_ids[0]], native_chains[native_ids[1]], contact_cutoff, interface_cutoff)
        metrics["mapping"] = current
        scored.append(metrics)
    return sorted(scored, key=lambda item: (-item["DockQ"], json_mapping(item["mapping"])))[0]


def json_mapping(mapping: dict[str, str]) -> str:
    return ",".join(f"{key}:{mapping[key]}" for key in sorted(mapping))


def protein_to_structure(prot) -> dict[str, Any]:
    """Convert an AlphaFold ``Protein`` into the bounded in-memory contract."""
    from alphafold.common import residue_constants

    restypes = residue_constants.restypes + ["X"]
    chains: dict[str, list[dict[str, Any]]] = {}
    for index in range(len(prot.aatype)):
        chain_id = chr(ord("A") + int(prot.chain_index[index]))
        one_letter = restypes[int(prot.aatype[index])]
        residue_name = residue_constants.restype_1to3.get(one_letter, "UNK")
        atoms = {}
        for atom_name, atom_index in residue_constants.atom_order.items():
            if prot.atom_mask[index, atom_index] >= 0.5:
                atoms[atom_name] = [
                    float(value) for value in prot.atom_positions[index, atom_index]
                ]
        chains.setdefault(chain_id, []).append(
            {"name": residue_name, "atoms": atoms}
        )
    return {"chains": chains}


def main() -> None:
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--native", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.model, encoding="utf-8") as handle: model = json.load(handle)
    with open(args.native, encoding="utf-8") as handle: native = json.load(handle)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(
            score_complex(model, native),
            handle,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        handle.write("\n")

if __name__ == "__main__": main()
