# Triage Rules — Detailed Classification Rules

## Hard rules

### HR-001: Oversized PR (> 500 lines)

**Calculation**: `sum(file.additions + file.deletions for file in pr_files)`

**Edge cases**:
- Exclude generated files (`*_generated.go`, `*.pb.go`, `schema.graphql`) from the line count
- Exclude lock files (`package-lock.json`, `yarn.lock`, `Pipfile.lock`) from the line count
- Exclude migration files (`*/migrations/*.sql`) from the line count

**Handling**: return `human_required`, with `skip_reason = "PR changes {n} lines, exceeding the automatic-review threshold of 500 lines"`

### HR-002：Breaking Change

**Keywords** (case-insensitive):
- Title: `breaking change`, `BREAKING`, `[BREAKING]`, `breaking:`
- Description: `## Breaking Changes`, `BREAKING CHANGE:`, `⚠️ breaking`

**Handling**: return `human_required`, with `skip_reason = "PR contains breaking changes; human assessment of the impact is required"`

### HR-003: RFC / design document

**Keywords**:
- Title prefixes: `[RFC]`, `RFC:`, `RFC -`, `[Design]`, `[Proposal]`

**Handling**: return `human_required`, with `skip_reason = "This PR is an RFC/design proposal requiring team discussion"`

### HR-004: Security-critical files (3+)

**Security-critical path patterns** (one point for each match):
```
auth/*, authentication*, authorization*  → security_score += 1
security/*, permission*, access_control* → security_score += 1
secret*, credential*, password*, token*  → security_score += 1 (excluding test files)
payment/*, billing*, checkout*           → security_score += 1
```

**Handling**: `security_score >= 3` → return `human_required`

### HR-005：Draft PR

**Detection**: `pr.draft == true`

**Handling**: return `human_required`, with `skip_reason = "PR is a draft and is not yet complete"`

---

## LLM classification prompt

### Construct the input

```python
file_list = "\n".join([
    f"- {f.filename} (+{f.additions}/-{f.deletions})"
    for f in pr_files[:20]  # Up to 20 files
])

memory_summary = memory_rules[:500]  # First 500 characters
```

### Output fields

| Field | Type | Description |
|------|------|------|
| `review_type` | `"auto"\|"human_required"` | Classification result |
| `confidence` | `float [0,1]` | Confidence; force human_required when < 0.6 |
| `focus_areas` | `string[]` | Areas needing attention |
| `files_to_review` | `string[]` | Prioritized files, up to 10 |
| `estimated_complexity` | `"simple"\|"moderate"\|"complex"` | Complexity assessment |
| `skip_reason` | `string\|null` | Reason for human_required |

### Complexity criteria

| Complexity | Conditions |
|--------|------|
| simple | < 100 changed lines, one feature, no cross-module dependencies |
| moderate | 100-300 changed lines, 2-3 modules, test files present |
| complex | > 300 changed lines, multiple modules, database or API changes |

---

## Edge cases

### PR without a description
- Continue classification, adding `"documentation"` to focus_areas
- Suggest adding a PR description in the review

### Test-only changes
- `review_type = "auto"`
- `focus_areas = ["test_quality"]`
- `estimated_complexity = "simple"`

### Documentation-only changes
- `review_type = "auto"`
- `focus_areas = ["documentation"]`
- `estimated_complexity = "simple"`

### Configuration-only changes
- Check for security-related configuration, such as CORS, CSP, or authentication settings
- If present, add `"security"` to `focus_areas`
- Otherwise, set `estimated_complexity = "simple"`
