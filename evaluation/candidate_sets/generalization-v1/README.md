# New candidate evaluation cases

**16 cases across 8 new patterns: 8 clean refactors and 8 buggy counterparts.**
They are assistant-authored candidates awaiting human review. No evaluated model
has been run on them, and no new inference prompts contain their labels or checks.
They are not yet an independently validated holdout set.

| Pattern | Main behavior being tested |
|---|---|
| Weighted mean denominator | Weight totals rather than observation counts; scaling weights preserves the mean. |
| Sample variance | Correct n − 1 denominator for unbiased sample variance. |
| Confusion-matrix recall | Correct row/column convention and TP/(TP+FN). |
| Running-peak drawdown | Earlier observations cannot use a future portfolio peak. |
| Historical quote lookup | Select the latest eligible observation, not the oldest. |
| Literal SQL prefix | Treat wildcard characters literally even with safely bound SQL parameters. |
| Scoped permission | Both tenant membership and read permission are required. |
| Ranking input mutation | Return a sorted copy without changing the caller's list. |

The new case IDs and exact source texts do not overlap the original 16 fixtures.
Related concepts still overlap (temporal correctness, authorization, SQL and state),
and the construction style and author are shared. This is broader coverage, not
proof of independent generalization. All cases remain small single-file examples.

## What was checked

`validation.json` records **96 reference checks**: two checks for each of base,
head and reference repair across all 16 cases. The normal regression must pass
every revision; the targeted check must fail only the buggy head. Each subprocess
starts fresh and receives no inherited API key. All expected failures were
assertion failures. These checks establish behavior for the authored examples,
not universal contract correctness or completeness of the gold labels.

The SQL fixture seeds meaningful rows and includes literal special-character
prefixes. Permission checks include all four boolean combinations. Mutation checks
examine both returned values and caller-owned input state. Preconditions are stated
explicitly to let human reviewers distinguish invalid tests from real regressions.

## Files and review order

1. Read the eight Markdown files in [review-packets](review-packets). Each contains
   the contract, base, clean refactor, buggy refactor, proposed label and checks.
2. Record human decisions in `human-review.json`, leaving uncertainties pending.
   No decisions are pre-approved. Changes to data or labels require a new candidate
   version and another validation pass.
3. `inputs.jsonl` contains only the five model-visible fields accepted by the
   existing fixture schema. `labels.jsonl` separately holds variants, reference
   issues, repairs and checks. Never include labels or review packets in inference.
4. `manifest.json` records data/builder hashes and candidate status. `source-review.json`
   lists source identities for a later execution audit; it is not an active allowlist.

To reproduce local reference checks without any model calls:

```bash
.venv/bin/python evaluation/candidate_sets/generalization-v1/build.py
```

The builder rejects differing pre-existing data instead of silently replacing it,
and does not overwrite a human-review form that already exists.

## Before an evaluation run

The current execution worker intentionally accepts only the original audited
source identities. **These cases are not yet supported by agent-verified.** Do
not run a three-system evaluation on them yet: rejected source would invalidate
that comparison. Audit and admit the new source in a separately versioned execution
registry, and add source-appropriate scripted protocol examples, before freezing
the next experiment. This is tooling preparation, not evidence of model quality.

First complete human checks of the existing disputed judgments and these candidate
labels. Preserve the frozen v3 inference code while reviewing. For independent
validation, use someone independent of construction and earlier assistant scoring;
review by a participant in that process should simply be described as human review.

Do not tune prompts using model outputs on these candidates before deciding their
evaluation role. Freeze the next model/system/scoring configuration before the first
model run. If these cases become development data, reserve different cases for
later evaluation and label the split accordingly. No paid run is scheduled here.
