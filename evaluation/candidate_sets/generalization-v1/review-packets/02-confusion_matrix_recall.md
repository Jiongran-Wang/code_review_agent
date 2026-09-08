# Candidate family 2: confusion_matrix_recall

Human validation: PENDING

Clean case: 221540e5c718

Defect case: 6f17cd1fc93d

## Contract

positive_recall(matrix): a 2x2 matrix of nonnegative integer counts, with rows=true class and columns=predicted class, ordered negative then positive. At least one actual positive exists. Return TP / (TP + FN).

## Base

```python
def positive_recall(matrix):
    return matrix[1][1] / (matrix[1][0] + matrix[1][1])
```

## Clean refactor

```python
def positive_recall(matrix):
    true_positive = matrix[1][1]
    false_negative = matrix[1][0]
    return true_positive / (true_positive + false_negative)
```

## Buggy refactor

```python
def positive_recall(matrix):
    true_positive = matrix[1][1]
    false_negative = matrix[0][1]
    return true_positive / (true_positive + false_negative)
```

## Proposed label

Reads false positives instead of false negatives, computing precision rather than recall and potentially dividing by zero despite actual positives.

## Setup checks

```python

```

## Regression checks

```python
assert m.positive_recall([[5, 0], [0, 4]]) == 1
```

## Trigger checks

```python
assert m.positive_recall([[8, 2], [3, 7]]) == 0.7
assert m.positive_recall([[8, 0], [3, 0]]) == 0
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
