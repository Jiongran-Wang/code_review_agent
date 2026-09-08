---
name: code-review-triage
description: |
  Classify GitHub PRs to decide whether automatic review is appropriate or human intervention is required.
  Internal skill called by code-review. Also triggered independently by:
  "classify this PR", "should this PR be auto-reviewed", "triage PR #N",
  "does this PR need human review", "classify a PR", "assess PR complexity".
  Make sure to use this skill whenever the user asks to classify, triage,
  or assess whether a PR needs human review.
---

# Code Review Triage

Quickly classify a PR and choose automatic review or human intervention.

## Input

- `owner/repo`: repository identifier
- `pr_number`: pull-request number
- Memory-rule summary (optional, provided by code-review-memory)

## Workflow

### Step 1: Fetch PR metadata (0 LLM calls)

Call concurrently:
- `mcp__github__get_pull_request`: fetch title, description, and status
- `mcp__github__get_pull_request_files`: fetch the changed-file list

### Step 2: Check hard rules (0 LLM calls)

If any condition below holds, immediately return `human_required` and skip LLM classification:

| Rule | Condition | Reason |
|------|------|------|
| Oversized PR | Changed lines > 500 | Poor automatic-review effectiveness |
| Breaking Change | Title/description contains "breaking change" or "BREAKING" | Broad impact requiring human assessment |
| RFC/design document | Title contains "RFC", "[RFC]", or "design doc" | Requires architectural discussion |
| Security-critical files | Changes involve 3+ security-critical files | Security changes require human confirmation |
| Draft PR | PR is a draft | Work is incomplete |

**Counting security-critical files**: count **files**, not pattern groups. Each file matching any pattern below counts once:
- `*/auth/*`、`*authentication*`、`*authorization*`
- `*/security/*`、`*permission*`、`*access_control*`
- `*secret*`, `*credential*`, `*password*`, `*token*` (exclude paths containing `test` or `mock`)

Example: `auth/login.py` (1) + `security/permissions.py` (1) + `utils/token_helper.py` (1) = 3 → human_required

### Step 3: LLM classification (1 LLM call)

If no hard rule triggers, call the LLM for semantic classification.

**Prompt structure**:
```
You are a code-review classifier. Decide whether the following PR can be reviewed automatically.

PR title: {title}
PR description: {description}
Changed files: {file_list}
Team-rule summary: {memory_rules_summary}

Output JSON:
{
  "review_type": "auto" | "human_required",
  "confidence": 0.0-1.0,
  "focus_areas": ["security", "style", "logic", "performance"],
  "files_to_review": ["prioritized file paths"],
  "estimated_complexity": "simple" | "moderate" | "complex",
  "skip_reason": null | "reason"
}

Criteria for human_required:
- Refactoring core business logic
- Complex dependency changes across modules
- Changes affecting the database schema
- Changes to third-party integrations
- Automatically downgrade when confidence < 0.6
```

**Confidence handling**:
- confidence < 0.6 → force `review_type = "human_required"` and `skip_reason = "Insufficient confidence; human confirmation recommended"`

### Step 4: Output ReviewPlan

```json
{
  "review_type": "auto",
  "focus_areas": ["security", "style"],
  "files_to_review": ["app/views.py", "app/models.py"],
  "estimated_complexity": "simple",
  "skip_reason": null,
  "hard_rule_triggered": false,
  "confidence": 0.85
}
```

## Output format

Show the classification result:

```
## PR Triage Results

**PR**: #{pr_number} - {title}
**Classification**: ✅ Automatic review | ⚠️ Human intervention required
**Complexity**: simple/moderate/complex
**Focus areas**: security, style
**Prioritized files**:
  - app/views.py
  - app/models.py

{If human_required: "Skip reason: {skip_reason}"}
```

Read `references/triage-rules.md` for detailed rules and edge cases.
