---
name: code-review-test-gen
description: |
  Generate unit tests for new PR code paths that lack test coverage, and submit them as part of a fix PR.
  Internal skill called by code-review-act when its trigger conditions are met. Also triggered by:
  "generate tests for PR #N", "create unit tests", "add test coverage",
  "generate test cases", "automatically generate unit tests", "add test coverage".
  Make sure to use this skill whenever the user asks to generate tests,
  add test coverage, or create unit tests for a PR.
---

# Code Review Test Generation

Generate unit tests for newly added business logic in a PR to improve code coverage.

## Trigger conditions

Trigger when **all** of the following conditions hold:
1. `changed_files` includes business-logic files (not `test_*.py`/`*_test.*`/`*.test.*`/`*.spec.*`)
2. `additions > 20` (more than 20 added lines)
3. The diff adds function or method definitions (`def ` / `function ` / `const.*=>` / `class `)

## Input

- `diff`: PR code changes from `get_pull_request_files`
- `framework_info`: test-framework information from `detect_test_framework`
- `owner/repo`: repository identifier
- `pr_number`: pull-request number

## Analysis steps

### Step 1: Identify new functions/methods

Extract all added function/method definitions (lines starting with `+`) from the diff:

```
Python:  def function_name(...)
JS/TS:   function name(...) | const name = (...) => | async name(...)
Java:    public/private/protected returnType methodName(...)
Go:      func functionName(...)
```

### Step 2: Analyze code paths

For each new function, identify paths that need tests:

1. **Happy path**: the function's main behavior
2. **Boundary conditions**: null, zero, maximum, and minimum values
3. **Error paths**: invalid input and exception scenarios
4. **Conditional branches**: each branch in `if/else`, `try/except`, and `switch`

### Step 3: Generate test code

Choose a template using `framework_info.primary_framework`; see `references/test-patterns.md`.

#### Prompt structure

```
You are a test engineer. Generate unit tests for the following new code.

## New code
{diff_additions}

## Test framework
{framework}: {version}

## Requirements
1. Cover happy paths, boundary conditions, and error paths
2. Give each test a clear name describing its scenario
3. Use standard {framework} assertions
4. Mock external dependencies (databases, HTTP requests, and the filesystem)
5. Test file path: {test_file_path}

## Existing tests (if any)
{existing_tests}

Output format:
```json
{
  "test_file_path": "tests/test_xxx.py",
  "test_code": "complete test file contents",
  "test_count": number,
  "coverage_summary": "brief description of the covered scenarios"
}
```
```

### Step 4: Choose the test file path

| Language | Original file | Test file path |
|------|---------|------------|
| Python | `src/services/user.py` | `tests/test_user.py` |
| Python | `app/utils/helpers.py` | `tests/utils/test_helpers.py` |
| JavaScript | `src/utils/format.js` | `src/utils/format.test.js` |
| TypeScript | `src/api/users.ts` | `src/api/users.spec.ts` |
| Go | `pkg/user/service.go` | `pkg/user/service_test.go` |

### Step 5: Submit the test file

Submit the tests in the fix PR, together with automatic fixes, or create a separate test PR:

```
# Read the existing test file first, if present
file_info = get_file_contents(owner, repo, test_file_path, branch=fix_branch)

# Write the test file
create_or_update_file(
  owner=owner, repo=repo,
  path=test_file_path,
  content=test_code,
  sha=file_info.sha if file_info else None,  # sha is required for updates
  message=f"test: add unit tests for PR #{pr_number} changes",
  branch=fix_branch
)
```

## Output

```
## Generated Unit Tests

**Test framework**: {framework}
**Generated file**: {test_file_path}
**Test count**: {test_count}

### Covered scenarios
{coverage_summary}

### Test file added to fix PR #{fix_pr_number}
```

## Notes

1. **Do not modify business code**: generate test files only; leave the code under test unchanged
2. **Preserve idempotency**: append new cases to existing test files instead of overwriting them
3. **Mock external dependencies**: databases, HTTP, and filesystem operations must be mocked so tests do not depend on the external environment
4. **Test naming**: use `test_<function_name>_<scenario>`

Read `references/test-patterns.md` for language-specific test templates.
