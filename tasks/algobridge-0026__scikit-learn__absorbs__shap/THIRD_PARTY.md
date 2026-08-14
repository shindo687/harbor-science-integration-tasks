# Third-party material

The task ships immutable source snapshots so that both the Agent and verifier
can run without network access.

| Component | Locked revision | License | Location |
|---|---|---|---|
| scikit-learn | `e27ccf58592fcfe8c7ca87f53dde840c436093b2` | BSD-3-Clause | `environment/host-source`, `tests/reference/host-source` |
| SHAP | `df974a1966294b9c7acebb1373fd6dc5445d1d3d` | MIT | `environment/donor-source`, verifier-only reference files |

The Agent receives the algorithm-relevant SHAP source and documentation for
study. The submitted implementation must be an independent scikit-learn
implementation and may not import, execute, link, copy, or vendor SHAP.

The verifier-only SHAP wheel was built from the locked donor revision. It is
used solely to compute fresh differential reference values before the candidate
phase and is not present on the candidate import path.

