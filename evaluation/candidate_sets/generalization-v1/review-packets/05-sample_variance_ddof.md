# Candidate family 5: sample_variance_ddof

Human validation: PENDING

Clean case: ea9740de4878

Defect case: 359a5d763cfa

## Contract

sample_variance(values): at least two finite numeric observations. Return unbiased sample variance, dividing the sum of squared deviations by n - 1. Preserve the input.

## Base

```python
def sample_variance(values):
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / (len(values) - 1)
```

## Clean refactor

```python
def sample_variance(values):
    count = len(values)
    mean = sum(values) / count
    squared_error = sum((x - mean) ** 2 for x in values)
    return squared_error / (count - 1)
```

## Buggy refactor

```python
def sample_variance(values):
    count = len(values)
    mean = sum(values) / count
    squared_error = sum((x - mean) ** 2 for x in values)
    return squared_error / count
```

## Proposed label

Dividing by n computes population variance instead of the required unbiased sample variance, underestimating nonzero sample variance.

## Setup checks

```python

```

## Regression checks

```python
assert m.sample_variance([3, 3, 3]) == 0
```

## Trigger checks

```python
assert m.sample_variance([1, 3]) == 2
assert m.sample_variance([2, 4, 6]) == 4
```

## Human review (pending)

- Is the contract clear and internally consistent? 
- Is the base correct under the stated preconditions? 
- Does the clean refactor preserve the contract? 
- Is the proposed defect introduced, and is the gold location accurate? 
- Do the checks use valid inputs and meaningful state/data setup? 
- Are additional defects missing from the labels? 
- Does this add a useful pattern beyond the original development data? 

Reviewer: 

Decision: 

Corrections and supporting reasoning: 
