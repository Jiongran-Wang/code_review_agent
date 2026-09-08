# Evidence prompt experiment v1

Control: `evaluation/runs/gpt4omini-dev-v1`.
Treatment: `evaluation/runs/gpt4omini-evidence-v1`.
Status: treatment prepared; no treatment model results yet.

## Question and controlled change

Does requiring concrete behavioral evidence reduce unsupported findings and
improve detection under the same model and review budgets?

Append `prompts/evidence-v1.md` to the existing baseline and agent system
prompts. Keep GPT-4o-mini, the 16 development inputs, one repeat, case order
seed 42, temperature 0, 8 iterations, 2048 output tokens per call, 100000 observed
tokens per review, tools, memory isolation, and pacing settings unchanged.
The original prompt remains available through `--prompt-variant control`.
Model aliases can change and generation is not deterministic; retained response
model IDs and metadata should be checked in the eventual comparison.

No labels, case IDs, oracle tests, prior model answers, category-specific hints,
or scoring calibration examples are included in the added inference prompt.
Its design was informed by development errors, so this is prompt tuning on
development data, not an independent test of generalization.

Descriptions keep the same JSON schema and add Trigger, Expected, Actual, and
Cause labels. Parser acceptance is unchanged, so a format-only difference does
not artificially improve completion. Evidence correctness must be checked
semantically; presence of labels alone is not success. Actual test execution is
not available through this fixture tool set, and the prompt says to label code
inspection honestly.

## Scoring and comparison

Use `scoring-policy-v1.md` for both control and treatment. Primary matching
requires the introduced cause and a correct concrete consequence. Old outputs
need not use the new labels or state a literal triggering input. Cause-only
partial matches receive sensitivity credit separately. Do not change this rule
after viewing treatment outputs; any revision requires a new policy version
and rescoring both runs.

Control score arithmetic has been checked with the current scorer. These remain
assistant judgments, not independently human-validated results:

| Strict primary metric | Agent | Baseline |
| --- | ---: | ---: |
| True / false positives / misses | 3 / 3 / 5 | 7 / 9 / 1 |
| Precision | 50.0% | 43.75% |
| Recall | 37.5% | 87.5% |
| F1 | 42.86% | 58.33% |
| Semantic false alarms on clean PRs | 1/8 | 6/8 |

Under cause-level sensitivity matching, agent TP/FP/FN become 5/1/3 and F1
71.43%; baseline scores are unchanged. The change in ranking shows why the
matching rule matters. These alternate numbers are not confidence intervals.
Agent praise in one raw finding is excluded semantically but retained as an
output-scope violation; the raw positive clean-PR rate is 2/8 for the agent.

After the treatment run, adjudicate it using the same policy. Report paired
case changes, per-system TP/FP/FN, precision/recall/F1, clean false alarms,
completion, token usage, API calls, and API duration excluding pacing. Do not
equate fewer findings with improved quality. A gain in precision accompanied by
a loss in recall is a tradeoff. One repeat cannot isolate prompt effects from
sampling variability or demonstrate statistical superiority.

The control has separate `assistant-adjudication-strict-v1/` and
`assistant-adjudication-sensitivity-v1/` folders with per-finding rationales and
policy snapshots. Their generated `scoring-*.json` reports carry explicit
provisional assistant provenance. The original `adjudication/` packets remain
pending for a human reviewer; do not misrepresent the assistant copies as
independent validation.

## Run

From the project folder, execute:

```bash
bash evaluation/run_evidence_experiment.sh
```

Enter the API key at the hidden prompt. The default output must not exist.
As in the control, expect roughly 30–45 minutes, possibly longer because the
new explanation requirement can increase generation or tool calls. API usage
is billed by the provider; this command does not change the selected model.

After the run completes:

```bash
.venv/bin/python -m evaluation.adjudicate prepare \
  --run evaluation/runs/gpt4omini-evidence-v1 \
  --labels evaluation/data/labels.jsonl \
  --output evaluation/runs/gpt4omini-evidence-v1/adjudication
```

Prompt design follows the principle of explicit instructions and empirical
evaluation in the [official OpenAI prompt guidance](https://developers.openai.com/api/docs/guides/prompt-engineering).
