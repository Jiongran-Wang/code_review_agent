---
name: code-review-memory
description: |
  Manage the code-review knowledge graph: rules, known issue patterns, false positives, and fix templates.
  Internal skill called by other code-review skills. Also triggered independently by:
  "add review rule", "mark as false positive", "update code review memory",
  "show review rules", "add a review rule", "show known issue patterns", "show false positives",
  "update review rules", "manage the code-review knowledge base".
  Make sure to use this skill whenever the user mentions managing review rules,
  false positives, known patterns, or code review memory.
---

# Code Review Memory

Manage persistent storage and retrieval of code-review knowledge.

## Storage location

Store all data in `~/.claude/review_memory.jsonl`, with one JSON object per line.

## Data structure

Record format:
```json
{
  "type": "review_rule|known_pattern|false_positive|fix_template",
  "id": "unique-id",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "content": { ... }
}
```

See `references/memory-schema.md` for the detailed schema.

## Supported operations

### Queries (0 LLM calls)

**show rules** / **view rules**:
- Read `~/.claude/review_memory.jsonl`
- Display all entries grouped by type
- Use a table or list

**search `<keyword>`**：
- Match keywords against every record's content field
- Return the matching records

**get_all** (called by other skills):
- Return a summary of all rules, with ≤ 50 characters per entry
- Format the text for inclusion in an LLM prompt
- **Maximum 3,000 tokens** (approximately 12,000 characters): truncate in priority order `known_pattern > review_rule > false_positive > fix_template`, adding `[Truncated: {n} entries total, showing the first {m}]`

### Writes (0 LLM calls)

**add_rule `<description>`**：
```json
{
  "type": "review_rule",
  "content": {
    "description": "rule description",
    "severity": "error|warning|info",
    "category": "security|style|logic|performance",
    "language": "python|javascript|go|... (optional)",
    "example_bad": "problematic code example (optional)",
    "example_good": "correct code example (optional)",
    "source": "team_standard|incident|best_practice|manual",
    "tags": ["tag1", "tag2"]
  }
}
```

**add_pattern `<name>` `<description>`**：
```json
{
  "type": "known_pattern",
  "content": {
    "name": "SQL injection",
    "description": "Non-parameterized SQL query",
    "indicators": ["f-string SQL", "string concatenation in query"],
    "severity": "critical"
  }
}
```

**add_false_positive `<pattern>` `<reason>`**：
```json
{
  "type": "false_positive",
  "content": {
    "pattern": "hardcoded credentials in test_*.py",
    "reason": "Test files use mock credentials, not real secrets",
    "file_patterns": ["test_*.py", "*/tests/*", "*/migrations/*"]
  }
}
```

**add_template `<name>` `<fix_code>`**：
```json
{
  "type": "fix_template",
  "content": {
    "name": "Parameterized SQL query",
    "problem": "SQL injection",
    "before": "cursor.execute(f'SELECT * FROM users WHERE id={id}')",
    "after": "cursor.execute('SELECT * FROM users WHERE id=%s', (id,))"
  }
}
```

## Execution steps

1. Parse the requested operation (show/search/add_rule/add_pattern/add_false_positive/add_template)
2. Read `~/.claude/review_memory.jsonl`; create an empty file if it does not exist
3. Perform the corresponding CRUD operation
4. Write the file by appending or rewriting
5. Confirm the result

## Built-in defaults

On first use, initialize an empty file with these defaults, including complete created_at/updated_at fields:

```json
{"type":"known_pattern","id":"builtin-1","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","content":{"name":"SQL injection","description":"SQL queries built with string concatenation or f-strings","severity":"critical","indicators":["f\"SELECT","f'SELECT","+ \" WHERE","+ ' WHERE"]}}
{"type":"known_pattern","id":"builtin-2","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","content":{"name":"Hardcoded secrets","description":"API keys, passwords, or tokens embedded directly in code","severity":"critical","indicators":["password =","api_key =","secret =","token ="]}}
{"type":"known_pattern","id":"builtin-3","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","content":{"name":"XSS vulnerability","description":"Unescaped user input rendered directly as HTML","severity":"high","indicators":["innerHTML =","dangerouslySetInnerHTML","render_template_string"]}}
{"type":"false_positive","id":"builtin-fp-1","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","content":{"pattern":"Hardcoded values in test files","reason":"Test files use mock data","file_patterns":["test_*.py","*_test.py","*/tests/*","*/test/*"]}}
{"type":"false_positive","id":"builtin-fp-2","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","content":{"pattern":"SQL in migration files","reason":"Raw SQL is normal in database migrations","file_patterns":["*/migrations/*","*migration*.py"]}}
```

Read `references/memory-schema.md` for the complete data-structure specification.
