"""Check the authored fixtures, not arbitrary agent-generated patches.

Runs local Python in subprocesses with a timeout. This is process isolation,
NOT a security sandbox; use a disposable container for untrusted code.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from build_dataset import ROOT, make_records


def check(source, oracle, check_name):
    # Fixtures import only the standard library. A fresh process per check
    # prevents state carryover between variants or test stages.
    script = "import types\nm = types.ModuleType('subject')\n"
    script += "exec(compile(" + repr(source) + ", 'module.py', 'exec'), m.__dict__)\n"
    script += oracle["setup"] + "\n" + oracle[check_name]
    with tempfile.TemporaryDirectory(prefix="review-fixture-") as directory:
        result = subprocess.run([sys.executable, "-I", "-c", script],
                                cwd=directory, capture_output=True, text=True, timeout=5)
    return result.returncode == 0, result.stderr


def main():
    expected_inputs, expected_labels = make_records()
    inputs = [json.loads(s) for s in (ROOT / "data/inputs.jsonl").read_text().splitlines()]
    labels = [json.loads(s) for s in (ROOT / "data/labels.jsonl").read_text().splitlines()]
    if inputs != expected_inputs or labels != expected_labels:
        raise ValueError("Data differs from builder; regenerate or version intentional changes")
    inputs_by_id = {r["case_id"]: r for r in inputs}
    checks = 0
    for label in labels:
        row = inputs_by_id[label["case_id"]]
        oracle = label["oracle"]
        for revision, source in (("base", row["base_files"]["module.py"]),
                                 ("head", row["head_files"]["module.py"]),
                                 ("reference", label["reference_head_files"]["module.py"])):
            compile(source, "module.py", "exec")
            for check_name in ("regression", "trigger"):
                passed, error = check(source, oracle, check_name)
                should_pass = not (revision == "head" and label["variant"] == "defect"
                                   and check_name == "trigger")
                if passed != should_pass:
                    raise AssertionError(f"{label['case_id']} {revision}/{check_name}: {error}")
                if not passed and not any(e in error for e in ("AssertionError", "ZeroDivisionError")):
                    raise AssertionError(f"Unexpected failure rather than intended defect: {error}")
                checks += 1
        for issue in label["issues"]:
            if not (1 <= issue["line_start"] <= len(row["head_files"]["module.py"].splitlines())):
                raise ValueError("Invalid gold location")
    print(json.dumps({"cases": len(inputs), "paired_seeds": len(labels) // 2,
                      "revision_checks": checks, "status": "passed",
                      "agent_evaluated": False}, indent=2))


if __name__ == "__main__":
    main()
