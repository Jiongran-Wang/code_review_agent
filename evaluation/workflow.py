"""Workflow completion is separate from JSON parsing and defect correctness."""


def assess_workflow(system, status, submitted_reviews, executed_examples=0):
    required = system != "baseline"
    valid = status == "ok"
    submitted = submitted_reviews > 0
    execution_required = system == "agent-verified"
    executed = executed_examples > 0
    return {"final_output_valid": valid, "review_submission_required": required,
            "review_submitted": submitted,
            "example_execution_required": execution_required, "example_executed": executed,
            "complete": valid and (submitted or not required) and (executed or not execution_required)}


def summarize_workflow(results):
    output = {}
    for name in sorted({r["system"] for r in results}):
        rows = [r for r in results if r["system"] == name]
        assessments = [assess_workflow(name, r["status"], r["metrics"]["submitted_reviews"],
                                      r["metrics"].get("example_execution_successes", 0)) for r in rows]
        output[name] = {"attempted": len(rows),
                        "final_outputs_valid": sum(r["final_output_valid"] for r in assessments),
                        "reviews_submitted": sum(r["review_submitted"] for r in assessments),
                        "reviews_with_executed_examples": sum(r["example_executed"] for r in assessments),
                        "workflow_complete": sum(r["complete"] for r in assessments),
                        "workflow_completion_rate": sum(r["complete"] for r in assessments) / len(rows)}
    return output
