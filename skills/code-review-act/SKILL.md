---
name: code-review-act
description: |
  Perform code review: analyze issues, submit review comments, and create fix PRs
  for issues that can be repaired automatically. Internal skill called by code-review; also triggered by:
  "review this code", "submit review for PR #N", "auto-fix PR issues",
  "create fix PR", "submit a code review", "automatically fix code", "review a PR and fix its issues",
  "submit review feedback on a PR".
  Make sure to use this skill whenever the user asks to review code,
  submit review comments, auto-fix issues, or create a fix PR.
---

# Code Review Act

Analyze the code and take action: submit a review and optionally create a fix PR.

## Input

- `analysis_data`: complete analysis data from code-review-analyze
- `review_plan`: ReviewPlan from code-review-triage
- `owner/repo`: repository identifier
- `pr_number`: pull-request number

## Phase 2.5: Read the developer profile

Before analyzing the PR, call `memory_get_developer_profile` to retrieve the author's review history:

```
memory_get_developer_profile(author=pr_info.author)
```

Adjust the review style based on the profile:
- **Beginner** (`pr_count < 5`): include detailed explanations and sample code, using a friendly, encouraging tone
- **Intermediate** (`5 ≤ pr_count < 20`): briefly explain the issue and how to fix it
- **Experienced** (`pr_count ≥ 20`): state the issue directly without unnecessary explanation
- **Recurring issues** (a category in `issue_history` has count > 3): include development suggestions in the review summary

## Phase 3: REVIEW analysis (1 LLM call)

### Prompt structure

```
You are a senior code reviewer. Perform a comprehensive code review of the following PR.

## PR information
{pr_info}

## Code changes
{diffs}

## Security alerts
{security_alerts}

## Team rules
{memory_rules}

## Commit history
{commits}

Identify issues in this priority order:
1. 🔴 Security vulnerabilities (SQL injection, XSS, hardcoded secrets, authorization bypass)
2. 🟠 Bugs (logic errors, null pointers, boundary conditions)
3. 🟡 Standards issues (naming, comments, code style)
4. 🟢 Performance improvement suggestions

Output JSON:
{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "security|bug|style|performance",
      "file": "file path",
      "line": line number (must be an actual changed line in the diff; otherwise use null),
      "description": "issue description",
      "suggestion": "suggested fix",
      "auto_fixable": true|false,
      "fix_code": "IMPORTANT: if auto_fixable=true, provide the COMPLETE corrected file contents, not a code snippet. If auto_fixable=false, use null."
    }
  ],
  "decision": "APPROVE|REQUEST_CHANGES|COMMENT",
  "summary": "overall assessment (2-3 sentences)",
  "confidence": 0.0-1.0
}

Note: auto_fixable may be true only for the following:
- SQL injection (with a clear replacement using parameterized queries)
- Hardcoded secrets (replace with os.environ.get())
- Simple missing null checks (add None/null checks)
- Formatting issues (without changing logic)
For issues with category=logic or category=architecture, auto_fixable must be false.
```

### Decision logic

| Condition | Decision |
|------|----------|
| Critical/high-severity security vulnerability | REQUEST_CHANGES |
| High-severity bug | REQUEST_CHANGES |
| Only medium/low-severity issues | COMMENT |
| No issues | APPROVE |
| confidence < 0.6 | Force downgrade to COMMENT |

### Automatic-fix criteria

**Automatically fixable** (`auto_fixable: true`):
- Clear security vulnerabilities: SQL injection or hardcoded secrets with an established fix pattern
- Formatting/standards issues: code-style changes that preserve business logic
- Simple bugs: clear missing null checks or boundary checks

**Not automatically fixable** (`auto_fixable: false`):
- Logic errors requiring business-domain understanding
- Architectural issues involving multi-file refactoring
- Ambiguous issues with more than one possible fix

## Phase 4: ACT execution (0 LLM calls)

### Branch A: Submit a GitHub review

Call `mcp__github__create_pull_request_review`:

```json
{
  "owner": "...",
  "repo": "...",
  "pull_number": 42,
  "event": "APPROVE|REQUEST_CHANGES|COMMENT",
  "body": "## Code Review Summary\n\n{summary}\n\n### Issues Found\n{issues_summary}",
  "comments": [
    {
      "path": "app/views.py",
      "line": 42,
      "body": "🔴 **Security vulnerability**: {description}\n\n**Suggestion**: {suggestion}\n\n```python\n{fix_code}\n```"
    }
  ]
}
```

### Branch B: Create a fix PR (only for auto_fixable issues)

