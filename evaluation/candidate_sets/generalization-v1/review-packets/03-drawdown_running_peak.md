# Candidate family 3: drawdown_running_peak

Human validation: PENDING

Clean case: 43ef97578bb4

Defect case: b8074f37df14

## Contract

max_drawdown(values): a nonempty chronological sequence of finite positive portfolio values. Return the largest fractional fall from a peak seen at or before each observation; future peaks cannot be used for earlier observations.

## Base

```python
def max_drawdown(values):
    peak = values[0]
    worst = 0.0
    for value in values:
        if value > peak:
            peak = value
        worst = max(worst, (peak - value) / peak)
    return worst
```

## Clean refactor

```python
def max_drawdown(values):
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        decline = (peak - value) / peak
        worst = max(worst, decline)
    return worst
```

## Buggy refactor

```python
def max_drawdown(values):
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(values)
        decline = (peak - value) / peak
        worst = max(worst, decline)
    return worst
```

## Proposed label

Uses the full-series peak for earlier observations, introducing future information and overstating drawdown before a later peak.

## Setup checks

```python

```

## Regression checks

```python
assert m.max_drawdown([100, 80, 60]) == 0.4
```

## Trigger checks

```python
assert m.max_drawdown([100, 90, 120]) == 0.1
assert m.max_drawdown([100, 110, 120]) == 0
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
