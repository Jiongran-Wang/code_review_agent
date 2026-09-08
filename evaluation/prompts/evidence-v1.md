Evidence requirements for this review:

Review the changed behavior against the PR's stated requirements and the base
revision. For a candidate defect, check a concrete input or state that satisfies
the documented preconditions. Compare the required behavior, the base behavior,
and the head behavior. Report introduced violations, not hypothetical problems
outside the contract or problems already present in the base revision.

In each finding's existing description string, provide a concise explanation
with these labels: "Trigger:", "Expected:", "Actual:", and "Cause:". State a
specific triggering input or state, the required result, the head revision's
different result, and the changed code responsible for it. Describe the effect
accurately rather than only naming a suspicious expression. No additional JSON
fields are needed. This is a short, checkable defect explanation.

Use available source and tool results as evidence. If no execution tool is
available, infer the behavior by inspecting the code and say "Basis: code
inspection". Do not claim to have executed tests without an actual tool result.
When proposing a repair, check that it restores the required behavior for the
triggering case; omit an unverified repair rather than presenting it as proven.

Keep praise, stylistic preferences, generic security reminders, and speculative
warnings out of findings and submitted defect comments. Do not invent a defect
to fill the requested structure. Return findings: [] if no actionable introduced
defect is supported. Apply the same evidence standard to tool-submitted reviews
and the final JSON. Preserve the final JSON schema specified above.
