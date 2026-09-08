"""Score structured reviews after independent semantic adjudication.

This deliberately does not treat keywords, review decisions, or an LLM's own
issue count as ground truth. See README.md for the annotation protocol.
"""
import argparse
import json
from pathlib import Path


def indexed(rows, field):
    result = {}
    for row in rows:
        key = row[field]
        if key in result:
            raise ValueError(f"Duplicate {field}: {key}")
        result[key] = row
    return result


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def score(labels, reviews, adjudications):
    gold = indexed(labels, "case_id")
    predicted = indexed(reviews, "case_id")
    judged = indexed(adjudications, "case_id")
    if set(gold) != set(predicted) or set(gold) != set(judged):
        raise ValueError("Every case needs exactly one review and adjudication, including failed runs")
    if not gold:
        raise ValueError("Empty evaluation")

    tp = fp = total_gold = localized = completed = clean_completed = clean_flagged = 0
    by_category = {}
    for case_id, label in gold.items():
        review, judgment = predicted[case_id], judged[case_id]
        if review["status"] not in ("ok", "error"):
            raise ValueError("status must be ok or error")
        findings = indexed(review["findings"], "finding_id")
        decisions = indexed(judgment["decisions"], "finding_id")
        if set(findings) != set(decisions):
            raise ValueError("Every finding needs an adjudication, including false positives")
        if review["status"] == "error" and findings:
            raise ValueError("Error runs must have no scored findings; retain partial output separately")
        for finding in findings.values():
            if not isinstance(finding.get("description"), str) or not finding["description"].strip():
                raise ValueError("Findings need a nonempty description")
            if not isinstance(finding.get("file"), str):
                raise ValueError("Findings need a file path (empty string allowed for unlocalized findings)")
            line = finding.get("line")
            if line is not None and (type(line) is not int or line < 1):
                raise ValueError("line must be a positive integer or null")
        issues = indexed(label["issues"], "issue_id")
        total_gold += len(issues)
        for issue in issues.values():
            bucket = by_category.setdefault(issue["category"], {"detected": 0, "total": 0})
            bucket["total"] += 1
        completed += review["status"] == "ok"
        if not issues and review["status"] == "ok":
            clean_completed += 1
            clean_flagged += bool(findings)
        used = set()
        for finding_id, decision in decisions.items():
            issue_id = decision["gold_issue_id"]
            if issue_id is None:
                fp += 1
                continue
            if issue_id not in issues:
                raise ValueError("Matched issue must belong to the same PR case")
            if issue_id in used:
                raise ValueError("One-to-one matching required; mark duplicate findings as unmatched")
            used.add(issue_id)
            tp += 1
            issue, finding = issues[issue_id], findings[finding_id]
            by_category[issue["category"]]["detected"] += 1
            line = finding.get("line")
            localized += (finding["file"] == issue["file"] and line is not None
                          and issue["line_start"] <= line <= issue["line_end"])
    fn = total_gold - tp
    for bucket in by_category.values():
        bucket["recall"] = rate(bucket["detected"], bucket["total"])
    return {
        "cases": len(gold), "completed": completed, "failed": len(gold) - completed,
        "completion_rate": rate(completed, len(gold)),
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": rate(tp, tp + fp), "recall": rate(tp, total_gold),
        "f1": rate(2 * tp, 2 * tp + fp + fn),
        "localized_recall": rate(localized, total_gold),
        "clean_cases": sum(not row["issues"] for row in labels),
        "clean_completed": clean_completed, "clean_flagged": clean_flagged,
        "clean_pr_false_alarm_rate": rate(clean_flagged, clean_completed),
        "by_category": by_category,
        "notes": ["Rates are fractions; null means undefined, not zero.",
                  "Failed buggy cases count as misses; clean false-alarm rate uses completed clean cases.",
                  "These metrics depend on independently adjudicated findings and label completeness."],
    }


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--adjudications", required=True)
    args = parser.parse_args()
    print(json.dumps(score(read_jsonl(args.labels), read_jsonl(args.reviews),
                           read_jsonl(args.adjudications)), indent=2))


if __name__ == "__main__":
    main()
