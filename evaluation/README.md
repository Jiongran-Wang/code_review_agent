# Evaluation

The evaluation framework compares code-review configurations on paired synthetic
pull requests. GitHub operations are served by a local fixture adapter; model
inference is selected separately with `--backend scripted` or `--backend live`.

## Dataset

The development dataset contains **16 Python PR fixtures: eight planted defects
and eight clean counterparts**. Each pair shares its base revision, PR title,
and behavioral requirements, with a different head revision.

| Family | Planted defect |
|---|---|
| Pagination | Exclusive endpoint omits an item |
| Mutable default | Calls share an unintended list |
| Empty aggregate | Empty input divides by zero |
| Expiration | Exact expiry boundary is accepted |
| SQL parameterization | Untrusted input changes a query |
| Ownership check | Authentication replaces authorization |
| Preprocessing leakage | Centering fits on train and test data |
| Historical-price window | Feature includes an unavailable current price |

`data/inputs.jsonl` contains model-visible PR metadata, source, and diffs.
`data/labels.jsonl` contains evaluator-only labels, reference repairs, and checks.
The base, clean head, and reference repairs pass the regression and trigger checks;
planted defects fail their targeted trigger checks. Validation covers 96
revision/check combinations. These checks execute authored fixtures in subprocesses,
not a security sandbox for untrusted code.

The fixtures are assistant-authored development data with executable reference
checks. They have not received independent human annotation. The separate
[16-case candidate set](candidate_sets/generalization-v1/README.md) has not been
model-evaluated or added to the execution allowlist.

## Configurations

| System | Behavior |
|---|---|
| `baseline` | One model call with the review rubric and supplied source context |
| `agent` | Original tool-driven review loop with isolated per-case memory |
| `agent-verified` (v3) | Context collection, bounded fixture execution, review submission, and compact finalization |

The adapter reuses the production tool schemas and captures review submissions,
proposed fixes, and memory operations locally. V3 executes only audited,
hash-registered fixture functions. The configurations differ in prompts, tools,
and compute; the comparison measures complete systems.

## Published results

The completed GPT-4o-mini run contains **48 reviews**, one per fixture and system.
Results include quality metrics, completion failures, execution evidence, usage,
and strict versus cause-only scoring sensitivity.

- [Results and failure analysis](published/full-comparison-v3/comparison.md)
- [Run artifacts and provenance](published/full-comparison-v3/README.md)
- [Scoring policy](scoring-policy-v1.md)

Scores are provisional, non-blinded assistant judgments on development data.
Independent human validation is pending. Fix correctness and memory benefits
are not measured by this comparison.

The published run used the original Chinese skill prompts, preserved in the
artifact archive. The active skills are now English; their model performance
has not been evaluated.

Recompute the published scores without API calls, from the repository root:

```bash
.venv/bin/python scripts/verify_published_results.py
```

## Run locally

Use Python 3.12 with the root `requirements.txt` installed in `.venv`.

```bash
.venv/bin/python evaluation/validate_dataset.py
.venv/bin/python -m unittest discover -s evaluation -p 'test_*.py'

.venv/bin/python -m evaluation.run \
  --backend scripted --systems baseline agent agent-verified \
  --verification-version v3 --max-iterations 8 \
  --output evaluation/runs/local-smoke
```

Scripted runs use no API key and test workflow behavior, not model quality.
Output directories must be fresh.

To rerun the historical comparison, follow the separate-checkout instructions
in the [experiment specification](full-comparison-v3.md). Its launcher verifies
the original source and prompt hashes, prompts for an API key without echoing it,
and schedules 48 paid reviews with pacing and bounded retries. It rejects the
active English prompts because they differ from the original experiment.
Budgets are checked between calls and are not hard billing caps.

Interrupted runs can reuse successful outputs in a fresh directory:

```bash
.venv/bin/python -m evaluation.run \
  --resume-from evaluation/runs/my-full-comparison \
  --prompt-api-key --output evaluation/runs/my-full-comparison-resumed
```

Resume restores the original settings and checks source, prompt, and fixture
compatibility. It retries missing cases or API failures with no model responses;
completed quality failures and partial agent executions are preserved.

## Scoring

The strict policy requires a finding to identify both the introduced cause and
a correct, concrete consequence within the fixture contract. Each gold issue
can match one finding. Unmatched and duplicate defect claims count against
precision. Pure praise is excluded with normalization notes retained.

Failed buggy reviews count as misses. Failed clean reviews are excluded from the
clean false-alarm denominator and reported through completion counts. Exact-line
localization is scored separately from semantic detection.

To prepare review packets for a completed live run:

```bash
.venv/bin/python -m evaluation.adjudicate prepare \
  --run evaluation/runs/my-full-comparison \
  --labels evaluation/data/labels.jsonl \
  --output evaluation/runs/my-review-packets
```

Each packet contains the source, gold issues, raw review, and pending decisions.
After completing normalization and semantic judgments:

```bash
.venv/bin/python -m evaluation.adjudicate report \
  --packets evaluation/runs/my-review-packets \
  --output evaluation/runs/my-scoring.json
```

Run artifacts retain input snapshots, source and prompt hashes, model settings,
request records, tool traces, findings, submitted reviews, and usage statistics.
