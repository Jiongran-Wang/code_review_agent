"""Prepare blinded review packets and score completed semantic judgments."""
import argparse
import json
import math
import random
import statistics
from pathlib import Path

from .fixture_router import digest
from .run import read_jsonl, write_json, write_jsonl
from .score import score
from .workflow import summarize_workflow


def prepare(run, labels_path, output):
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest["backend"] != "live":
        raise ValueError("Scripted smoke runs are not model evaluations and cannot be scored")
    if output.exists():
        raise ValueError("Packet output already exists")
    inputs = {r["case_id"]: r for r in read_jsonl(run / "inputs.jsonl")}
    labels = {r["case_id"]: r for r in read_jsonl(labels_path)}
    if not inputs.keys() <= labels.keys():
        raise ValueError("Missing labels for run cases")
    if digest(list(inputs.values())) != manifest["input_sha256"]:
        raise ValueError("Input snapshot differs from the run manifest")
    results = read_jsonl(run / "results.jsonl")
    index = {(r["system"], r["repeat"], r["case_id"]): r for r in results}
    if len(index) != len(results):
        raise ValueError("Duplicate run results")
    expected = {(name, repeat, case_id)
                for name in manifest["settings"]["systems"]
                for repeat in range(1, manifest["settings"]["repeats"] + 1)
                for case_id in inputs}
    if set(index) != expected:
        raise ValueError("Run is incomplete; finish the planned run before adjudication")
    records = sorted(index)
    random.Random(817).shuffle(records)
    output.mkdir(parents=True)
    keys = []
    for number, (system, repeat, case_id) in enumerate(records, 1):
        task_id = f"review-{number:04d}"
        result = index[(system, repeat, case_id)]
        raw_path = run / system / f"repeat-{repeat}" / case_id / "raw.json"
        packet = {"task_id": task_id, "case_id": case_id, "input": inputs[case_id],
                  "gold_issues": labels[case_id]["issues"],
                  "status": result["status"], "findings": result["findings"],
                  "raw_review": json.loads(raw_path.read_text()),
                  "normalization_reviewed": False,
                  "decisions": [{"finding_id": f["finding_id"], "gold_issue_id": "PENDING",
                                 "rationale": ""} for f in result["findings"]]}
        write_json(output / f"{task_id}.json", packet)
        keys.append({"task_id": task_id, "system": system, "repeat": repeat, "case_id": case_id,
                     "original_status": result["status"]})
    # Keep system mapping separate from the packets presented to reviewers.
    write_json(output / "mapping.json", {"run_path": str(run.resolve()),
               "manifest_sha256": digest(manifest), "results_sha256": digest(results),
               "labels_sha256": digest([labels[c] for c in sorted(inputs)]), "tasks": keys})
    write_jsonl(output / "labels.snapshot.jsonl", [labels[c] for c in sorted(inputs)])
    return len(keys)


def report(packets):
    mapping = json.loads((packets / "mapping.json").read_text())
    labels = read_jsonl(packets / "labels.snapshot.jsonl")
    if digest(labels) != mapping["labels_sha256"]:
        raise ValueError("Gold labels changed; prepare a new version and rescore all systems")
    run = Path(mapping["run_path"])
    manifest = json.loads((run / "manifest.json").read_text())
    results = read_jsonl(run / "results.jsonl")
    if (digest(manifest) != mapping["manifest_sha256"]
            or digest(results) != mapping["results_sha256"] or manifest["backend"] != "live"):
        raise ValueError("Run artifacts changed after packet preparation")
    groups = {}
    for entry in mapping["tasks"]:
        packet = json.loads((packets / f"{entry['task_id']}.json").read_text())
        if packet["case_id"] != entry["case_id"] or packet["status"] != entry["original_status"]:
            raise ValueError("Do not change case identity or execution status during adjudication")
        if packet.get("normalization_reviewed") is not True:
            raise ValueError(f"{entry['task_id']}: normalization review is pending")
        for decision in packet["decisions"]:
            if decision["gold_issue_id"] == "PENDING" or not decision.get("rationale", "").strip():
                raise ValueError(f"{entry['task_id']}: every finding needs a judgment and rationale")
        key = (entry["system"], entry["repeat"])
        reviews, judgments = groups.setdefault(key, ([], []))
        reviews.append({"case_id": packet["case_id"], "status": packet["status"],
                        "findings": packet["findings"]})
        judgments.append({"case_id": packet["case_id"], "decisions": packet["decisions"]})
    output = {"backend": "live", "dataset": "development pilot", "systems": {},
              "workflow": summarize_workflow(results) if all("submitted_reviews" in r["metrics"] for r in results) else None,
              "adjudication": mapping.get("adjudication", {
                  "reviewer_type": "unspecified", "human_validation": "not_verified"})}
    for (system, repeat), (reviews, judgments) in sorted(groups.items()):
        quality = score(labels, reviews, judgments)
        observations = [r["metrics"] for r in results if r["system"] == system and r["repeat"] == repeat]
        durations = sorted(r["duration_ms"] for r in observations)
        efficiency = {"median_duration_ms": statistics.median(durations),
                      "p95_duration_ms": durations[math.ceil(0.95 * len(durations)) - 1],
                      "reported_input_tokens": sum(r["input_tokens"] or 0 for r in observations),
                      "reported_output_tokens": sum(r["output_tokens"] or 0 for r in observations),
                      "unknown_usage_runs": sum(r["input_tokens"] is None for r in observations),
                      "tool_errors": sum(r["tool_errors"] for r in observations)}
        if all("pacing_wait_ms" in r for r in observations):
            efficiency.update(pacing_wait_ms=sum(r["pacing_wait_ms"] for r in observations),
                              rate_limit_retries=sum(r["rate_limit_retries"] for r in observations),
                              api_duration_ms=sum(r["api_duration_ms"] for r in observations))
        if all("example_execution_calls" in r for r in observations):
            efficiency.update({key: sum(r[key] for r in observations) for key in
                               ("example_execution_calls", "example_execution_successes", "example_execution_duration_ms")})
        output["systems"].setdefault(system, {})[f"repeat-{repeat}"] = {
            "quality": quality, "efficiency": efficiency}
    output["notes"] = ["Each repeat is reported separately; repeated cases are not independent samples.",
                       "Latency includes failures. Token totals include only reported usage, not inferred costs.",
                       "Review duration includes pacing; API duration and pacing waits are reported separately when recorded.",
                       "Packet normalization and semantic matches need independent human validation.",
                       "Fix correctness has not been executed or scored."]
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("prepare")
    make.add_argument("--run", type=Path, required=True)
    make.add_argument("--labels", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("report")
    evaluate.add_argument("--packets", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(f"Prepared {prepare(args.run, args.labels, args.output)} packets; judgments are pending")
        else:
            if args.output.exists():
                raise ValueError("Report output already exists")
            result = report(args.packets)
            write_json(args.output, result)
            print(f"Report: {args.output}")
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
