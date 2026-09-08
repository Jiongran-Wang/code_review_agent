---
name: code-review
description: |
  Automated code review for GitHub PRs: check code quality, scan for security vulnerabilities,
  review coding standards, and submit fix PRs for clear issues.
  Triggers: PR review, code review, review PR #N, check this PR,
  code checks, security scans, automatic code fixes, or help reviewing a PR.
  Keywords: PR, pull request, review, code review, security vulnerability, automatic fix, code check.
  Make sure to use this skill whenever the user mentions reviewing a PR,
  checking code quality, scanning for security issues, or auto-fixing code,
  even if they don't explicitly say "code review".
---

# Code Review

Main entry point for the automated code-review system. Route to the subskills to complete the review workflow.

## Quick start

**Usage**: `/code-review owner/repo PR #42`
**Or**: ask "Please review github.com/owner/repo/pull/42"

## Workflow overview

```
User input
  ↓
[Step 1] Parse input → extract owner/repo + pr_number
  ↓
[Step 2] /code-review-triage → ReviewPlan
  ↓ human_required?
  ├── YES → Add an explanatory PR comment → End
  └── NO ↓
[Step 3] /code-review-analyze → AnalysisData
  ↓
[Step 4] /code-review-act → Review + optional fix PR
  ↓
[Step 5] /code-review-memory → Update the knowledge graph
  ↓
Output the review summary
```

## Step 1: Parse input

Extract the following from the user's input:
- `owner`: repository owner (user or organization)
- `repo`: repository name
- `pr_number`: pull-request number

Supported formats:
- `owner/repo #42`
- `owner/repo PR 42`
- `github.com/owner/repo/pull/42`
- `https://github.com/owner/repo/pull/42`

If parsing fails, ask the user:
```
Please provide the PR as: owner/repo #PR_NUMBER
For example: anthropics/claude-code #123
```

## Step 2: Triage

Call `/code-review-triage` with:
- `owner/repo`
- `pr_number`

**If it returns `human_required`**:
```python
mcp__github__add_issue_comment(
  owner=owner,
  repo=repo,
  issue_number=pr_number,
  body=f"""## 🤖 Automatic Review Skipped

**Reason**: {skip_reason}

This PR requires human review for the following reasons:
- {human_required_details}

Please ask a team member to review the code manually."""
)
```
End the workflow and show the user why the review was skipped.

## Step 3: Collect data

Call `/code-review-analyze` with:
- `owner/repo`
- `pr_number`
- `files_to_review` from triage
- `focus_areas` from triage

## Step 4: Review and act

Call `/code-review-act` with:
- `analysis_data` from analyze
- `review_plan` from triage
- `owner/repo`
- `pr_number`

## Step 5: Update memory

Call `/code-review-memory` to update the knowledge graph. code-review-act calls this internally; no additional step is needed.

## Final output format

```
## ✅ Code Review Complete

**Repository**: owner/repo
**PR**: #42 - {pr_title}
**Author**: @{author}

### Review results
- **Decision**: ✅ APPROVE | 🔄 REQUEST_CHANGES | 💬 COMMENT
- **Issues found**: {n}
  - 🔴 Critical: {n}
  - 🟠 High: {n}
  - 🟡 Medium: {n}
  - 🟢 Low: {n}

### Automatic fixes
{With fixes: "Created fix PR: #{fix_pr_number}" | Without fixes: "No automatically fixable issues"}

### Summary
{review_summary}
```

## References

- `references/review-checklist.md`: complete checklist for security, standards, logic, and performance
- `references/escalation-rules.md`: detailed human-escalation rules

## Subskills

| Skill | Responsibility | LLM calls |
|-------|------|----------|
| `code-review-triage` | PR classification | 1 |
| `code-review-analyze` | Data collection | 0 |
| `code-review-act` | Review and fixes | 1 |
| `code-review-memory` | Knowledge graph | 0 |

**Total: ≤ 2 LLM calls per PR** (1 for triage + 1 for review)
