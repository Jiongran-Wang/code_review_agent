# Candidate family 6: scoped_permission_conjunction

Human validation: PENDING

Clean case: d2d495bdf5d0

Defect case: fa484b727b39

## Contract

can_access(same_tenant, has_read_permission): both arguments are booleans. Grant access only when the requester belongs to the same tenant AND has read permission; otherwise deny. Return a bool.

## Base

```python
def can_access(same_tenant, has_read_permission):
    if not same_tenant:
        return False
    return has_read_permission
```

## Clean refactor

```python
def can_access(same_tenant, has_read_permission):
    allowed = same_tenant and has_read_permission
    return allowed
```

## Buggy refactor

```python
def can_access(same_tenant, has_read_permission):
    allowed = same_tenant or has_read_permission
    return allowed
```

## Proposed label

OR grants access when only one required permission condition holds, permitting cross-tenant or unprivileged access.

## Setup checks

```python

```

## Regression checks

```python
assert m.can_access(True, True) is True
assert m.can_access(False, False) is False
```

## Trigger checks

```python
assert m.can_access(False, True) is False
assert m.can_access(True, False) is False
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
