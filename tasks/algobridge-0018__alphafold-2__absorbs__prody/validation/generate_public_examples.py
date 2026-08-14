#!/usr/bin/env python3
"""Generate five public fixtures from the locked reference pipeline."""

from __future__ import annotations

import json
from pathlib import Path
import sys


sys.path.insert(0, "/repo/tests")
from cases import case, curve, helix  # noqa: E402
from reference_runner import run_one  # noqa: E402
from alphafold.common import protein as af_protein  # noqa: E402


OUTPUT = Path("/output")


def public_cases():
    square_pyramid = [
        [0, 0, 0], [5, 0, 0], [5, 5, 0], [0, 5, 0], [2.5, 2.5, 4.0]
    ]
    irregular = [
        [0, 0, 0], [4.3, 0.2, 0.1], [1.1, 4.6, 0.5],
        [0.4, 1.2, 4.8], [4.2, 4.0, 3.7], [7.5, 2.2, 2.0],
    ]
    plddt = [95, 52, 83, 68, 91, 44, 76, 88, 63]
    chains = ["A"] * 4 + ["B"] * 4
    return [
        case("public_gnm_square_pyramid", square_pyramid, model="gnm",
             cutoff=6.0, gamma=1.1, n_modes=4),
        case("public_anm_irregular", irregular, model="anm", cutoff=12.0,
             gamma=1.0, n_modes=6),
        case("public_gnm_plddt", curve(9), model="gnm", cutoff=7.5,
             gamma=1.0, plddt_threshold=60.0, n_modes=4,
             pdb_options={"plddt": plddt}),
        case("public_anm_chain_selection", helix(8), model="anm", cutoff=15.0,
             gamma=0.8, chain_indices=[1], n_modes=5,
             pdb_options={"chains": chains}),
        case("public_gnm_mmcif", helix(7), format="mmcif", model="gnm",
             cutoff=8.0, gamma=1.4, n_modes=5),
    ]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(public_cases(), start=1):
        if item["format"] == "mmcif":
            parsed = af_protein.from_pdb_string(item["structure"])
            item["structure"] = af_protein.to_mmcif(
                parsed, file_id="PUBLIC", model_type="Monomer"
            )
        expected = run_one(item)["result"]
        path = OUTPUT / f"{index:02d}-{item['name']}.json"
        path.write_text(
            json.dumps({"input": item, "expected": expected}, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()

