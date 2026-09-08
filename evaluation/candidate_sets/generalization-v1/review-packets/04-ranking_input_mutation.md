# Candidate family 4: ranking_input_mutation

Human validation: PENDING

Clean case: fa6de2b34ecd

Defect case: 72306f7547f4

## Contract

rank_scores(scores): scores is a list of finite numbers, possibly empty. Return a new list sorted descending and leave the caller input unchanged.

## Base

```python
def rank_scores(scores):
    return sorted(scores, reverse=True)
```

## Clean refactor

```python
def rank_scores(scores):
    ranked = list(scores)
    ranked.sort(reverse=True)
    return ranked
```

## Buggy refactor

```python
def rank_scores(scores):
    ranked = scores
    ranked.sort(reverse=True)
    return ranked
```

## Proposed label

Aliases the caller list before an in-place sort, mutating the input and returning the same list instead of an independent ranked copy.

## Setup checks

```python

```

## Regression checks

```python
assert m.rank_scores([3, 2, 1]) == [3, 2, 1]
assert m.rank_scores([]) == []
```

## Trigger checks

```python
scores = [1, 3, 2]
result = m.rank_scores(scores)
assert result == [3, 2, 1]
assert scores == [1, 3, 2]
assert result is not scores
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
