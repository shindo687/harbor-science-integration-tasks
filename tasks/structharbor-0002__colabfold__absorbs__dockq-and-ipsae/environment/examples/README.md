# Public examples

Each numbered directory contains `model.pdb`, `native.pdb`, ColabFold-style
`scores.json`, and an `expected.json` produced with the two locked original
donors. The examples exercise identity, interface displacement, rigid-body
motion, sequence-based chain mapping, asymmetric PAE, and non-default cutoffs.

Run:

```bash
python3 /examples/verify_examples.py \
  /testbed/colabfold/alphafold/complex_metrics.py
```

