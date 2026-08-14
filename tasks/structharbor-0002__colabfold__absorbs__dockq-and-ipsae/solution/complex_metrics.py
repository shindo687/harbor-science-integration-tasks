"""Independent ColabFold implementation of bounded DockQ and ipSAE semantics.

The equations and thresholds are derived from DockQ at commit
75db7ab4f6b824c70d120c5f620582e164ed5479 (MIT).  This module is an
independent implementation and does not import, invoke, or vendor DockQ.

The ipSAE equations are independently implemented from DunbrackLab/IPSAE at
commit 6174cf9e71cb1bd660cc805856a18c4871a6dec3 (MIT).  The supported ipSAE
contract is AlphaFold2/ColabFold protein PDB output with one PAE/plDDT value
per residue.
"""

import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

BACKBONE = ("N", "CA", "C", "O")


def _read_text(value: str | Path) -> str:
    if isinstance(value, Path):
        return value.read_text(encoding="utf-8")
    if "\n" not in value and len(value) < 4096:
        path = Path(value)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return value


def pdb_to_structure(value: str | Path) -> dict[str, Any]:
    """Parse the first MODEL of a protein PDB into the bounded DockQ contract."""
    chains: dict[str, list[dict[str, Any]]] = {}
    residues: dict[tuple[str, str, str], dict[str, Any]] = {}
    for line in _read_text(value).splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM"):
            continue
        altloc = line[16:17]
        if altloc not in (" ", "A"):
            continue
        chain_id = line[21:22].strip() or "_"
        key = (chain_id, line[22:26], line[26:27])
        if key not in residues:
            residue = {"name": line[17:20].strip(), "atoms": {}}
            residues[key] = residue
            chains.setdefault(chain_id, []).append(residue)
        residues[key]["atoms"][line[12:16].strip()] = [
            float(line[30:38]), float(line[38:46]), float(line[46:54])
        ]
    if not chains:
        raise ValueError("PDB contains no protein ATOM records")
    return {"chains": chains}


def _sequence(chain: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(residue["name"]) for residue in chain)


def _atoms(residue: dict[str, Any]) -> list[np.ndarray]:
    # DockQ removes hydrogen/deuterium atoms before residue-distance tests.
    return [
        np.asarray(value, dtype=float)
        for name, value in residue["atoms"].items()
        if not name.strip().upper().lstrip("0123456789").startswith(("H", "D"))
    ]


