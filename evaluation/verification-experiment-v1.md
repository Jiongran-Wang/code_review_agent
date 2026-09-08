# Verification experiment v1

Status: implementation and local tests complete; live model run not yet started.

## Experiment

Compare `agent` with `agent-verified` on the same 16 development fixtures, one
repeat each: 32 reviews. Both use GPT-4o-mini, temperature 0, the original control
rubric, 8 iterations, 2048 output tokens per call, a 100000 observed-token budget
per review, isolated memory, and the existing pacing/retry policy. The verified
agent additionally receives `execute_example` and its short usage guidance.
It does not use the evidence-v1 prompt or its forced evidence headings.

This tests the combined addition of an execution tool and instructions to use
it. It does not isolate the tool from its guidance. A fresh original-agent arm
helps contextualize sampling variation; neither arm is replaced by prior
results. Case selection remains 8 clean/defect pairs, not a held-out test set.

Hypothesis: observations from runnable examples reduce incorrect behavioral
claims and improve defect detection, while preserving review submission. Report
the same primary semantic and sensitivity metrics from `scoring-policy-v1.md`,
plus workflow completion, execution use, API calls, tokens, execution duration,
and API duration separately from pacing. A lower cost accompanied by incomplete
work is not an equivalent-work improvement. Do not revise scoring after viewing
the new outputs.

## Completion checks

`status=ok` continues to mean valid final JSON, preserving prior detection
metrics. Every new result also has a `workflow` object:

- All systems require valid final output.
- Agent systems additionally require at least one successful fixture review
  submission.
- `agent-verified` also requires at least one plan that returned execution
  observations for both revisions.

Execution exceptions such as `ZeroDivisionError` are observations, not tool
errors. An example that executes is not necessarily a valid defect witness.
Incorrect function arguments can also produce exception observations; semantic
adjudication must check the proposed inputs against the contract. Submission
presence does not establish consistency or correctness of the review body.

The runner prints incomplete workflows and returns a nonzero exit code if any
attempted review has an incomplete workflow. It continues the remaining cases
unless an existing API-abort condition applies. It does not repair final JSON,
silently submit a review, or reroll model-quality failures. The detection report
and workflow report remain separate. Resume reuses previously valid outputs;
it is not a way to improve missing-submission results by sampling again.

Retrospective workflow audits were saved beside the original runs without
changing them: original agent 16/16 complete, evidence-v1 agent 5/16 complete.

## Execution interface and boundary

The tool accepts JSON `calls`, optional named `values`, and optional
`sqlite_rows`. It executes the same plan on both original base and head source.
Calls within one revision share state, and each revision/plan starts fresh.
Return values, named-state snapshots, and exception types are recorded. The tool
does not read labels or oracle tests, supply expected answers, grade correctness,
or execute proposed fixes. Inference guidance contains no fixture-specific test
inputs or answers.

Only the 24 manually inspected source modules whose SHA-256 identities appear
in `execution_registry.py` can run. User-supplied Python, shell commands, imports,
function introspection, new source modules, and modified fix branches are not
supported. Function names must refer to functions defined by the approved
module. JSON values cannot supply Python objects or callbacks.

Each revision runs in a fresh Python process with a temporary working directory,
an environment containing no API key, a 3-second wall timeout, CPU/file-size/file
descriptor limits, and bounded input/output. Plans allow at most 12 calls, JSON
depth 8, collections of 128 elements, strings of 2048 characters, and finite
numbers bounded in magnitude. Requests are limited to 32 KiB and each revision's
response to 24 KiB. Four plans are allowed per review, including rejected plans
after argument validation.

For the SQL fixture, the tool creates only an in-memory `users(id, name)` table.
An authorizer denies file/extension/other SQL operations; statement size and VM
work are bounded. This still allows the fixture's SELECT injection to be
observed against caller-supplied rows.

This is an audited-fixture executor, **not a general security sandbox for
untrusted repository code**. The source registry and declarative interface are
essential restrictions. The process still uses the local Python runtime; do
not relax the hash gate or execute model-written code with it. Generalizing to
arbitrary PRs requires a separate container/VM execution design and validation.
This implementation is tested on the current macOS Python 3.12 environment.

## Run

From the project directory:

```bash
bash evaluation/run_verification_experiment.sh
```

Enter the API key at the hidden prompt. Output defaults to
`evaluation/runs/gpt4omini-verification-v1`; optionally supply a new directory as
the script's first argument. Allow roughly 45–75 minutes: both arms now use
multiple agent calls, unlike the previous single-call baseline arm. Runtime can
be longer if throttled or if the model uses more iterations. This is paid API
usage with the same model and budgets as before.

After completion, prepare independent review packets:

```bash
.venv/bin/python -m evaluation.adjudicate prepare \
  --run evaluation/runs/gpt4omini-verification-v1 \
  --labels evaluation/data/labels.jsonl \
  --output evaluation/runs/gpt4omini-verification-v1/adjudication
```

Local tests cover actual behavior for all eight defect families, state isolation,
in-memory SQL injection and extension rejection, unknown-source rejection,
declarative-only input, cross-case rejection, plan limits, timeout handling,
environment isolation, prompt hashes, and workflow semantics. The scripted
32-review run exercises both arms and makes no model-quality claims. In that
smoke test, generic calls with omitted arguments deliberately exercise exception
observations; behavioral correctness is covered by separate concrete tests.
