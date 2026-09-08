---
name: code-review-analyze
description: |
  Collect PR analysis data concurrently: diffs, security alerts, commit history, and memory rules.
  Internal skill called by code-review. It can also be triggered independently:
  "fetch PR data", "get PR diff and alerts", "analyze PR #N data",
  "get PR data", "collect PR analysis information", "get code changes and security alerts".
  Make sure to use this skill whenever the user asks to fetch or collect
  PR data, diff, security alerts, or commit history for analysis.
---

# Code Review Analyze

Collect all PR analysis data concurrently to prepare input for code-review-act. **0 LLM calls**.

## Input

- `owner/repo`: repository identifier
- `pr_number`: pull-request number
- `files_to_review`: prioritized file list from triage
- `focus_areas`: focus areas from triage

## Workflow

### Step 1: Collect data concurrently

Issue the following requests concurrently:

```
Concurrent task A: mcp__github__get_pull_request
  → Fetch PR metadata (title, description, author, base/head branches, head.sha)

Concurrent task B: mcp__github__get_pull_request_files
  → Fetch diffs for all changed files (patch field)

Concurrent task C: mcp__github__list_commits(owner, repo, sha=head_branch)
  → Fetch the head branch's commit history (up to 10 commits)
  → Note: list_commits accepts sha (a branch name or commit SHA), not a PR number
  → Obtain head_branch from task A's result (pr.head.ref)

Concurrent task D: code-review-memory get_all
  → Fetch team-rule summaries (review_rules + known_patterns + false_positives, up to 3000 tokens)
```

**Note**: task C depends on task A for the head branch name. Start A with the PR number and launch C after A returns. Alternatively, run A first, then B/C/D concurrently.

### Step 2: Fetch complete security-critical files

For files in `files_to_review` matching the following patterns, also retrieve the complete contents:
- `*/auth/*`、`*authentication*`、`*authorization*`
- `*/security/*`、`*permission*`

Call `mcp__github__get_file_contents` to fetch complete contents from the head branch.

### Step 3: Manage the token budget and truncate diffs

Total budget: **32,000 tokens**

| Section | Budget | Priority |
|------|------|--------|
| System Prompt | 3,000 | - |
| PR metadata | 1,000 | - |
| Memory rules | 3,000 | - |
| Code diffs | 20,000 | Truncate by priority |
| Security alerts | 2,000 | - |
| Commit history | 1,000 | - |
| Previous turns | 2,000 | - |

**Diff truncation strategy** (when total diffs exceed 20,000 tokens):

File priorities:
1. **Priority 1** (no truncation): security-critical files (auth/security/permission)
2. **Priority 2** (partial truncation): business-logic files (views/models/controllers)
3. **Priority 3** (skip first): tests, configuration, and documentation

Truncation algorithm:
1. Include complete diffs for all Priority 1 files
2. Allocate the remaining budget to Priority 2 files, ordered by changed-line count from smallest to largest
3. Include Priority 3 files if budget remains
4. Mark files exceeding the budget as `[TRUNCATED: filename, reason]`

### Step 3.5: Attempt to fetch security alerts (optional; ignore failures)

Call `mcp__github__get_pull_request_status` for CI status, including security-scan results.
If Code Scanning is not enabled, this step returns no alerts; set `security_alerts` to `[]`.

**Note**: the GitHub Code Scanning API (`list_code_scanning_alerts`) is unavailable in GitHub MCP.
Use PR status checks instead and extract security-related information from check runs.

### Step 4: Assemble AnalysisData

```json
{
  "pr_info": {
    "title": "...",
    "description": "...",
    "author": "...",
    "base_branch": "main",
    "head_branch": "feature/xxx",
    "changed_files_count": 5,
    "additions": 120,
    "deletions": 30
  },
  "diffs": [
    {
      "filename": "app/views.py",
      "status": "modified",
      "additions": 50,
      "deletions": 10,
      "patch": "...",
      "full_content": "...",
      "priority": 1,
      "truncated": false
    }
  ],
  "commits": [
    {"sha": "abc123", "message": "...", "author": "..."}
  ],
  "memory_rules": {
    "review_rules": "...",
    "known_patterns": "...",
    "false_positives": "..."
  },
  "token_usage": {
    "total_estimated": 18500,
    "budget": 32000,
    "truncated_files": []
  }
}
```

## Output

Show a data-collection summary:

```
## Data Collection Complete

**PR**: #{pr_number} - {title}
**Changed files**: {n} ({additions}+ / {deletions}-)
**Commits**: {n}
**Token usage**: {used}/{budget}
**Truncated files**: {truncated_files or "None"}
**Memory rules**: {rules_count} rules loaded
```

Read `references/context-budget.md` for token budgets and truncation algorithms.
