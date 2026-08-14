#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0025."""

from __future__ import annotations

import hashlib
import io
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tokenize

import numpy as np

from cases import hidden_cases, invalid_cases
from model import stable_sigmoid, walk_splits


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-xgboost-source")
REFERENCE_RUNTIME = Path("/opt/reference-runtime")
REFERENCE_RUNNER = Path("/opt/reference-runner/reference_runner.py")
CANDIDATE_TOOLS = Path("/opt/candidate-tools/materialize_candidate.py")
CANDIDATE_RUNNER = Path("/opt/candidate-runner/candidate_runner.py")
INIT = Path("sklearn/ensemble/__init__.py")
MODULE = Path("sklearn/ensemble/_second_order_gradient_boosting.py")
ALLOWED = {str(INIT), str(MODULE)}
FORBIDDEN_NAMES = {
    "xgboost", "lightgbm", "catboost", "subprocess", "ctypes", "cffi",
    "socket", "requests", "urllib", "importlib", "runpy", "pickle",
    "marshal", "joblib", "cloudpickle", "dill", "exec", "eval",
    "compile", "__import__", "popen", "system", "decisiontreeregressor",
    "gradientboostingregressor", "histgradientboostingregressor",
}


def write_report(report, reward):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["reward"] = float(reward)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    REWARD.write_text(f"{float(reward):.10f}\n")


def fail(reason, report=None):
    report = {} if report is None else report
    report.update({"status": "hard_gate_failed", "reason": reason})
    write_report(report, 0.0)
    raise SystemExit(0)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ignored(relative):
    return (
        "__pycache__" in relative.parts
        or ".pytest_cache" in relative.parts
        or relative.suffix in {".pyc", ".pyo"}
    )


