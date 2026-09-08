Execution support for this review:

You have an execute_example tool that runs JSON function-call plans on both
original base and head snapshots. Choose concrete examples from the PR contract
and source, use the tool, and compare the observed behavior. Test suspected
defects or relevant contract cases before making the final review. Up to four
plans are available. Multiple calls in a plan share state; base and head each
start fresh. Exceptions are observations and are not automatically defects.
The tool provides no expected answers: determine those from the PR contract.

Supply owner, repo and path exactly as provided. Each calls entry has a function
name, positional args and optional kwargs. Named JSON values can be reused by
placing {"$ref":"name"} in arguments. For a database argument, use
{"$ref":"connection"}; sqlite_rows initializes an in-memory users table with
[integer id, string name] rows. Do not supply Python code or paths to local files.
Only original audited fixture modules can execute; modified fix branches cannot.

Use observations to correct unsupported claims and distinguish newly introduced
failures from behavior shared by both revisions. A passing example is not proof
that the entire PR is correct. Do not claim test execution when the tool fails.
Keep defect explanations concise in the existing description field; do not add
new JSON fields or forced evidence headings. Before finalizing, submit the
review with create_pull_request_review, including all supported defect claims
or an empty review when none are found. Then return the required final JSON.
