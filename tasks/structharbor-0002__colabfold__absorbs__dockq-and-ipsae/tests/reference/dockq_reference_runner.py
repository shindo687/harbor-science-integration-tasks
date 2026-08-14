#!/usr/bin/env python3
"""Execute unmodified locked DockQ functions and emit JSON-safe metrics."""
import json
import sys

from DockQ.DockQ import load_PDB, run_on_all_native_interfaces


model_path, native_path, output_path = sys.argv[1:4]
model = load_PDB(model_path)
native = load_PDB(native_path)
if len(sys.argv) == 5:
    model_ids, native_ids = sys.argv[4].split(":")
    chain_map = dict(zip(native_ids, model_ids))
else:
    # The bounded task has sequence-distinct chains; discover the map exactly.
    chain_map = {}
    for native_id in native.child_dict:
        matches = [model_id for model_id in model.child_dict if model[model_id].sequence == native[native_id].sequence]
        if len(matches) != 1:
            raise RuntimeError(f"ambiguous sequence map for native chain {native_id}: {matches}")
        chain_map[native_id] = matches[0]
result, total = run_on_all_native_interfaces(model, native, chain_map=chain_map)
pair = next(iter(result.values()))
score = float(pair["DockQ"])
if score >= 0.80:
    capri = "high"
elif score >= 0.49:
    capri = "medium"
elif score >= 0.23:
    capri = "acceptable"
else:
    capri = "incorrect"
payload = {
    "DockQ": score,
    "iRMSD": float(pair["iRMSD"]),
    "LRMSD": float(pair["LRMSD"]),
    "fnat": float(pair["fnat"]),
    "CAPRI": capri,
    "native_contacts": int(pair["nat_total"]),
    "preserved_contacts": int(pair["nat_correct"]),
    # DockQ reports native -> model; the task contract is model -> native.
    "mapping": {str(v): str(k) for k, v in pair["chain_map"].items()},
}
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True)
print(json.dumps(payload, sort_keys=True))