def manifest(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if path.is_symlink():
            result[str(relative)] = "SYMLINK"
        elif path.is_file():
            result[str(relative)] = sha256(path)
    return result


def python_tokens(path):
    output = []
    try:
        stream = tokenize.tokenize(io.BytesIO(path.read_bytes()).readline)
        for token in stream:
            if token.type not in {
                tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                tokenize.COMMENT, tokenize.STRING,
            }:
                output.append(token.string)
    except (OSError, SyntaxError, tokenize.TokenError):
        return []
    return output


_LEXEME = re.compile(
    r"[A-Za-z_][A-Za-z_0-9]*|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|"
    r"==|!=|<=|>=|&&|\|\||[-+*/%<>=!&|^~]+|[()[\]{},.:;]"
)


def generic_tokens(path):
    try:
        return _LEXEME.findall(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return []


def donor_fragments():
    fragments = {64: set(), 96: set()}
    relevant = [
        DONOR / "src/tree/updater_colmaker.cc",
        DONOR / "src/tree/param.h",
        DONOR / "src/objective/squared_error_obj.h",
        DONOR / "src/objective/logistic_obj.h",
    ]
    for path in relevant:
        tokens = generic_tokens(path)
        for size in fragments:
            fragments[size].update(
                tuple(tokens[index:index + size])
                for index in range(max(0, len(tokens) - size + 1))
            )
    return fragments


def trusted_extensions():
    installed = Path(
        importlib.metadata.distribution("scikit-learn").locate_file("sklearn")
    ).resolve()
    result = {}
    for path in installed.rglob("*.so"):
        relative = Path("sklearn") / path.relative_to(installed)
        result[str(relative)] = sha256(path)
    return result


def source_policy():
    candidate = manifest(TESTBED)
    pristine = manifest(PRISTINE)
    extensions = trusted_extensions()
    bad_extensions = []
    for name in sorted(set(candidate) - set(pristine)):
        if name.endswith(".so"):
            if extensions.get(name) != candidate[name]:
                bad_extensions.append(name)
            else:
                candidate.pop(name)
    if bad_extensions:
        return False, f"untrusted compiled extension: {bad_extensions[:3]}"
    missing = sorted(set(pristine) - set(candidate))
    changed = sorted(
        name for name in set(pristine) & set(candidate)
        if pristine[name] != candidate[name]
    )
    added = sorted(set(candidate) - set(pristine))
    if missing:
        return False, f"locked host files removed: {missing[:4]}"
    if changed != [str(INIT)]:
        return False, f"unexpected changed files: {changed[:4]}"
    if added != [str(MODULE)]:
        return False, f"unexpected added files: {added[:4]}"
    total_bytes = 0
    for relative in (INIT, MODULE):
        path = TESTBED / relative
        if not path.is_file() or path.is_symlink():
            return False, f"missing regular candidate file: {relative}"
        if path.stat().st_size > 120_000:
            return False, f"candidate file exceeds 120000 bytes: {relative}"
        total_bytes += path.stat().st_size
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (UnicodeDecodeError, SyntaxError) as error:
            return False, f"invalid candidate Python: {type(error).__name__}"
        lowered = {token.lower() for token in python_tokens(path)}
        prohibited_names = FORBIDDEN_NAMES
        if relative == INIT:
            # The pristine ensemble export file legitimately names existing
            # sklearn gradient-boosting estimators.
            prohibited_names = prohibited_names - {
                "decisiontreeregressor",
                "gradientboostingregressor",
                "histgradientboostingregressor",
            }
        prohibited = sorted(lowered & prohibited_names)
        if prohibited:
            return False, f"forbidden dependency or primitive: {prohibited[:3]}"
    init_tokens = python_tokens(TESTBED / INIT)
    if (
        "SecondOrderGradientBoosting" not in init_tokens
        or "_second_order_gradient_boosting" not in init_tokens
    ):
        return False, "sklearn.ensemble does not export the requested estimator"
    candidate_tokens = generic_tokens(TESTBED / MODULE)
    fragments = donor_fragments()
    for size in (96, 64):
        if any(
            tuple(candidate_tokens[index:index + size]) in fragments[size]
            for index in range(max(0, len(candidate_tokens) - size + 1))
        ):
            return False, f"normalized donor fragment detected ({size} tokens)"
    return True, {
        "changed": changed,
        "added": added,
        "trusted_extensions": len(extensions),
        "candidate_bytes": total_bytes,
        "module_sha256": sha256(TESTBED / MODULE),
        "donor_fragment_scan": "pass",
    }


def run_file(command, input_path, output_path, *, env, cwd, uid=None, timeout=300):
    def demote():
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)

    completed = subprocess.run(
        command + [str(input_path), str(output_path)],
        cwd=str(cwd), env=env, capture_output=True, text=True,
        timeout=timeout, check=False,
        preexec_fn=demote if uid is not None else None,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"runner failed ({completed.returncode}): {completed.stderr[-2000:]}"
        )
    if not output_path.is_file() or output_path.stat().st_size > 20_000_000:
        raise RuntimeError("runner output missing or oversized")
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError("runner returned invalid JSON") from error


def reference_environment():
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONPATH": f"{REFERENCE_RUNTIME}:/opt/reference-runner",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
    }


def candidate_environment():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/candidate-runtime:/opt/candidate-runner",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "HOME": "/nonexistent",
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "ALL_PROXY": "",
        "NO_PROXY": "*",
    }


