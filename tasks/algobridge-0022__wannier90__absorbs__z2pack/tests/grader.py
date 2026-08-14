#!/usr/bin/env python3
"""Differential Harbor grader: native candidate versus locked real Z2Pack."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import tempfile
import traceback

import numpy as np

from candidate_runner import run_candidate
from cases import hidden_cases, invalid_cases, make_case, public_cases, write_case
from reference_runner import run_reference


LOG_DIR = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
WCC_TOL = 1.0e-6
GAP_TOL = 1.0e-6


def _circle_distance(a, b):
    delta = np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))
    return np.minimum(delta % 1.0, (-delta) % 1.0)


def _wcc_error(reference, candidate) -> float:
    ref = np.asarray(reference, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    if ref.shape != cand.shape or ref.ndim != 2 or ref.shape[1] != 2:
        return math.inf
    errors = []
    for rrow, crow in zip(ref, cand):
        direct = max(_circle_distance(rrow, crow))
        swapped = max(_circle_distance(rrow, crow[::-1]))
        errors.append(min(direct, swapped))
    return float(max(errors, default=0.0))


def _compare(reference: dict, candidate: dict) -> tuple[bool, dict]:
    detail = {"reference_status": reference.get("status"),
              "candidate_status": candidate.get("status")}
    if reference.get("status") != candidate.get("status"):
        detail["reason"] = "status mismatch"
        return False, detail
    if reference.get("status") != "ok":
        return True, detail
    try:
        wcc_error = _wcc_error(reference["wcc"], candidate["wcc"])
        gap_path_error = float(np.max(_circle_distance(
            reference["largest_gap_path"], candidate["largest_gap_path"]
        )))
        gap_size_error = float(np.max(np.abs(
            np.asarray(reference["largest_gap_size"], dtype=float)
            - np.asarray(candidate["largest_gap_size"], dtype=float)
        )))
        line_error = float(np.max(np.abs(
            np.asarray(reference["line_positions"], dtype=float)
            - np.asarray(candidate["line_positions"], dtype=float)
        )))
        min_gap_error = abs(float(reference["min_direct_gap"])
                            - float(candidate["min_direct_gap"]))
        min_gap_limit = 1e-8 * max(1.0, abs(float(reference["min_direct_gap"])))
        scalar_ok = (
            candidate.get("z2") == reference.get("z2")
            and candidate.get("num_lines") == reference.get("num_lines")
            and candidate.get("loop_points") == reference.get("loop_points")
            and candidate.get("converged") is True
        )
        ok = (scalar_ok and wcc_error <= WCC_TOL and gap_path_error <= GAP_TOL
              and gap_size_error <= GAP_TOL and line_error <= 1e-12
              and min_gap_error <= min_gap_limit)
        detail.update({
            "z2_reference": reference.get("z2"),
            "z2_candidate": candidate.get("z2"),
            "wcc_max_circle_error": wcc_error,
            "gap_path_max_circle_error": gap_path_error,
            "gap_size_max_error": gap_size_error,
            "line_position_max_error": line_error,
            "min_gap_error": min_gap_error,
        })
        if not ok:
            detail["reason"] = "scientific output mismatch"
        return ok, detail
    except Exception as exc:
        detail["reason"] = f"malformed candidate output: {exc}"
        return False, detail


def _run(case: dict, work: Path) -> tuple[dict, dict]:
    path = work / (re.sub(r"[^A-Za-z0-9_.-]", "_", case.get("name", "case")) + ".json")
    write_case(path, case)
    try:
        reference = run_reference(path)
    except Exception as exc:
        reference = {"status": "invalid_input", "error": str(exc)}
    try:
        candidate = run_candidate(path)
    except Exception as exc:
        candidate = {"status": "invalid_input", "error": str(exc)}
    return reference, candidate


def _source_audit() -> tuple[bool, list[str]]:
    module = Path(os.environ.get("Z2_CANDIDATE_MODULE", "/testbed/src/z2_wilson_loop.F90"))
    if not module.is_file():
        return False, ["missing src/z2_wilson_loop.F90"]
    if module.stat().st_size > 262_144:
        return False, ["candidate module exceeds 256 KiB"]
    text = module.read_text(errors="replace")
    required = [r"module\s+w90_z2_wilson_loop", r"subroutine\s+z2_wilson_loop"]
    forbidden = {
        "downstream name": r"z2pack",
        "process execution": r"execute_command_line|\bcall\s+system\b|\bpopen\b|\bfork\b",
        "foreign-function escape": r"iso_c_binding|bind\s*\(\s*c|\bdlopen\b",
        "absolute/include escape": r"#\s*include|\binclude\s*['\"]\s*/|/tests|/opt/",
        "network/tool escape": r"\bcurl\b|\bwget\b|\bsocket\b|\bpython[0-9.]*\b",
    }
    findings = []
    for pattern in required:
        if not re.search(pattern, text, flags=re.IGNORECASE):
            findings.append(f"missing required interface: {pattern}")
    for label, pattern in forbidden.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            findings.append(f"forbidden {label}")
    return not findings, findings


def _metamorphic_pairs() -> list[tuple[str, dict, dict]]:
    return [
        (
            "constant_unitary_basis",
            make_case("meta_gauge_base", mass=-1.3, num_lines=17, loop_points=30),
            make_case("meta_gauge_rotated", mass=-1.3, gauge_seed=2291,
                      num_lines=17, loop_points=30),
        ),
        (
            "identity_dispersion_and_energy_scale",
            make_case("meta_scale_base", mass=1.7, a=0.7, num_lines=19,
                      loop_points=32),
            make_case("meta_scale_shifted", mass=1.7, a=0.7, c=0.8, d=0.17,
                      energy_scale=0.03, gap_tolerance=1e-10, num_lines=19,
                      loop_points=32),
        ),
    ]


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "task": "algobridge-0022__wannier90__absorbs__z2pack",
        "reference": "locked real Z2Pack v2.2.0 hm.System/surface.run/invariant.z2",
        "tolerances": {"wcc_circle": WCC_TOL, "largest_gap": GAP_TOL},
    }
    try:
        audit_ok, findings = _source_audit()
        report["source_audit"] = {"passed": audit_ok, "findings": findings}
        with tempfile.TemporaryDirectory(prefix="z2-grader-") as tmp:
            work = Path(tmp)
            sections = {}
            for section_name, case_list in (
                ("public", public_cases()),
                ("hidden", hidden_cases()),
            ):
                rows = []
                for case in case_list:
                    reference, candidate = _run(case, work)
                    passed, detail = _compare(reference, candidate)
                    rows.append({"name": case["name"], "passed": passed, **detail})
                sections[section_name] = {
                    "passed": sum(row["passed"] for row in rows),
                    "total": len(rows),
                    "cases": rows,
                }

            invalid_rows = []
            for name, case in invalid_cases():
                reference, candidate = _run(case, work)
                passed = (reference.get("status") == candidate.get("status")
                          and reference.get("status") in {"invalid_input", "gap_closed"})
                invalid_rows.append({
                    "name": name,
                    "passed": passed,
                    "reference_status": reference.get("status"),
                    "candidate_status": candidate.get("status"),
                })
            sections["invalid"] = {
                "passed": sum(row["passed"] for row in invalid_rows),
                "total": len(invalid_rows),
                "cases": invalid_rows,
            }

            meta_rows = []
            for name, left_case, right_case in _metamorphic_pairs():
                left_ref, left_cand = _run(left_case, work)
                right_ref, right_cand = _run(right_case, work)
                left_ok, _ = _compare(left_ref, left_cand)
                right_ok, _ = _compare(right_ref, right_cand)
                invariant_ok = False
                if left_ok and right_ok:
                    invariant_ok = (
                        left_cand["z2"] == right_cand["z2"]
                        and _wcc_error(left_cand["wcc"], right_cand["wcc"]) <= WCC_TOL
                    )
                meta_rows.append({"name": name, "passed": invariant_ok})
            sections["metamorphic"] = {
                "passed": sum(row["passed"] for row in meta_rows),
                "total": len(meta_rows),
                "cases": meta_rows,
            }
            report.update(sections)

        hidden_passed = report["hidden"]["passed"] if audit_ok else 0
        reward = hidden_passed / report["hidden"]["total"]
        report["reward"] = reward
    except Exception as exc:
        report["fatal_error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        reward = 0.0

    (LOG_DIR / "verifier_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (LOG_DIR / "reward.txt").write_text(f"{reward:.12g}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
