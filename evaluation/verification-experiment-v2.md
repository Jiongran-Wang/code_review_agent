# Verification v2: integration repair and diagnostic pilot

The previous paired experiment found no increase in strict recall, more false
positives, and only 7/16 completed execution-enabled workflows. This iteration
addresses tool misuse and finalization before another full comparison.

## Changes

- The v2 execution schema lists audited head-source function names as an enum,
  with paths and actual signatures/defaults in its description. A generic JSON
  example distinguishes source calls from agent tools. No gold labels, oracle
  assertions, reference repairs or expected outputs enter the inference prompt.
- The worker validates function names, argument binding and named references
  before any fixture function call. Invalid plans return a bounded actionable
  `invalid_plan` error. A `TypeError` raised inside a correctly bound fixture
  function remains a runtime observation. Failed plans no longer claim execution.
- Guidance asks the agent to check contract preconditions, compare base/head,
  use matching JSON key types, batch related inputs and report each defect once.
  These are instructions to the model, not automatic semantic correctness checks.
- Only the v2 execution-enabled arm uses the finalization policy. It closes
  investigation when fewer than three conservatively estimated calls fit the
  remaining observed-token budget, or only two iterations remain. The estimate
  is 1.2 times the last reported input tokens plus the output cap. It advertises
  only the review-submission tool, then removes tools and requests final JSON.
  The router rejects unadvertised investigation calls during finalization.
- The policy logs its phase changes and reports `token_budget_exhausted` explicitly
  when its observed-token guard stops the run. It does not increase the budget,
  synthesize a review, repair JSON, or mark a missing execution/submission complete.
  It cannot guarantee finalization if the model ignores instructions or a request
  grows unexpectedly. The budget remains checked between calls, not a hard cap
  on provider billing.

The worker remains restricted to exact audited source hashes and bounded JSON
plans in isolated processes. It is not a general sandbox for generated Python.
Validation does not infer arbitrary input types or semantic preconditions:
an integer key against string dictionary keys can still produce a real KeyError
observation. The model and subsequent evaluator must interpret it correctly.

Original run artifacts and the control prompt are preserved. V2 uses a separate
prompt file and explicit manifest setting. Worker validation repairs are shared
by current execution runs, including the v1 prompt option; source-hash checks
prevent resuming an old execution run across these changes. Do not treat a new
v1-prompt run as a reproduction of the old worker implementation.

## Local checks

Run `.venv/bin/python -m unittest discover -s evaluation -p 'test_*.py' -q`.
Regression tests cover nested tool names, source-derived schemas, too many or
missing arguments, duplicate argument assignment, body-level exceptions, invalid
references, recovery after rejected plans, submission/final-output budget reserve,
iteration reserve, explicit budget termination, and no fabricated execution.

The full 16-fixture, two-arm scripted smoke run is recorded under
`evaluation/runs/verification-v2-smoke`. Scripted inputs use fixed neutral examples
to exercise valid invocation and protocol flow. They do not measure model quality.
`validation-audit.json` there records replay of previously rejected live plans.

## Six-case live diagnostic

Run from the project folder:

```bash
bash evaluation/run_verification_diagnostic.sh
```

Paste the full API secret into the hidden terminal prompt. The script uses paid
`gpt-4o-mini` calls, the existing pacing/retry controls, one sample per case, and
the unchanged 100,000 observed-token budget / 2,048 output-token cap. It runs only
the revised arm on six existing development cases, roughly 10–20 minutes with
pacing if there are no extended retries. Actual usage and duration can vary.
It always writes a new output directory and will not overwrite an existing run.
An optional first argument selects another fresh output directory.

The fixed source-only input file is
`evaluation/data/verification-v2-diagnostic-inputs.jsonl`. The following selection
is for evaluator documentation only; it is not passed as inference guidance:

| Case ID | Observed failure being diagnosed |
|---|---|
| 85ad40fd5032 | Tool-name confusion and repeated rejected plans |
| 6a75289b0733 | Recursive tool-call generation reaching the output cap |
| 9ec94bab74f0 | Invalid argument count interpreted as a code defect |
| 4d93c32539ce | Out-of-contract input interpreted as an introduced defect |
| c85a607a54b5 | Correct behavioral discrepancy, budget exhausted before final JSON |
| ebc8d8481ffc | Multiple witnesses reported as duplicate defects |

Before scaling up, inspect whether all six runs produce valid JSON, submit a
review and execute at least one plan; whether invalid calls recover without
repetition; whether exception reports respect the contract and both revisions;
and whether each defect is reported once. The two clean cases require particular
attention to false alarms. Preserve failures rather than rerolling them away.
Use the existing semantic scoring policy for any quality judgments, with human
validation still pending. This selected diagnostic is not a fair comparative
benchmark and cannot establish a performance gain.

If the integration behaves correctly, schedule a new paired experiment with a
fresh control and fixed settings. A later holdout should use new independently
checked cases, since these development fixtures have informed the repairs.