def array(value, shape=None):
    result = np.asarray(value, dtype=float)
    if shape is not None and result.shape != shape:
        raise ValueError(f"expected shape {shape}, got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError("non-finite numeric output")
    return result


def close(left, right, *, atol, rtol):
    return np.allclose(left, right, atol=atol, rtol=rtol)


def tree_prediction(tree, X):
    values = []
    for row in X:
        node = tree
        while "leaf" not in node:
            value = row[int(node["feature"])]
            if np.isnan(value):
                node = node[str(node["missing"])]
            elif value < float(node["threshold"]):
                node = node["left"]
            else:
                node = node["right"]
        values.append(float(node["leaf"]))
    return np.asarray(values, dtype=np.float32)


def compare_tree(expected, observed, reasons, metrics, path="root"):
    if not isinstance(observed, dict):
        reasons.append(f"tree_schema:{path}")
        return
    expected_leaf = "leaf" in expected
    observed_leaf = "leaf" in observed
    if expected_leaf != observed_leaf:
        reasons.append(f"tree_kind:{path}")
        return
    for key in ("node_id", "depth"):
        if int(observed.get(key, -999)) != int(expected[key]):
            reasons.append(f"tree_{key}:{path}")
    try:
        expected_cover = float(expected["cover"])
        cover = float(observed["cover"])
        if not math.isfinite(cover):
            raise ValueError
        metrics["tree_numeric_max_abs"] = max(
            metrics.get("tree_numeric_max_abs", 0.0),
            abs(cover - expected_cover),
        )
        if not math.isclose(cover, expected_cover, abs_tol=2e-6, rel_tol=3e-7):
            reasons.append(f"tree_cover:{path}")
    except (KeyError, TypeError, ValueError):
        reasons.append(f"tree_cover_schema:{path}")
        return
    if expected_leaf:
        try:
            leaf = float(observed["leaf"])
            if not math.isfinite(leaf):
                raise ValueError
            metrics["tree_numeric_max_abs"] = max(
                metrics.get("tree_numeric_max_abs", 0.0),
                abs(leaf - float(expected["leaf"])),
            )
            if not math.isclose(
                leaf, float(expected["leaf"]), abs_tol=2e-7, rel_tol=2e-7
            ):
                reasons.append(f"tree_leaf:{path}")
        except (KeyError, TypeError, ValueError):
            reasons.append(f"tree_leaf_schema:{path}")
        return
    for key in ("feature", "missing"):
        if observed.get(key) != expected[key]:
            reasons.append(f"tree_{key}:{path}")
    for key, atol, rtol in (
        ("threshold", 2e-7, 2e-7),
        # The locked JSON dumper emits decimalized float gains while the
        # candidate returns the originating float32 value. Small gains need a
        # few ulps of absolute slack; topology, leaves and margins stay tight.
        ("gain", 5e-6, 5e-6),
    ):
        try:
            value = float(observed[key])
            expected_value = float(expected[key])
            if not math.isfinite(value):
                raise ValueError
            metrics["tree_numeric_max_abs"] = max(
                metrics.get("tree_numeric_max_abs", 0.0),
                abs(value - expected_value),
            )
            if not math.isclose(value, expected_value, abs_tol=atol, rel_tol=rtol):
                reasons.append(f"tree_{key}:{path}")
        except (KeyError, TypeError, ValueError):
            reasons.append(f"tree_{key}_schema:{path}")
    if observed.get("missing") not in {"left", "right"}:
        reasons.append(f"tree_missing_schema:{path}")
        return
    for branch in ("left", "right"):
        if branch not in observed:
            reasons.append(f"tree_child:{path}:{branch}")
        else:
            compare_tree(
                expected[branch], observed[branch], reasons, metrics,
                path + ("L" if branch == "left" else "R"),
            )


def validate_candidate_invariants(case, observed, reasons, metrics):
    X = np.asarray(case.get("test_X", case["X"]), dtype=float)
    reconstructed = np.zeros(X.shape[0], dtype=np.float32)
    depth = 0
    gains = np.zeros(X.shape[1], dtype=float)
    for tree in observed["trees"]:
        reconstructed = np.asarray(
            reconstructed + tree_prediction(tree, X), dtype=np.float32
        )
        for split in walk_splits(tree):
            depth = max(depth, int(split["depth"]))
            gains[int(split["feature"])] += float(split["gain"])
            left_cover = float(split["left"]["cover"])
            right_cover = float(split["right"]["cover"])
            if not math.isclose(
                float(split["cover"]), left_cover + right_cover,
                abs_tol=3e-5, rel_tol=3e-6,
            ):
                reasons.append("cover_additivity_invariant")
    margin = array(observed["margin"], (X.shape[0],))
    metrics["margin_reconstruction_max_abs"] = float(
        np.max(np.abs(margin - reconstructed))
    )
    if not close(margin, reconstructed, atol=2e-7, rtol=2e-7):
        reasons.append("tree_margin_reconstruction_invariant")
    observed_gains = array(observed["feature_gains"], (X.shape[1],))
    metrics["feature_gain_reconstruction_max_abs"] = float(
        np.max(np.abs(observed_gains - gains))
    )
    if not close(observed_gains, gains, atol=2e-6, rtol=3e-7):
        reasons.append("feature_gain_reconstruction_invariant")
    losses = array(
        observed["training_loss"],
        (int(case["params"]["n_estimators"]) + 1,),
    )
    maximum_increase = float(np.max(np.diff(losses)))
    metrics["maximum_training_loss_increase"] = maximum_increase
    if maximum_increase > 2e-9:
        reasons.append("training_loss_monotonic_invariant")
    if depth > int(case["params"]["max_depth"]):
        reasons.append("maximum_depth_invariant")
    if case["params"]["objective"] == "logistic":
        probability = array(observed["probability"], (X.shape[0], 2))
        expected_positive = stable_sigmoid(margin)
        if not close(
            probability[:, 1], expected_positive, atol=2e-7, rtol=2e-7
        ) or not close(
            probability.sum(axis=1), np.ones(X.shape[0]), atol=2e-12, rtol=0
        ):
            reasons.append("probability_invariant")


def compare_case(case, expected, observed):
    reasons = []
    metrics = {}
    if "error_type" in observed:
        return ["candidate_error:" + str(observed["error_type"])], metrics
    if observed.get("name") != expected.get("name"):
        reasons.append("case_name")
    if int(observed.get("n_features_in", -1)) != len(case["X"][0]):
        reasons.append("n_features_in")
    expected_trees = expected["trees"]
    observed_trees = observed.get("trees")
    if not isinstance(observed_trees, list) or len(observed_trees) != len(expected_trees):
        reasons.append("tree_count")
    else:
        for index, (left, right) in enumerate(zip(expected_trees, observed_trees)):
            compare_tree(left, right, reasons, metrics, f"t{index}")
    n_test = len(case.get("test_X", case["X"]))
    n_features = len(case["X"][0])
    comparisons = (
        ("margin", (n_test,), 2e-7, 2e-7),
        ("prediction", (n_test,), 2e-7, 2e-7),
        ("feature_gains", (n_features,), 2e-5, 5e-7),
        ("training_loss", (int(case["params"]["n_estimators"]) + 1,), 2e-8, 2e-8),
    )
    for key, shape, atol, rtol in comparisons:
        try:
            expected_value = array(expected[key], shape)
            value = array(observed[key], shape)
            error = float(np.max(np.abs(value - expected_value)))
            metrics[f"{key}_max_abs"] = error
            if not close(value, expected_value, atol=atol, rtol=rtol):
                reasons.append(key)
        except (KeyError, TypeError, ValueError) as error:
            reasons.append(f"{key}_schema:{type(error).__name__}")
    if case["params"]["objective"] == "logistic":
        try:
            expected_probability = array(expected["probability"], (n_test, 2))
            probability = array(observed["probability"], (n_test, 2))
            metrics["probability_max_abs"] = float(
                np.max(np.abs(probability - expected_probability))
            )
            if not close(probability, expected_probability, atol=2e-7, rtol=2e-7):
                reasons.append("probability")
        except (KeyError, TypeError, ValueError) as error:
            reasons.append(f"probability_schema:{type(error).__name__}")
    if not reasons:
        try:
            validate_candidate_invariants(case, observed, reasons, metrics)
        except (KeyError, TypeError, ValueError, IndexError) as error:
            reasons.append(f"invariant_schema:{type(error).__name__}")
    return sorted(set(reasons)), metrics


def normalized_model(case_result):
    """Drop only floating diagnostics before exact permutation comparison."""
    return case_result["trees"]


def leaves(tree):
    if "leaf" in tree:
        yield float(tree["leaf"])
        return
    yield from leaves(tree["left"])
    yield from leaves(tree["right"])


def reference_self_check(reference):
    cases = reference.get("cases", [])
    if reference.get("version") != "3.5.0-dev" or len(cases) != 15:
        return False, "reference version or case count"
    by_name = {case["name"]: case for case in cases}
    for case in cases:
        loss = np.asarray(case["training_loss"], dtype=float)
        if not np.all(np.isfinite(loss)) or np.max(np.diff(loss)) > 2e-9:
            return False, f"reference loss invariant: {case['name']}"
    if by_name["missing_default_right"]["trees"][0]["missing"] != "right":
        return False, "reference missing-right fixture"
    if by_name["missing_default_left"]["trees"][0]["missing"] != "left":
        return False, "reference missing-left fixture"
    if by_name["feature_split_tie"]["trees"][0]["feature"] != 0:
        return False, "reference tie fixture"
    if max(abs(value) for value in by_name["learning_rate_zero"]["margin"]) != 0.0:
        return False, "reference zero-rate fixture"
    if not any(
        value == 0.0
        for tree in by_name["l1_zero_leaf"]["trees"]
        for value in leaves(tree)
    ):
        return False, "reference L1 zero-leaf fixture"
    first = by_name["row_permutation_base"]
    second = by_name["row_permutation_shuffled"]
    if normalized_model(first) != normalized_model(second) or first["margin"] != second["margin"]:
        return False, "reference row-permutation fixture"
    return True, "pass"


def cross_case_gate(candidate):
    by_name = {case["name"]: case for case in candidate}
    required = {
        "learning_rate_zero", "feature_split_tie", "l1_zero_leaf",
        "missing_default_right", "missing_default_left",
        "row_permutation_base", "row_permutation_shuffled",
    }
    if not required <= set(by_name) or any("error_type" in by_name[name] for name in required):
        return False, "missing cross-case result"
    if max(abs(float(value)) for value in by_name["learning_rate_zero"]["margin"]) > 1e-12:
        return False, "learning_rate=0 changed margins"
    if by_name["feature_split_tie"]["trees"][0].get("feature") != 0:
        return False, "feature tie did not choose feature 0"
    if by_name["missing_default_right"]["trees"][0].get("missing") != "right":
        return False, "missing-right route"
    if by_name["missing_default_left"]["trees"][0].get("missing") != "left":
        return False, "missing-left route"
    if not any(
        value == 0.0
        for tree in by_name["l1_zero_leaf"]["trees"]
        for value in leaves(tree)
    ):
        return False, "L1 produced no exact zero leaf"
    first = by_name["row_permutation_base"]
    second = by_name["row_permutation_shuffled"]
    if normalized_model(first) != normalized_model(second):
        return False, "row permutation changed normalized trees"
    if not close(
        array(first["margin"]), array(second["margin"]), atol=1e-12, rtol=0
    ):
        return False, "row permutation changed aligned predictions"
    return True, "pass"


def run_host_regression(env, cwd):
    code = r'''
import importlib.util
import numpy as np
from sklearn.base import clone
from sklearn.ensemble import (
    GradientBoostingRegressor, RandomForestRegressor,
    SecondOrderGradientBoosting,
)
assert importlib.util.find_spec("xgboost") is None
est = SecondOrderGradientBoosting(n_estimators=2, max_depth=1)
assert clone(est).get_params()["n_estimators"] == 2
X = np.array([[0.0], [1.0], [2.0], [3.0]])
y = np.array([0.0, 0.0, 1.0, 1.0])
for model in (GradientBoostingRegressor(n_estimators=2, max_depth=1),
              RandomForestRegressor(n_estimators=2, max_depth=1, random_state=0)):
    prediction = model.fit(X, y).predict(X)
    assert prediction.shape == (4,) and np.all(np.isfinite(prediction))
'''
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=str(cwd), env=env,
        capture_output=True, text=True, timeout=120, check=False,
        preexec_fn=lambda: (os.setgroups([]), os.setgid(10001), os.setuid(10001)),
    )
    if completed.returncode != 0:
        return False, completed.stderr[-1200:]
    return True, "pass"


