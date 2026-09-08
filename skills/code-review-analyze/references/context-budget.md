# Context Budget — Token Budgets and Truncation

## Token allocation

Total budget: **32,000 tokens**

```
┌─────────────────────────────────────────────────────┐
│ Token budget allocation                              │
├──────────────────────┬──────────┬───────────────────┤
│ Section              │ Budget   │ Description         │
├──────────────────────┼──────────┼───────────────────┤
│ System Prompt        │ 3,000    │ Fixed               │
│ PR metadata          │ 1,000    │ Title/description   │
│ Memory rules         │ 3,000    │ Team-rule summary   │
│ Code diffs           │ 20,000   │ Truncate by priority│
│ Security alerts      │ 2,000    │ Security-scan results│
│ Commit history       │ 1,000    │ Latest 5-10 commits │
│ Previous turns       │ 2,000    │ Conversation context│
└──────────────────────┴──────────┴───────────────────┘
```

## File priorities

### Priority 1: Security-critical files (no truncation)

Path patterns:
```
*/auth/*
*/security/*
*authentication*
*authorization*
*permission*
*access_control*
*secret* (excluding test files)
*credential* (excluding test files)
```

Handling: include the full diff and complete file contents, fetched with `get_file_contents`.

### Priority 2: Business-logic files (partial truncation)

Path patterns:
```
*/views/*
*/controllers/*
*/handlers/*
*/models/*
*/services/*
*/api/*
*.py (excluding tests)
*.js (excluding tests)
*.ts (excluding tests)
*.go (excluding tests)
```

Handling: include files in ascending order of changed-line count; truncate when the budget is exceeded.

### Priority 3: Low-priority files (skip first)

Path patterns:
```
test_*.py
*_test.py
*.test.js
*.spec.ts
*/tests/*
*/test/*
*.md
*.txt
*.json (configuration, not business logic)
package-lock.json
yarn.lock
*.lock
```

Handling: include when sufficient budget remains; otherwise skip.

## Truncation algorithm

```python
def allocate_diff_budget(files, budget=20000):
    p1_files = [f for f in files if is_priority_1(f)]
    p2_files = [f for f in files if is_priority_2(f)]
    p3_files = [f for f in files if is_priority_3(f)]

    result = []
    remaining = budget

    # Step 1: Include all P1 files without truncation
    for f in p1_files:
        tokens = estimate_tokens(f.patch + f.full_content)
        result.append({"file": f, "truncated": False})
        remaining -= tokens

    # Step 2: Include P2 files in ascending order of changed-line count
    p2_sorted = sorted(p2_files, key=lambda f: f.additions + f.deletions)
    for f in p2_sorted:
        tokens = estimate_tokens(f.patch)
        if remaining >= tokens:
            result.append({"file": f, "truncated": False})
            remaining -= tokens
        elif remaining >= 500:  # Include at least 500 tokens
            truncated_patch = truncate_to_tokens(f.patch, remaining)
            result.append({"file": f, "truncated": True, "patch": truncated_patch})
            remaining = 0
            break
        else:
            result.append({"file": f, "truncated": True, "patch": "[TRUNCATED: insufficient budget]"})

    # Step 3: Allocate remaining budget to P3 files
    for f in p3_files:
        tokens = estimate_tokens(f.patch)
        if remaining >= tokens:
            result.append({"file": f, "truncated": False})
            remaining -= tokens
        else:
            result.append({"file": f, "truncated": True, "patch": "[SKIPPED: low priority, insufficient budget]"})

    return result
```

## Token estimates

Rough estimates for budget control:
- 1 token ≈ 4 English characters
- 1 token ≈ 2 Chinese characters
- 1 line of code ≈ 10-20 tokens

```python
def estimate_tokens(text: str) -> int:
    return len(text) // 4  # Rough estimate
```

## Truncation markers

When a file is truncated, append the following to the diff:

```
[... TRUNCATED: showing the first {shown_lines} of {total_lines} lines.
Full file path: {filename}
Reason: token budget limit ({used}/{budget} used)]
```

## Concurrent requests

Issue GitHub API requests concurrently without waiting for the preceding request:

```python
import asyncio

async def collect_data(owner, repo, pr_number, files_to_review):
    tasks = [
        get_pull_request(owner, repo, pr_number),
        get_pull_request_files(owner, repo, pr_number),
        list_commits(owner, repo, pr_number),
        get_memory_rules(),
    ]

    # Execute concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Also fetch complete contents for security-critical files
    security_files = [f for f in results[1] if is_priority_1(f)]
    if security_files:
        content_tasks = [
            get_file_contents(owner, repo, f.filename, ref=pr_head_sha)
            for f in security_files
        ]
        file_contents = await asyncio.gather(*content_tasks)

    return assemble_analysis_data(results, file_contents)
```
