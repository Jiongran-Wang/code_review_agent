# Candidate family 1: asof_latest_observation

Human validation: PENDING

Clean case: 7b880c32f492

Defect case: 8ccc0d9c72a5

## Contract

asof_value(observations, timestamp): observations are [time, value] pairs sorted by unique increasing finite numeric time; values and timestamp are finite numbers. Return the value at the latest time <= timestamp, or None if there is no eligible observation.

## Base

```python
def asof_value(observations, timestamp):
    for time, value in reversed(observations):
        if time <= timestamp:
            return value
    return None
```

## Clean refactor

```python
def asof_value(observations, timestamp):
    eligible = [pair for pair in observations if pair[0] <= timestamp]
    if not eligible:
        return None
    return eligible[-1][1]
```

## Buggy refactor

```python
def asof_value(observations, timestamp):
    eligible = [pair for pair in observations if pair[0] <= timestamp]
    if not eligible:
        return None
    return eligible[0][1]
```

## Proposed label

Returns the oldest eligible quote instead of the latest, yielding stale values whenever multiple observations precede the query time.

## Setup checks

```python

```

## Regression checks

```python
assert m.asof_value([[1, 10], [3, 30]], 2) == 10
assert m.asof_value([], 2) is None
```

## Trigger checks

```python
assert m.asof_value([[1, 10], [3, 30], [5, 50]], 4) == 30
assert m.asof_value([[1, 10], [3, 30]], 3) == 30
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
