# Coaching Guidelines — Comment Styles Based on Developer Profiles

## Core principle

Code review identifies issues and helps developers improve. Adapt comments to the developer's experience
so the review provides useful instruction rather than simply pointing out mistakes.

---

## Experience levels

| Level | Criterion | Comment style |
|------|------|-------------|
| Beginner | `pr_count < 5` | Friendly tone, detailed explanation, and sample code |
| Intermediate | `5 ≤ pr_count < 20` | Brief explanation and direction for a fix |
| Experienced | `pr_count ≥ 20` | Direct feedback without redundant explanation |

---

## Beginner example

**Issue**: SQL injection vulnerability

```
🔴 **Security vulnerability: SQL injection**

This query is built by concatenating strings. An attacker can craft input that executes arbitrary SQL commands.

**Why is this dangerous?**
If `user_id` comes from user input, an attacker could enter `1 OR 1=1` to bypass authorization checks.

**Fix**: use a parameterized query:
```python
# ❌ Unsafe
cursor.execute(f"SELECT * FROM users WHERE id={user_id}")

# ✅ Safe
cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
```

This is the standard Python DB-API approach; the database driver handles escaping. With SQLAlchemy,
use `session.query(User).filter(User.id == user_id)` to avoid writing raw SQL.
```

---

## Intermediate example

**Issue**: SQL injection vulnerability

```
🔴 **SQL injection**: `cursor.execute(f"...{user_id}...")` is vulnerable to injection.

Use a parameterized query: `cursor.execute("...%s...", (user_id,))`
```

---

## Experienced-developer example

**Issue**: SQL injection vulnerability

```
🔴 SQL injection (L42): replace the f-string with a parameterized query.
```

---

## Recurring-issue tracking

When a category in the developer's `issue_history` has `count > 3`, add development suggestions at the end of the review summary:

```
---
📈 **Development suggestions**

Your recent PR reviews include five security issues: three SQL injection findings and two hardcoded secrets.
Suggestions:
1. Scan Python code with `bandit` before submitting a PR (`pip install bandit && bandit -r .`)
2. Consult the team's security guidelines (link)
3. Consider a local pre-commit hook for automatic checks

Keep going! Addressing these patterns will make a noticeable improvement in code quality.
```

---

## Positive feedback

Recognize good practices as well as issues:

- Comprehensive tests → "👍 Thorough test coverage, including boundary conditions"
- Consistent naming → "Clear names that follow team conventions"
- Complete documentation → "Helpful docstrings that make future maintenance easier"

Positive feedback helps developers identify practices worth continuing and build good habits.

---

## Tone

1. **Focus on the code**: comment on the code, not the person. Say "This code..." instead of "You wrote..."
2. **Provide direction**: include a suggested fix for every issue
3. **Encourage appropriately**: end a beginner's PR review with a brief overall assessment
4. **Avoid dismissive wording**: say "Consider changing this to..." instead of "This is wrong"