**Preflight checks**: for each issue with `auto_fixable: true`, verify:
- `category` is neither `logic` nor `architecture` (force `auto_fixable: false` for these categories)
- `fix_code` is not empty

1. **Create a fix branch** from the original PR's head branch:
   ```
   mcp__github__create_branch(
     owner=owner,
     repo=repo,
     branch="auto-fix/pr-{pr_number}-{date}",
     from_branch=analysis_data.pr_info.head_branch  # Branch from the PR head
   )
   ```

2. **Read each file and write its fix**:
   For each issue with `auto_fixable: true`:
   ```
   # Step 2a: Read current contents and sha (create_or_update_file requires sha when updating a file)
   file_info = mcp__github__get_file_contents(
     owner=owner, repo=repo,
     path=issue.file,
     branch="auto-fix/pr-{pr_number}-{date}"
   )

   # Step 2b: Apply fix_code to the file
   # fix_code contains the complete corrected file, as required by the LLM prompt
   mcp__github__create_or_update_file(
     owner=owner, repo=repo,
     path=issue.file,
     content=issue.fix_code,          # Complete file contents
     sha=file_info.sha,               # The current file sha is required
     message="fix({category}): {issue.description}\n\nAuto-fix for PR #{pr_number}",
     branch="auto-fix/pr-{pr_number}-{date}"
   )
   ```

3. **Create the fix PR**:
   Read `references/fix-pr-template.md` for the title and body, then:
   ```
   mcp__github__create_pull_request(
     owner=owner, repo=repo,
     title="[Auto Fix] PR #{pr_number}: {issues_summary}",
     body="{fix_pr_body}",
     head="auto-fix/pr-{pr_number}-{date}",
     base=analysis_data.pr_info.head_branch  # Merge the fix PR into the original PR's feature branch
   )
   ```

### Branch C: Handle CRITICAL security vulnerabilities

If any security vulnerability has `severity: "critical"`:
1. Force the review decision to `REQUEST_CHANGES`
2. Add a `🚨 CRITICAL SECURITY ISSUE` warning at the top of the review body
3. Add a PR comment indicating that human confirmation is required:
   ```
   mcp__github__add_issue_comment(
     body="⚠️ **Human security review required**\n\nFound {n} critical security vulnerabilities. Automatic fixes have been created, but must be confirmed by a human before merging.\n\n{issues_list}"
   )
   ```

### Branch D: Update memory

Call `/code-review-memory` to update the knowledge graph:
- Add newly discovered issue patterns as `known_pattern`
- Add confirmed false positives as `false_positive`

### Branch E: Update the developer profile

After the review, call `memory_update_developer_profile`:

```
memory_update_developer_profile(
  author=pr_info.author,
  new_issues=[{"category": issue.category, "severity": issue.severity} for issue in issues],
  strengths=<strengths observed in this review, such as "comprehensive test coverage" or "consistent naming">,
  growth_areas=<areas for improvement, such as "SQL security" or "error handling">
)
```

### Branch F: Aggregate cross-PR patterns

After the review, call `memory_aggregate_patterns` to update repository-level issue statistics:

```
memory_aggregate_patterns(
  repo="{owner}/{repo}",
  issues=[{"category": issue.category, "severity": issue.severity,
           "file": issue.file, "description": issue.description}
          for issue in issues]
)
```

### Branch G: Generate tests when the conditions are met

**Trigger**: `changed_files` contains business-logic files (not `test_*.py`/`*_test.*`) and `additions > 20`

1. Call `detect_test_framework` to identify the project's test framework:
   ```
   detect_test_framework(owner=owner, repo=repo)
   ```

2. Identify code paths in newly added functions/methods that existing tests do not cover, including boundary and error paths

3. Generate tests in the project's framework and include them in the fix PR, or create a separate test PR

See `skills/code-review-test-gen/SKILL.md` for detailed test-generation instructions.

## Output

```
## Code Review Complete

**PR**: #{pr_number} - {title}
**Decision**: ✅ APPROVE | 🔄 REQUEST_CHANGES | 💬 COMMENT
**Issues found**: {total} (🔴 {critical} critical / 🟠 {high} high / 🟡 {medium} medium / 🟢 {low} low)
**Automatic fixes**: fix PR #{fix_pr_number} created for {auto_fixable_count} issues

### Main issues
{issues_list}

### Summary
{summary}
```

Read `references/review-patterns.md` for common issue patterns and example fixes.
Read `references/fix-pr-template.md` for fix-PR formatting requirements.
