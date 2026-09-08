# Verification v3: require execution before submission

The six-case v2 pilot completed only four workflows. In two cases, separate PR
and diff fetches consumed both investigation turns permitted by the budget rule.
The agent then had no opportunity to execute. One final review also paired APPROVE
with a nonempty praise finding. V3 addresses this workflow regression before a
larger experiment.

## Implementation

The execution-enabled arm now advertises tools by required stage:

1. **Context:** read PR metadata and changed code. Both PR and diff tools must
   succeed; fetching them in separate model turns is supported.
2. **Execute:** only execute_example is available. It must return observations
   before the agent can enter submission. A rejected plan stays in this stage
   for correction, subject to the existing four-plan and overall budget limits.
3. **Submit:** only create_pull_request_review is available. The model interprets
   execution results and submits its own review.
4. **Final:** no tools; the model returns the required JSON. APPROVE requires an
   empty findings array. Praise and readability comments are not defect findings.

The router rejects calls outside the current stage. The model can still terminate
prematurely; such a run remains workflow-incomplete. The harness does not create
tests or submissions on the model's behalf, repair final JSON, or remove findings.

Context collection and execution retain the full original review rubric plus
versioned guidance. Submission and final JSON use a concise system prompt with
the same evaluation scope, output contract, verification instructions and a stage
instruction. Full message history, source context and tool observations remain
available. This reduces finalization input cost instead of increasing limits.
The revised arm therefore changes both workflow/tool exposure and stage prompts;
it is not a pure test of one prompt sentence.

Before each call after the first response, the policy estimates remaining stage
costs using reported input-token usage calibrated against recorded request size,
the actual prompt/tool set for each phase, a 15% estimation allowance, 1,024
additional context tokens per subsequent stage, and the configured output cap.
Insufficient estimated tokens or iterations stop the run explicitly as
`insufficient_workflow_budget`, instead of skipping execution. Requests log each
estimate and phase transition. Token estimates are approximate; unusually large
tool results can invalidate the estimate. The observed-budget guard remains in
place, checked between calls rather than imposing a strict billing cap.

The guidance also distinguishes reference objects such as `{"$ref":"items"}`
from literal strings, encourages contract-derived boundary examples, and explains
that default-state checks must omit optional state arguments. It supplies no
fixture-specific inputs, expected answers, reference repairs or labels.

Returning observations is a mechanical execution check, not verification of a
diagnosis. Invalid argument values and out-of-contract tests can still produce
observations. These require model reasoning and later independent adjudication.
The audited-source gate and bounded JSON execution restrictions are unchanged.

## Validation and live diagnostic

Local regression tests cover separate metadata/diff turns, rejected-plan recovery,
phase-specific budget estimates, explicit insufficient-budget termination,
iteration limits, early final output and preservation of inconsistent APPROVE
outputs. Existing evaluation tests cover reference resolution, binding errors,
fixture isolation and scoring. Scripted full-fixture results are stored separately
under `evaluation/runs/verification-v3-smoke`; they are not model quality scores.

Run the same six selected development cases, same model and limits, into a fresh
directory:

```bash
bash evaluation/run_verification_diagnostic_v3.sh
```

This uses paid GPT-4o-mini calls and a hidden API-key prompt. Allow approximately
10–20 minutes with the existing pacing, longer if retries are needed. It uses the
unchanged v2 six-case input file deliberately; the new manifest records version
v3, code hashes and exact hashes for all four stage prompts. Every request records
its actual prompt and tools. The previous launch script and live results remain
available, and resume refuses changed workflow policy/prompts.

Acceptance checks before a full paired experiment: six valid final reviews, six
submissions, six cases with executed examples, no skipped execution after separate
fetches, and no praise entries under APPROVE. Inspect test relevance, reference
syntax, boundary coverage and duplicate findings separately. Keep failures and
apply the existing scoring policy; do not reroll quality failures. Results remain
selected development diagnostics without a fresh control or independent human
validation, so they cannot establish a general accuracy improvement.
