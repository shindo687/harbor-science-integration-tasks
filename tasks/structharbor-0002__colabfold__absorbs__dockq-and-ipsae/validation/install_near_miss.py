#!/usr/bin/env python3
"""Install a one-donor near miss while retaining the full integration shell."""

from __future__ import annotations

import pathlib
import shutil
import sys


if len(sys.argv) != 3 or sys.argv[1] not in {"dockq-only", "ipsae-only"}:
    raise SystemExit("usage: install_near_miss.py {dockq-only|ipsae-only} TESTBED")

mode = sys.argv[1]
testbed = pathlib.Path(sys.argv[2])
solution = pathlib.Path(__file__).parent.parent / "solution"
module = testbed / "colabfold/alphafold/complex_metrics.py"
shutil.copyfile(solution / "complex_metrics.py", module)

text = module.read_text(encoding="utf-8")
if mode == "dockq-only":
    start = text.index("def score_ipsae(")
    end = text.index("\ndef main() -> None:", start)
    replacement = '''def score_ipsae(
    pae, plddt, model_pdb, pae_cutoff=15.0, distance_cutoff=15.0, iptm=None,
):
    """Schema-correct placeholder: the ipSAE algorithm is intentionally absent."""
    del pae, plddt, model_pdb, iptm
    return {
        "pae_cutoff": float(pae_cutoff),
        "distance_cutoff": float(distance_cutoff),
        "chain_pairs": [],
    }

'''
else:
    start = text.index("def score_dockq(")
    end = text.index("\ndef _pdb_residues", start)
    replacement = '''def score_dockq(
    model_pdb, native_pdb, mapping=None, contact_cutoff=5.0,
    interface_cutoff=10.0,
):
    """Schema-correct placeholder: the DockQ algorithm is intentionally absent."""
    del model_pdb, native_pdb, contact_cutoff, interface_cutoff
    return {
        "fnat": 0.0, "iRMSD": 0.0, "LRMSD": 0.0, "DockQ": 0.0,
        "CAPRI": "incorrect", "native_contacts": 0,
        "preserved_contacts": 0, "mapping": {} if mapping is None else mapping,
    }

'''
module.write_text(text[:start] + replacement + text[end + 1 :], encoding="utf-8")

batch = testbed / "colabfold/batch.py"
namespace = {"__name__": "__main__", "__file__": str(solution / "patch_batch.py")}
old_argv = sys.argv
try:
    sys.argv = ["patch_batch.py", str(batch)]
    exec(compile((solution / "patch_batch.py").read_text(), "patch_batch.py", "exec"), namespace)
finally:
    sys.argv = old_argv
