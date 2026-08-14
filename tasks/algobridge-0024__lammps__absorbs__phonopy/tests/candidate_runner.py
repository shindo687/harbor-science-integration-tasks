"""Execute candidate LAMMPS in a small unprivileged writable sandbox."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


CANDIDATE_UID = 10001
CANDIDATE_GID = 10001


def run_candidate(executable: Path, candidate_input, work_dir: Path, *, timeout=120, unprivileged=True):
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / "input.json"
    output_path = work_dir / "output.json"
    script_path = work_dir / "candidate.in"
    input_path.write_text(json.dumps(candidate_input, separators=(",", ":")) + "\n", encoding="utf-8")
    script_path.write_text(f"fit_harmonic_fc2 {input_path} {output_path}\n", encoding="utf-8")
    output_path.unlink(missing_ok=True)
    if unprivileged:
        os.chmod(work_dir, 0o777)
        os.chmod(input_path, 0o444)
        os.chmod(script_path, 0o444)
        command = [
            "setpriv",
            f"--reuid={CANDIDATE_UID}",
            f"--regid={CANDIDATE_GID}",
            "--clear-groups",
            str(executable),
            "-log",
            "none",
            "-screen",
            "none",
            "-in",
            str(script_path),
        ]
    else:
        command = [
            str(executable), "-log", "none", "-screen", "none", "-in", str(script_path)
        ]
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "PYTHONPATH": "/nonexistent",
        "LD_LIBRARY_PATH": "",
        "OMP_NUM_THREADS": "1",
    }
    process = subprocess.run(
        command,
        cwd=work_dir,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"candidate exited {process.returncode}: {process.stdout[-3000:]}")
    if not output_path.is_file():
        raise RuntimeError("candidate did not create output")
    try:
        return json.loads(output_path.read_text(encoding="utf-8")), process.stdout
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("candidate output is not valid JSON") from exc


def run_invalid(executable: Path, candidate_input, work_dir: Path):
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / "input.json"
    output_path = work_dir / "output.json"
    script_path = work_dir / "candidate.in"
    input_path.write_text(json.dumps(candidate_input, separators=(",", ":")) + "\n", encoding="utf-8")
    script_path.write_text(f"fit_harmonic_fc2 {input_path} {output_path}\n", encoding="utf-8")
    output_path.unlink(missing_ok=True)
    os.chmod(work_dir, 0o777)
    os.chmod(input_path, 0o444)
    os.chmod(script_path, 0o444)
    process = subprocess.run(
        [
            "setpriv",
            f"--reuid={CANDIDATE_UID}",
            f"--regid={CANDIDATE_GID}",
            "--clear-groups",
            str(executable),
            "-log",
            "none",
            "-screen",
            "none",
            "-in",
            str(script_path),
        ],
        cwd=work_dir,
        env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LD_LIBRARY_PATH": ""},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    return process.returncode != 0 and not output_path.exists(), process.stdout

