# Scoring policy v1: introduced defects and supported consequences

This policy was specified after inspecting the initial development run and
before the evidence-v1 experiment. It is a post-hoc clarification for the old
run, not a preregistered policy for it. Apply it identically to both prompts and
both systems. The 16 fixtures remain development data.

## Normalize before matching

Review final JSON and tool-submitted review bodies together. Preserve each
distinct defect allegation, including speculative warnings and style criticisms
presented as issues. Do not remove a claim simply because it is wrong. Merge
the same claim repeated in tool and final output; keep separate duplicates
within the final defect list as unmatched if they allege the same gold issue.
Pure praise or neutral descriptions that allege no defect are excluded from
semantic predictions and recorded separately as non-defect entries. Record the
original text and rationale for every normalization change. Also report the
raw clean-PR positive rate so normalization does not conceal output violations.

## Primary semantic match

Credit a finding only when it identifies the introduced causal change and a
correct concrete consequence under the stated preconditions, corresponding to
a reference issue. A wrong or self-contradictory consequence does not receive
primary credit, even if it points at the right expression. Naming suspicious
code without its behavioral consequence is insufficient. The old prompt need
not use Trigger/Expected/Actual labels or give a literal test input: equivalent
correct prose qualifies, avoiding a formatting advantage for the new prompt.

A proposed repair is assessed separately: a wrong repair does not erase an
otherwise complete and correct diagnosis. Conversely, a correct repair does
not rescue a contradictory diagnosis in the primary metric. Correct diagnoses
without repairs are eligible. Repair execution is not scored in this benchmark.

Match one finding to at most one reference issue in the same PR and one
reference issue to at most one finding. Unmatched defect claims are false
positives; unmatched reference issues are false negatives. Report detection
and exact gold-line localization separately. Incorrect line numbers do not
automatically erase a semantic match. If a finding reveals a valid defect
missing from the gold labels, audit/version the labels and rescore both systems.

## Partial findings and sensitivity

Keep an audit flag for findings that correctly identify the mutated cause but
omit or contradict its consequence. Primary scoring leaves these unmatched.
As a separate sensitivity analysis, allow these cause-level matches with the
same one-to-one constraint. Label this as an alternate scoring rule, not a
confidence interval or the primary score. Apply this rule across all systems.

For calibration on the initial run: the agent's pagination finding states the
opposite size change, and its empty-input finding lacks the empty-input failure
consequence. Both are partial. The baseline's shifted-history finding gives
the actual dropped observation and incorrect mean; it qualifies semantically
even though it does not use the term look-ahead leakage. These examples belong
to evaluator guidance only and must never be added to inference prompts.

## Provenance and reporting

Assistant-filled judgments are provisional and non-blinded when the assistant
has seen system identities. Do not label them independent human validation.
Keep human packets separate, preserve original results, and record policy and
artifact hashes. Human reviewers should examine reference correctness as well
as proposed matches. Repeated samples are not independent test cases.

Report precision, recall, F1, exact localization, clean-PR false alarms,
completion, API calls, tokens, tool errors and API duration separately from
pacing. Evidence-format adherence is secondary and must not change the primary
semantic rule. A single development repeat cannot establish generalization or
statistical superiority; report paired case changes before making claims.