def make_read_only(root):
    for path in sorted(root.rglob("*"), reverse=True):
        try:
            path.chmod(0o555 if path.is_dir() else 0o444)
        except FileNotFoundError:
            pass
    root.chmod(0o555)


def main():
    report = {
        "task": "ALGOBRIDGE-0025",
        "reference": "locked scikit-learn arrays to XGBoost a3e3df59 exact CPU",
        "total": 15,
        "hard_gates": {},
    }
    lock = json.loads(Path("/tests/source-lock.json").read_text())
    expected_lib = lock["reference_runtime"]["libxgboost_sha256"]
    runtime_lib = REFERENCE_RUNTIME / "xgboost/lib/libxgboost.so"
    if not runtime_lib.is_file() or sha256(runtime_lib) != expected_lib:
        fail("locked reference runtime integrity failed", report)
    report["hard_gates"]["locked_reference"] = "pass"

    policy_ok, policy_detail = source_policy()
    if not policy_ok:
        fail("source policy failed: " + str(policy_detail), report)
    report["hard_gates"]["source_policy"] = policy_detail

    work = Path("/tmp/verifier-root-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(mode=0o700)
    valid = hidden_cases()
    reference_input = work / "reference-input.json"
    reference_output = work / "reference-output.json"
    reference_input.write_text(json.dumps(valid, allow_nan=True), encoding="utf-8")
    try:
        reference = run_file(
            [sys.executable, str(REFERENCE_RUNNER)],
            reference_input, reference_output,
            env=reference_environment(), cwd=work, timeout=300,
        )
    except Exception as error:
        fail("reference execution failed: " + str(error), report)
    reference_ok, reference_detail = reference_self_check(reference)
    if not reference_ok:
        fail("reference self-check failed: " + reference_detail, report)
    report["hard_gates"]["reference_self_check"] = "pass"

    materialized = subprocess.run(
        [sys.executable, str(CANDIDATE_TOOLS), "--testbed", str(TESTBED),
         "--output", "/opt/candidate-runtime"],
        cwd="/tmp", capture_output=True, text=True, timeout=120, check=False,
    )
    if materialized.returncode != 0:
        fail("candidate materialization failed: " + materialized.stderr[-1000:], report)
    make_read_only(Path("/opt/candidate-runtime"))
    make_read_only(TESTBED)

    # Delete every private reference asset before the untrusted process starts.
    for path in (
        REFERENCE_RUNTIME, DONOR, Path("/opt/reference-runner"),
        Path("/opt/pristine-host"), Path("/opt/wheels"),
        Path("/opt/candidate-tools"),
    ):
        shutil.rmtree(path, ignore_errors=True)
    reference_input.unlink(missing_ok=True)
    reference_output.unlink(missing_ok=True)
    if any(path.exists() for path in (REFERENCE_RUNTIME, DONOR, Path("/opt/reference-runner"))):
        fail("reference removal failed", report)
    report["hard_gates"]["reference_removed_before_candidate"] = "pass"

    candidate_io = Path("/tmp/candidate-io")
    candidate_work = Path("/tmp/candidate-work")
    shutil.rmtree(candidate_io, ignore_errors=True)
    shutil.rmtree(candidate_work, ignore_errors=True)
    candidate_io.mkdir(mode=0o700)
    candidate_work.mkdir(mode=0o555)
    os.chown(candidate_io, 10001, 10001)
    os.chown(candidate_work, 0, 0)
    valid_input = candidate_io / "valid-input.json"
    valid_output = candidate_io / "valid-output.json"
    invalid_input = candidate_io / "invalid-input.json"
    invalid_output = candidate_io / "invalid-output.json"
    valid_input.write_text(json.dumps(valid, allow_nan=True), encoding="utf-8")
    invalid_input.write_text(
        json.dumps(invalid_cases(), allow_nan=True), encoding="utf-8"
    )
    os.chown(valid_input, 10001, 10001)
    os.chown(invalid_input, 10001, 10001)
    env = candidate_environment()
    try:
        candidate_payload = run_file(
            [sys.executable, str(CANDIDATE_RUNNER)], valid_input, valid_output,
            env=env, cwd=candidate_work, uid=10001, timeout=300,
        )
        invalid_payload = run_file(
            [sys.executable, str(CANDIDATE_RUNNER)], invalid_input, invalid_output,
            env=env, cwd=candidate_work, uid=10001, timeout=180,
        )
    except Exception as error:
        fail("candidate execution failed: " + str(error), report)

    invalid_results = invalid_payload.get("cases", [])
    expected_invalid = invalid_cases()
    if (
        len(invalid_results) != len(expected_invalid)
        or any(item.get("error_type") != "ValueError" for item in invalid_results)
    ):
        fail("invalid-input rejection gate failed", report)
    report["hard_gates"]["invalid_input_rejection"] = "pass"

    regression_ok, regression_detail = run_host_regression(env, candidate_work)
    if not regression_ok:
        fail("host regression failed: " + regression_detail, report)
    report["hard_gates"]["host_regression"] = "pass"

    observed_cases = candidate_payload.get("cases", [])
    if len(observed_cases) != 15:
        fail("candidate returned the wrong case count", report)
    cross_ok, cross_detail = cross_case_gate(observed_cases)
    if not cross_ok:
        fail("cross-case invariant failed: " + cross_detail, report)
    report["hard_gates"]["determinism_missing_l1_zero_rate"] = "pass"

    expected_cases = reference["cases"]
    results = []
    passed = 0
    for case, expected, observed in zip(valid, expected_cases, observed_cases):
        reasons, metrics = compare_case(case, expected, observed)
        ok = not reasons
        passed += int(ok)
        results.append({
            "name": case["name"],
            "passed": ok,
            "reasons": reasons,
            "metrics": metrics,
        })
    reward = passed / 15.0
    report.update({
        "status": "completed",
        "passed": passed,
        "cases": results,
    })
    write_report(report, reward)


if __name__ == "__main__":
    main()
