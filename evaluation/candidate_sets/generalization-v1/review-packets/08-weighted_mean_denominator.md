# Candidate family 8: weighted_mean_denominator

Human validation: PENDING

Clean case: ce3221263449

Defect case: 0573896e2ef2

## Contract

weighted_mean(values, weights): equally sized nonempty lists of finite numbers; weights are nonnegative and their sum is positive. Return sum(value * weight) / sum(weights). Do not mutate either input.

## Base

```python
def weighted_mean(values, weights):
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)
```

## Clean refactor

```python
def weighted_mean(values, weights):
    weighted_total = sum(v * w for v, w in zip(values, weights))
    denominator = sum(weights)
    return weighted_total / denominator
```

## Buggy refactor

```python
def weighted_mean(values, weights):
    weighted_total = sum(v * w for v, w in zip(values, weights))
    denominator = len(weights)
    return weighted_total / denominator
```

## Proposed label

Dividing by the number of weights rather than their sum mis-scales a weighted mean with non-unit total weight.

## Setup checks

```python

```

## Regression checks

```python
assert m.weighted_mean([10, 20], [1, 1]) == 15
```

## Trigger checks

```python
assert m.weighted_mean([10, 20], [1, 3]) == 17.5
assert m.weighted_mean([10, 20], [2, 6]) == 17.5
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
