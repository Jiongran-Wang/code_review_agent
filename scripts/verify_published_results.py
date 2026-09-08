"""Recompute published development scores without model or GitHub API calls."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.adjudicate import report


def read_json(path):
    return json.loads(path.read_text())


def check_hashes(directory, hashes):
    for name, expected in hashes.items():
        path = directory / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Published provenance mismatch: {path.relative_to(ROOT)}")


def main():
    # Published mapping files deliberately contain portable root-relative paths.
    os.chdir(ROOT)
    run = ROOT / "evaluation/published/full-comparison-v3"
    publication = read_json(run / "publication-manifest.json")
    check_hashes(run, publication["published_file_sha256"])
    freeze = read_json(ROOT / "evaluation/comparison-v3-freeze.json")
    # Historical metrics used the original Chinese prompts. Active skills are
    # now English, so verify the archived originals against the unchanged freeze.
    original_skills = read_json(run / "original-skills.json")
    skill_hashes = {name: sha for name, sha in freeze["file_sha256"].items()
                   if name.startswith("skills/")}
    if original_skills.keys() != skill_hashes.keys():
        raise ValueError("Original skill snapshot does not match the frozen file set")
    for name, expected in skill_hashes.items():
        if hashlib.sha256(original_skills[name].encode("utf-8")).hexdigest() != expected:
            raise ValueError(f"Historical skill provenance mismatch: {name}")
    check_hashes(ROOT, {name: sha for name, sha in freeze["file_sha256"].items()
                        if name not in skill_hashes})
    summary = read_json(run / "comparison.json")
    for mode in ("strict", "sensitivity"):
        recomputed = report(run / f"assistant-adjudication-{mode}-v1")
        saved = read_json(run / f"scoring-{mode}-v1.json")
        if recomputed != saved:
            raise ValueError(f"Recomputed {mode} scores differ from the published scores")
        print(f"{mode}: all three system reports reproduce exactly")
    for name, system in summary["systems"].items():
        q = system["quality"]
        print(f"{name}: strict F1={q['f1']:.4f}; completed={q['completed']}/{q['cases']}")
    print(f"Verified {len(publication['published_file_sha256'])} published artifacts "
          f"and {len(freeze['file_sha256'])} frozen source/fixture files.")
    print("Assistant-adjudicated development results; independent human validation pending.")
    print("Historical results use the archived original prompts, not the active English translation.")


if __name__ == "__main__":
    main()
