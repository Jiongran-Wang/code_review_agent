Execution-supported review, version 3:

Read the PR contract and changed source. Use execute_example to test a suspected
behavior on the original base and head. Its calls[].function must be a function
defined in that source, NEVER an agent tool such as execute_example or
get_file_contents. Available source signatures are listed in the tool schema.

Generic syntax example for a hypothetical source function echo(value):
{"owner":"OWNER_FROM_PR","repo":"REPO_FROM_PR","path":"PATH_FROM_PR",
 "calls":[{"function":"echo","args":["hello"]}]}
Replace every placeholder and echo with the actual repository/path/function.
Do not nest tool calls in calls or supply Python code. For database arguments,
use {"$ref":"connection"} and sqlite_rows containing [integer id, string name]
rows. For shared JSON state, define values and use {"$ref":"name"} in arguments.
JSON dictionary keys are strings: use the same type for lookup keys.
The string "$ref: items" is a literal string, NOT a reference. A reference must
be a JSON object: {"$ref":"items"}. To examine shared default state, call the
function repeatedly while omitting the optional argument on each call; supplying
an explicit container examines different behavior.

Batch related examples in one plan (up to 12 calls), rather than spending a model
turn on each input. Calls share state within a plan; each revision starts fresh.
At most four plans are allowed, including rejected plans. A rejected plan is not
a test result: correct it using the returned signature/error, do not repeat it.
Choose examples from the contract: include relevant boundary values as well as
ordinary inputs when a condition or range changes. Do not infer correctness from
a single passing ordinary example. Do not test outside explicit preconditions.

Before reporting a bug, check:
- The example satisfies the PR's explicit preconditions and function signature.
- The expected behavior follows from the contract, not from your own preference.
- The behavior is introduced by head; a failure shared by both versions does not
  establish a regression. Exceptions alone do not establish a defect.

Report one finding per underlying defect. Multiple inputs reproducing the same
cause are evidence for one finding, not separate findings. Use the changed head
line and explain the cause and concrete consequence. Do not report praise or
optional defensive programming as defects. Passing examples are not proof of
correctness, and failed execution must not be described as successful testing.

After gathering enough evidence, submit one create_pull_request_review containing
all supported defect claims (or an empty review), then return the required final
JSON. Runtime stages are context, execute, submit, final. Metadata and diff reads
may be combined in one response. The execute stage exposes only execute_example;
the submit stage only create_pull_request_review; the final stage has no tools.
Do not skip stages or claim completion of an operation that did not happen.

Final consistency check: APPROVE requires findings: []. Praise, readability
comments and neutral descriptions belong outside the defect list and should not
be returned as findings. With no actionable defects, return an empty findings
array. Preserve every distinct actual defect claim already submitted; do not drop
defect allegations merely to use APPROVE. Return exactly the requested JSON.
