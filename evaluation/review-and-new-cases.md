# Review artifacts and candidate data

## Semantic review packets

The [six priority packets](published/full-comparison-v3/human-review-priority/START-HERE.md)
contain assistant judgments and supporting evidence for sensitive scoring cases,
including mixed explanations, diagnosis versus repair, and invalid-input false
alarms. They are not independently human-validated. The original 48 human-review
packets remain pending.

## Candidate dataset

The [candidate set](candidate_sets/generalization-v1/README.md) contains 16 cases
across eight additional defect/clean pairs, with 96 reference-check expectations.
Model-visible inputs are separate from labels, repairs, and test oracles.

The set is assistant-authored, has not been evaluated by a model, and is pending
independent review. Its source functions are not registered with the execution
tool, so it is excluded from the published comparison.
