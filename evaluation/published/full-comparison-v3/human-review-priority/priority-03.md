# Priority review 3: review-0039

Case: bca9b18b8e18

## Contract

center(train, test): train is nonempty; subtract the training mean from both lists without fitting on test data.

## Base source

```python
def center(train, test):
    mean = sum(train) / len(train)
    return [x - mean for x in train], [x - mean for x in test]
```

## Head source

```python
def center(train, test):
    fitting_values = train + test
    offset = sum(fitting_values) / len(fitting_values)
    return [value - offset for value in train], [value - offset for value in test]
```

## Reference issue(s), subject to your review

[
  {
    "issue_id": "bca9b18b8e18:1",
    "file": "module.py",
    "line_start": 2,
    "line_end": 2,
    "category": "ml_data_leakage",
    "severity": "high",
    "description": "Fitting the centering offset on train plus test leaks held-out information into training features."
  }
]

## Final output

```json
{
  "decision": "REQUEST_CHANGES",
  "findings": [
    {
      "file": "module.py",
      "line": 2,
      "description": "The calculation of the mean is incorrect. The new implementation fits the mean on both train and test data, which violates the requirement to only fit on the training data."
    }
  ]
}
```

## Submitted reviews

## Assistant decision (completed; human validation pending)

Reviewer: Codex (AI assistant; not an independent human reviewer).

Distinct claims and judgments:

- **f1: strict match.** Explicitly identifies fitting the mean on train plus test and violating the training-only fitting requirement; that describes the prohibited data-leakage behavior.

Exact supporting evidence:

The contract says subtract the training mean without fitting on test data. Head line 2 sets fitting_values=train+test. The finding explicitly states that the new implementation fits on both datasets. For train=[1,3] and test=[100], base uses offset 2 while head uses 104/3; changing the test values changes the transformation of training values.

Normalization changes:

One final claim and no submitted review. Keep it as one semantic match; the exact word leakage is not required when the prohibited test-fitting behavior is explicitly described.

Gold or contract concerns:

No identified error in the contract or gold issue. This judgment credits the explicitly stated fitting violation without requiring a numerical example in the model output; the numerical illustration here is reviewer evidence, not text produced by the evaluated model.
