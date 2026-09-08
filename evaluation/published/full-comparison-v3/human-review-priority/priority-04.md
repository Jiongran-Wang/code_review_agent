# Priority review 4: review-0010

Case: e33a2e9207b7

## Contract

is_expired(now, expires_at): timestamps use the same unit; validity ends exactly at expires_at.

## Base source

```python
def is_expired(now, expires_at):
    return now >= expires_at
```

## Head source

```python
def is_expired(now, expires_at):
    remaining = expires_at - now
    return remaining <= 0
```

## Reference issue(s), subject to your review

[]

## Final output

```json
{"decision":"REQUEST_CHANGES","findings":[{"file":"module.py","line":2,"description":"The change from `return now >= expires_at` to `return remaining <= 0` alters the expiration logic. The original logic correctly allowed for equality, while the new logic does not."}]}
```

## Submitted reviews

The refactor of the `is_expired` function introduces a logical defect. The original implementation correctly returned `true` when `now` is equal to `expires_at`, indicating that the item is still valid until the exact expiration time. The new implementation, however, returns `false` in this case, which incorrectly indicates that the item is expired at the exact expiration time. This change alters the intended behavior of the function, leading to potential issues in any logic relying on this expiration check.

Inline comments:

```json
[
  {
    "path": "module.py",
    "line": 2,
    "body": "The change from `return now >= expires_at` to `return remaining <= 0` alters the expiration logic. The original logic correctly allowed for equality, while the new logic does not."
  }
]
```

## Assistant decision (completed; human validation pending)

Reviewer: Codex (AI assistant; not an independent human reviewer).

Distinct claims and judgments:

- **f1: unmatched defect claim.** The refactor preserves equality; the review alleges an incorrect base/head difference.

Exact supporting evidence:

For same-unit numeric timestamps, expires_at-now <= 0 is equivalent to now >= expires_at. At now=10, expires_at=10, remaining is 0 and both versions return True. The stored execution also reports True for both revisions at equality. The claim that the new code returns False contradicts the code and tool observations.

Normalization changes:

Merge final, submitted-body and inline versions of the same equality allegation. Keep it as a false positive; do not delete it because the review is wrong.

Gold or contract concerns:

The clean label is supported for the intended numeric-timestamp domain. The contract could explicitly name supported numeric types in a future dataset; the present allegation concerns equality and is false for its actual numeric examples. The review also confuses True meaning expired with still valid.
