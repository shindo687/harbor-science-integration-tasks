#!/usr/bin/env python3
"""Differential Harbor grader: native candidate versus locked real TB2J."""

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
from cases import hidden_cases, invalid_cases, metamorphic_pairs, public_cases, write_case
from reference_runner import run_reference


LOG_DIR = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
EXCHANGE_TOL = 2.0e-7
MOMENT_TOL = 2.0e-8
EMIN_TOL = 2.0e-10


def _max_error(left, right, expected_shape=None) -> float:
    try:
        a = np.asarray(left, dtype=float)
        b = np.asarray(right, dtype=float)
    except Exception:
        return math.inf
    if a.shape != b.shape or (expected_shape is not None and a.shape != expected_shape):
        return math.inf
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        return math.inf
    return float(np.max(np.abs(a - b), initial=0.0))


def _compare(reference: dict, candidate: dict) -> tuple[bool, dict]:
    detail = {
        "reference_status": reference.get("status"),
        "candidate_status": candidate.get("status"),
    }
    if reference.get("status") != candidate.get("status"):
        detail["reason"] = "status mismatch"
        return False, detail
    if reference.get("status") != "ok":
        return True, detail
    nk = int(reference["kmesh"])
    exchange_error = _max_error(
        reference.get("exchange_ev"), candidate.get("exchange_ev"), (nk, 2, 2)
    )
    moment_error = _max_error(
        reference.get("moments_z"), candidate.get("moments_z"), (2,)
    )
    try:
        emin_error = abs(float(reference["integration_emin"])
                         - float(candidate["integration_emin"]))
        reversal_error = abs(float(reference["pair_reversal_max_error"])
                             - float(candidate["pair_reversal_max_error"]))
    except Exception:
        emin_error = reversal_error = math.inf
    scalar_ok = (
        candidate.get("kmesh") == reference.get("kmesh")
        and candidate.get("contour_points") == reference.get("contour_points")
        and candidate.get("r_values") == reference.get("r_values")
    )
    ok = (
        scalar_ok
        and exchange_error <= EXCHANGE_TOL
        and moment_error <= MOMENT_TOL
        and emin_error <= EMIN_TOL
        and reversal_error <= EXCHANGE_TOL
    )
    detail.update({
        "exchange_max_abs_error_ev": exchange_error,
        "moment_max_abs_error": moment_error,
        "integration_emin_error_ev": emin_error,
        "reversal_diagnostic_error_ev": reversal_error,
    })
    if not ok:
        detail["reason"] = "scientific output mismatch"
    return ok, detail


def _run(case: dict, work: Path) -> tuple[dict, dict]:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", case.get("name", "case"))
    path = work / f"{safe}.json"
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
    module = Path(os.environ.get(
        "EXCHANGE_CANDIDATE_MODULE", "/testbed/src/liechtenstein_exchange.F90"
    ))
    if not module.is_file():
        return False, ["missing src/liechtenstein_exchange.F90"]
    if module.stat().st_size > 262_144:
        return False, ["candidate module exceeds 256 KiB"]
    text = module.read_text(errors="replace")
    required = [
        r"module\s+w90_liechtenstein_exchange",
        r"subroutine\s+liechtenstein_exchange",
    ]
    forbidden = {
        "downstream name": r"\btb2j\b",
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


def _invariance_error(left: dict, right: dict) -> tuple[float, float, float]:
    return (
        _max_error(left.get("exchange_ev"), right.get("exchange_ev")),
        _max_error(left.get("moments_z"), right.get("moments_z")),
        abs(float(left.get("integration_emin", math.inf))
            - float(right.get("integration_emin", -math.inf))),
    )


def _finite_or_none(value: float):
    return float(value) if math.isfinite(value) else None


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "task": "algobridge-0021__wannier90__absorbs__tb2j",
        "reference": "locked real TB2J 0.9.19 ExchangeCL2/TBGreen/Contour",
        "tolerances": {
            "exchange_ev": EXCHANGE_TOL,
            "moments": MOMENT_TOL,
            "integration_emin_ev": EMIN_TOL,
        },
    }
    try:
        audit_ok, findings = _source_audit()
        report["source_audit"] = {"passed": audit_ok, "findings": findings}
        with tempfile.TemporaryDirectory(prefix="exchange-grader-") as tmp:
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
                passed = (
                    reference.get("status") == candidate.get("status")
                    and reference.get("status") in {"invalid_input", "spin_degenerate"}
                )
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
            for name, left_case, right_case in metamorphic_pairs():
                left_ref, left_candidate = _run(left_case, work)
                right_ref, right_candidate = _run(right_case, work)
                left_ok, _ = _compare(left_ref, left_candidate)
                right_ok, _ = _compare(right_ref, right_candidate)
                exchange_error = moment_error = emin_error = math.inf
                if left_ok and right_ok:
                    exchange_error, moment_error, emin_error = _invariance_error(
                        left_candidate, right_candidate
                    )
                passed = (
                    left_ok and right_ok
                    and exchange_error <= EXCHANGE_TOL
                    and moment_error <= MOMENT_TOL
                    and emin_error <= EMIN_TOL
                )
                meta_rows.append({
                    "name": name,
                    "passed": passed,
                    "exchange_invariance_error_ev": _finite_or_none(exchange_error),
                    "moment_invariance_error": _finite_or_none(moment_error),
                    "emin_invariance_error_ev": _finite_or_none(emin_error),
                })
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

    (LOG_DIR / "verifier_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    (LOG_DIR / "reward.txt").write_text(f"{reward:.12g}\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
