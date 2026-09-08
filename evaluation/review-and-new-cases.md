# Human review and new-case preparation

Two deliverables are ready; no paid model calls were made.

**Start with the existing judgments:**
[six priority review packets](published/full-comparison-v3/human-review-priority/START-HERE.md).
The first three focus on mixed historical-price explanations, pagination diagnosis
versus repair, and how training-only fitting violations are described. Three more
check a contradictory clean-case report, an invalid-argument false alarm and a
diagnosis whose concrete consequence appears in the submitted body. The six priority answers are filled by an AI assistant and explicitly marked
not human-validated. The original 48 human packets and provisional scores are untouched.

**Then review the proposed new data:**
[16 candidate cases and reference checks](candidate_sets/generalization-v1/README.md).
There are eight additional patterns, each with clean and buggy variants, eight
human-readable family packets, and 96 passing validation expectations. Model-visible
inputs are separate from labels, reference repairs and test checks. The set remains
unrun, assistant-authored and pending human validation. No independent reviewer
has approved it yet.

The frozen v3 files and original full-run results still match their saved hashes.
The new candidate code has not been added to the execution allowlist, so it cannot
yet be used for a valid execution-enabled comparison. After label review and a
separate source audit/tooling update, freeze a new experiment before running models.
Do not describe the candidate set as a validated holdout or the current provisional
scores as independently verified performance.