def _matched_backbone(
    model_residue: dict[str, Any], native_residue: dict[str, Any]
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    model_atoms: list[np.ndarray] = []
    native_atoms: list[np.ndarray] = []
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
        model_atoms, native_atoms = _matched_backbone(model_residue, native_residue)
        model_receptor_atoms.extend(model_atoms)
        native_receptor_atoms.extend(native_atoms)
    model_ligand_atoms: list[np.ndarray] = []
    native_ligand_atoms: list[np.ndarray] = []
    for model_residue, native_residue in zip(model_ligand, native_ligand):
        model_atoms, native_atoms = _matched_backbone(model_residue, native_residue)
        model_ligand_atoms.extend(model_atoms)
        native_ligand_atoms.extend(native_atoms)
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


def score_dockq(
    model_pdb: str | Path,
    native_pdb: str | Path,
    mapping: dict[str, str] | None = None,
    contact_cutoff: float = 5.0,
    interface_cutoff: float = 10.0,
) -> dict[str, Any]:
    """Score two-chain PDB text or paths with the bounded DockQ contract."""
    return score_complex(
        pdb_to_structure(model_pdb),
        pdb_to_structure(native_pdb),
        mapping=mapping,
        contact_cutoff=contact_cutoff,
        interface_cutoff=interface_cutoff,
    )


def _pdb_residues(value: str | Path) -> list[dict[str, Any]]:
    structure = pdb_to_structure(value)
    residues: list[dict[str, Any]] = []
    for chain_id, chain in structure["chains"].items():
        for number, residue in enumerate(chain, start=1):
            atoms = residue["atoms"]
            if "CA" not in atoms:
                raise ValueError(f"chain {chain_id} residue {number} lacks CA")
            representative = atoms.get("CA") if residue["name"] == "GLY" else atoms.get("CB")
            if representative is None:
                raise ValueError(f"chain {chain_id} residue {number} lacks CB")
            residues.append({
                "chain": chain_id,
                "number": number,
                "name": residue["name"],
                "coordinate": np.asarray(representative, dtype=float),
            })
    return residues


def _d0(length: int) -> float:
    if length > 27:
        return max(1.0, 1.24 * (float(length) - 15.0) ** (1.0 / 3.0) - 1.8)
    return 1.0


def _ptm(values: np.ndarray, scale: float | np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + (values / scale) ** 2.0)


def score_ipsae(
    pae: Any,
    plddt: Any,
    model_pdb: str | Path,
    pae_cutoff: float = 15.0,
    distance_cutoff: float = 15.0,
    iptm: float | None = None,
) -> dict[str, Any]:
    """Return Dunbrack ipSAE-v4 chain-pair records for a ColabFold model."""
    residues = _pdb_residues(model_pdb)
    chains = np.asarray([residue["chain"] for residue in residues])
    chain_ids = list(dict.fromkeys(chains.tolist()))
    if len(chain_ids) < 2:
        raise ValueError("ipSAE requires at least two protein chains")
    pae_array = np.asarray(pae, dtype=float)
    plddt_array = np.asarray(plddt, dtype=float)
    size = len(residues)
    if pae_array.shape != (size, size):
        raise ValueError(f"PAE shape {pae_array.shape} does not match {size} residues")
    if plddt_array.shape != (size,):
        raise ValueError(f"plDDT shape {plddt_array.shape} does not match {size} residues")
    if not np.isfinite(pae_array).all() or not np.isfinite(plddt_array).all():
        raise ValueError("PAE and plDDT must be finite")

    coordinates = np.asarray([residue["coordinate"] for residue in residues])
    distances = np.linalg.norm(coordinates[:, None, :] - coordinates[None, :, :], axis=2)
    directed: dict[tuple[str, str], dict[str, Any]] = {}
    for chain1 in chain_ids:
        for chain2 in chain_ids:
            if chain1 == chain2:
                continue
            rows = chains == chain1
            cols = chains == chain2
            n0chn = int(rows.sum() + cols.sum())
            d0chn = _d0(n0chn)
            valid_matrix = rows[:, None] & cols[None, :] & (pae_array < pae_cutoff)
            valid_distance = valid_matrix & (distances < distance_cutoff)
            row_ids = np.flatnonzero(rows)
            ipsae_rows: list[float] = []
            ipsae_chn_rows: list[float] = []
            iptm_rows: list[float] = []
            n0res_rows: list[int] = []
            d0res_rows: list[float] = []
            for i in row_ids:
                valid = valid_matrix[i]
                n0res_i = int(valid.sum())
                d0res_i = _d0(n0res_i)
                n0res_rows.append(n0res_i)
                d0res_rows.append(d0res_i)
                iptm_rows.append(float(_ptm(pae_array[i, cols], d0chn).mean()))
                ipsae_chn_rows.append(
                    float(_ptm(pae_array[i, valid], d0chn).mean()) if valid.any() else 0.0
                )
                ipsae_rows.append(
                    float(_ptm(pae_array[i, valid], d0res_i).mean()) if valid.any() else 0.0
                )

            valid_row_residues = set(np.flatnonzero(valid_matrix.any(axis=1)).tolist())
            valid_col_residues = set(np.flatnonzero(valid_matrix.any(axis=0)).tolist())
            distance_rows = set(np.flatnonzero(valid_distance.any(axis=1)).tolist())
            distance_cols = set(np.flatnonzero(valid_distance.any(axis=0)).tolist())
            n0dom = len(valid_row_residues) + len(valid_col_residues)
            d0dom = _d0(n0dom)
            ipsae_dom_rows = [
                float(_ptm(pae_array[i, valid_matrix[i]], d0dom).mean())
                if valid_matrix[i].any() else 0.0
                for i in row_ids
            ]
            best = int(np.argmax(ipsae_rows))

            contact_mask = rows[:, None] & cols[None, :] & (distances <= 8.0)
            contact_pairs = int(contact_mask.sum())
            interface_indices = set(np.flatnonzero(contact_mask.any(axis=1)).tolist())
            interface_indices.update(np.flatnonzero(contact_mask.any(axis=0)).tolist())
            if contact_pairs:
                mean_plddt = float(plddt_array[sorted(interface_indices)].mean())
                x = mean_plddt * math.log10(contact_pairs)
                pdockq = 0.724 / (1.0 + math.exp(-0.052 * (x - 152.611))) + 0.018
                mean_ptm = float(_ptm(pae_array[contact_mask], 10.0).mean())
                x2 = mean_plddt * mean_ptm
                pdockq2 = 1.31 / (1.0 + math.exp(-0.075 * (x2 - 84.733))) + 0.005
            else:
                pdockq = 0.0
                pdockq2 = 0.0
            selected_pae = pae_array[rows[:, None] & cols[None, :]]
            lis_values = selected_pae[selected_pae < 12.0]
            lis = float(((12.0 - lis_values) / 12.0).mean()) if len(lis_values) else 0.0
            directed[(chain1, chain2)] = {
                "chain1": chain1,
                "chain2": chain2,
                "type": "asym",
                "ipsae": ipsae_rows[best],
                "ipsae_d0chn": max(ipsae_chn_rows),
                "ipsae_d0dom": max(ipsae_dom_rows),
                "iptm_af": -1.0 if iptm is None else float(iptm),
                "iptm_d0chn": max(iptm_rows),
                "pdockq": float(pdockq),
                "pdockq2": float(pdockq2),
                "lis": lis,
                "n0res": n0res_rows[best],
                "n0chn": n0chn,
                "n0dom": n0dom,
                "d0res": d0res_rows[best],
                "d0chn": d0chn,
                "d0dom": d0dom,
                "nres1": len(valid_row_residues),
                "nres2": len(valid_col_residues),
                "dist1": len(distance_rows),
                "dist2": len(distance_cols),
            }

    records: list[dict[str, Any]] = []
    for index, chain1 in enumerate(chain_ids):
        for chain2 in chain_ids[index + 1:]:
            forward = directed[(chain1, chain2)]
            reverse = directed[(chain2, chain1)]
            records.extend((forward, reverse))
            winners = {
                field: max(forward[field], reverse[field])
                for field in ("ipsae", "ipsae_d0chn", "ipsae_d0dom", "iptm_d0chn", "pdockq2")
            }
            ipsae_winner = forward if forward["ipsae"] >= reverse["ipsae"] else reverse
            dom_winner = forward if forward["ipsae_d0dom"] >= reverse["ipsae_d0dom"] else reverse
            records.append({
                "chain1": chain1,
                "chain2": chain2,
                "type": "max",
                **winners,
                "iptm_af": forward["iptm_af"],
                "pdockq": reverse["pdockq"],
                "lis": (forward["lis"] + reverse["lis"]) / 2.0,
                "n0res": ipsae_winner["n0res"],
                "n0chn": forward["n0chn"],
                "n0dom": dom_winner["n0dom"],
                "d0res": ipsae_winner["d0res"],
                "d0chn": forward["d0chn"],
                "d0dom": dom_winner["d0dom"],
                "nres1": max(forward["nres1"], reverse["nres2"]),
                "nres2": max(forward["nres2"], reverse["nres1"]),
                "dist1": max(forward["dist1"], reverse["dist2"]),
                "dist2": max(forward["dist2"], reverse["dist1"]),
            })
    return {
        "pae_cutoff": float(pae_cutoff),
        "distance_cutoff": float(distance_cutoff),
        "chain_pairs": records,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-pdb", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--native-pdb")
    parser.add_argument("--scores-json")
    parser.add_argument("--pae-cutoff", type=float, default=15.0)
    parser.add_argument("--distance-cutoff", type=float, default=15.0)
    args = parser.parse_args()
    output: dict[str, Any] = {}
    if args.native_pdb:
        output["dockq"] = score_dockq(args.model_pdb, args.native_pdb)
    if args.scores_json:
        scores = json.loads(Path(args.scores_json).read_text(encoding="utf-8"))
        output["ipsae"] = score_ipsae(
            scores.get("pae", scores.get("predicted_aligned_error")),
            scores["plddt"],
            args.model_pdb,
            args.pae_cutoff,
            args.distance_cutoff,
            scores.get("iptm"),
        )
    Path(args.output).write_text(
        json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

if __name__ == "__main__": main()
