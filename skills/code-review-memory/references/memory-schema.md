# Memory Schema — Knowledge Graph Data Structures

## Storage format

File: `~/.claude/review_memory.jsonl`
Format: one JSON object per line (JSONL)
Encoding: UTF-8

## Common fields

Every record must include:

```json
{
  "type": "review_rule|known_pattern|false_positive|fix_template",
  "id": "string (unique identifier)",
  "created_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime",
  "content": { ... }
}
```

**ID format**: `{type}-{timestamp}-{random4chars}`
Example: `review_rule-20260323-a1b2`

---

## Content schemas by type

### type: developer_profile

Developer profile tracking each developer's issue patterns across PRs.

```json
{
  "type": "developer_profile",
  "id": "developer_profile-20260421-a1b2",
  "created_at": "2026-04-21T10:00:00Z",
  "updated_at": "2026-04-21T10:00:00Z",
  "content": {
    "author": "github_username",
    "issue_history": [
      {"category": "security", "count": 3, "last_seen": "2026-04-01T00:00:00Z"},
      {"category": "style", "count": 8, "last_seen": "2026-04-15T00:00:00Z"}
    ],
    "strengths": ["high test coverage", "consistent naming"],
    "growth_areas": ["SQL security", "error handling"],
    "pr_count": 12,
    "last_updated": "2026-04-21T00:00:00Z"
  }
}
```

**Usage**: read the profile before reviewing and adapt comments: detailed explanations for beginners, concise suggestions for experienced developers.
**Tools**: `memory_get_developer_profile`, `memory_update_developer_profile`

---

### type: repo_pattern

Frequent issue patterns across PRs, used to generate repository health reports.

```json
{
  "type": "repo_pattern",
  "id": "repo_pattern-20260421-c3d4",
  "created_at": "2026-04-21T10:00:00Z",
  "updated_at": "2026-04-21T10:00:00Z",
  "content": {
    "repo": "owner/repo",
    "pattern_name": "high:security",
    "category": "security",
    "severity": "high",
    "occurrence_count": 7,
    "affected_files": ["services/*.py"],
    "first_seen": "2026-03-01T00:00:00Z",
    "last_seen": "2026-04-20T00:00:00Z",
    "trend": "increasing",
    "sample_description": "Unhandled exception"
  }
}
```

**Usage**: the `health-report` command reads these records to generate a Markdown health report.
**Tool**: `memory_aggregate_patterns`

---

### type: review_rule

A team code-standard rule.

```json
{
  "type": "review_rule",
  "id": "review_rule-20260323-a1b2",
  "created_at": "2026-03-23T10:00:00Z",
  "updated_at": "2026-03-23T10:00:00Z",
  "content": {
    "description": "All database queries must use parameterized queries",
    "severity": "error",
    "category": "security",
    "language": "python",
    "example_bad": "cursor.execute(f'SELECT * FROM users WHERE id={id}')",
    "example_good": "cursor.execute('SELECT * FROM users WHERE id=%s', (id,))",
    "source": "team_standard",
    "tags": ["sql", "security", "database"]
  }
}
```

**severity values**: `error | warning | info`
**category values**: `security | style | logic | performance | test`
**source values**: `team_standard | incident | best_practice | manual`

---

### type: known_pattern

A known issue pattern used for matching during review.

```json
{
  "type": "known_pattern",
  "id": "known_pattern-20260323-c3d4",
  "created_at": "2026-03-23T10:00:00Z",
  "updated_at": "2026-03-23T10:00:00Z",
  "content": {
    "name": "SQL injection",
    "description": "SQL queries built with string concatenation or f-strings",
    "severity": "critical",
    "category": "security",
    "indicators": [
      "f\"SELECT",
      "f'SELECT",
      "f\"INSERT",
      "f\"UPDATE",
      "f\"DELETE",
      "+ \" WHERE",
      "+ ' WHERE"
    ],
    "false_positive_rate": 0.05,
    "auto_fixable": true,
    "fix_template_id": "fix_template-builtin-sql-injection"
  }
}
```

**severity values**: `critical | high | medium | low`

---

### type: false_positive

A known false-positive rule identifying cases to skip during review.

```json
{
  "type": "false_positive",
  "id": "false_positive-20260323-e5f6",
  "created_at": "2026-03-23T10:00:00Z",
  "updated_at": "2026-03-23T10:00:00Z",
  "content": {
    "pattern": "Hardcoded credentials in test files",
    "reason": "Test files use mock data, not real secrets",
    "file_patterns": [
      "test_*.py",
      "*_test.py",
      "*/tests/*",
      "*/test/*",
      "conftest.py"
    ],
    "related_pattern_ids": ["known_pattern-builtin-hardcoded-secrets"],
    "confirmed_count": 12,
    "last_confirmed": "2026-03-20T15:30:00Z"
  }
}
```

---

### type: fix_template

An automatic code-fix template.

```json
{
  "type": "fix_template",
  "id": "fix_template-20260323-g7h8",
  "created_at": "2026-03-23T10:00:00Z",
  "updated_at": "2026-03-23T10:00:00Z",
  "content": {
    "name": "Parameterized SQL query (Python)",
    "problem_pattern": "SQL injection",
    "language": "python",
    "before_pattern": "cursor.execute(f'...{var}...')",
    "after_pattern": "cursor.execute('...%s...', (var,))",
    "before_example": "cursor.execute(f'SELECT * FROM users WHERE id={user_id}')",
    "after_example": "cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))",
    "regex_pattern": "cursor\\.execute\\(f['\"].*\\{.*\\}.*['\"]\\)",
    "usage_count": 5,
    "success_rate": 0.95
  }
}
```

---

## Query interface

### get_all (for reviews)

Return a formatted rule summary suitable for an LLM prompt:

```
## Team code standards
1. [error][security] All database queries must use parameterized queries
2. [warning][style] Functions must not exceed 50 lines

## Known issue patterns
1. [critical] SQL injection - indicators: f"SELECT, f'SELECT
2. [critical] Hardcoded secrets - indicators: password =, api_key =
3. [high] XSS vulnerability - indicators: innerHTML =

## False-positive exclusions
1. Hardcoded values in test files (test_*.py, *_test.py)
2. SQL in migrations (*/migrations/*)
```

### search (keyword search)

Match keywords case-insensitively against these fields in all records:
- `content.description`
- `content.name`
- `content.pattern`
- `content.tags` (array)

---

## File operations

### Read

```python
import json

def load_memory():
    try:
        with open("~/.claude/review_memory.jsonl", "r") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []
```

### Append

```python
def append_record(record):
    with open("~/.claude/review_memory.jsonl", "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

### Update (rewrite)

```python
def update_record(record_id, updated_content):
    records = load_memory()
    for i, r in enumerate(records):
        if r["id"] == record_id:
            records[i]["content"] = updated_content
            records[i]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            break

    with open("~/.claude/review_memory.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
```
