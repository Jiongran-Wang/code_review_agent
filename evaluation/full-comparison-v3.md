# Frozen v3 full development comparison

Run a fresh comparison on all 16 existing development fixtures: 8 planted-defect
cases and 8 clean variants, spanning eight source families. Each system reviews
each case once, for **48 reviews**. Do not reuse diagnostic outputs.

| System | Behavior |
|---|---|
| baseline | Single model call with PR metadata, base/head source and diff; no tools. |
| agent | Original review rubric and original tool-driven workflow. |
| agent-verified | Frozen v3 context → execution → submission → final workflow, including compact finalization prompts. |

This compares complete system configurations, not equal compute or tool
availability alone. The baseline has one call, while agents can use multiple
calls; the verified system also changes workflow and phase prompts. Report
accuracy, completion and observed usage together.

## Launch

```bash
bash evaluation/run_full_comparison_v3.sh
```

The script verifies `comparison-v3-freeze.json` before prompting for the API key.
The freeze covers inference sources, source-derived execution definitions, prompts,
fixture inputs, scoring policy and the launch script. A changed frozen file stops
the launch rather than silently changing the experiment. The freeze does not pin
the remote provider's serving configuration or local installed dependencies;
the run manifest records dependencies, and response records capture model IDs and
fingerprints. Do not edit inference code during the live run.

The key is entered at a hidden terminal prompt. Calls use paid `gpt-4o-mini` with
temperature 0, one repeat, order seed 42, no generation seed, a 100,000 observed
token budget per review, up to 8 iterations and 2,048 output tokens per call.
The runner paces at 30 seconds minimum between calls with a 48,000 target TPM,
up to 3 temporary-rate-limit retries and 180 seconds cumulative retry wait per call.
These match the diagnostic settings; the baseline still runs as a single call.

Output: `evaluation/runs/gpt4omini-full-comparison-v3-v1`. An optional first script
argument selects another fresh directory. Existing output is never overwritten.
Allow approximately **60–90 minutes**, depending on agent turns and retries.
The estimate follows previous observed call counts, not a service guarantee.
The 100,000-token budget is checked between calls and is not a hard billing cap.

## Analysis fixed before this run

Use the unchanged `scoring-policy-v1.md`. Review final JSON and submitted bodies
and inline comments together, merging repeated claims across those channels.
Preserve duplicate final defect claims, unsupported warnings and false alarms.
Exclude pure praise transparently, preserving raw clean-positive counts.
Match introduced cause plus correct in-contract consequence to the gold issue,
one-to-one. Report cause-only sensitivity separately. Do not repair failed model
output or reroll quality failures.

Report for all three systems:

- Semantic TP/FP/FN, precision, recall, F1 and exact-line localization.
- Clean-case false alarms with explicit completion denominators.
- Valid final outputs, submitted reviews and required workflow completion.
- Calls, input/output tokens, tool errors, retries, API time and pacing time.
- Per-family paired changes, not only aggregate percentages.
- For the verified arm, separate execution returning observations from valid
  examples that actually reproduce a diagnosed defect. Track out-of-contract
  examples, invalid argument values and duplicate execution plans.

Completion is a measured outcome, not grounds for discarding failed reviews.
When all scheduled cases have results, prepare separate pending human-review
packets and provisional assistant scores. Missing cases or API aborts must be
reported explicitly. Resume only where the existing runner permits it; do not
restart partially completed quality failures to replace their results.

Known diagnostic limitations to retain: the clean historical-mean false alarm
violates explicit preconditions; SQL examples did not demonstrate injection;
ownership examples used an invalid document mapping. Do not add case-specific
answers to the prompt to remove these failures before this comparison.

This is a **development comparison**, not a held-out benchmark. One repeat
does not estimate generation variability, and paired variants share source
families. Independent human validation and performance on unseen cases have
not been established.
