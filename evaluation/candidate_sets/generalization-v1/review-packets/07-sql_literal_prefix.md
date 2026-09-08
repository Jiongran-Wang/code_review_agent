# Candidate family 7: sql_literal_prefix

Human validation: PENDING

Clean case: 9b6717ff20c3

Defect case: a0409ff2a79f

## Contract

prefix_users(connection, prefix): users has integer id and text name columns. Names and nonempty prefix use uppercase ASCII letters, digits, _, %, ! only. Return [(id,), ...] in ascending id order for names starting with the literal prefix; %, _ and ! in input are ordinary characters, not pattern operators.

## Base

```python
def prefix_users(connection, prefix):
    pattern = prefix.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
    return connection.execute("SELECT id FROM users WHERE name LIKE ? ESCAPE '!' ORDER BY id", (pattern,)).fetchall()
```

## Clean refactor

```python
def prefix_users(connection, prefix):
    escaped = prefix.replace('!', '!!').replace('%', '!%').replace('_', '!_')
    pattern = escaped + '%'
    query = "SELECT id FROM users WHERE name LIKE ? ESCAPE '!' ORDER BY id"
    return connection.execute(query, (pattern,)).fetchall()
```

## Buggy refactor

```python
def prefix_users(connection, prefix):
    escaped = prefix.replace('!', '!!').replace('%', '!%').replace('_', '!_')
    pattern = prefix + '%'
    query = "SELECT id FROM users WHERE name LIKE ? ESCAPE '!' ORDER BY id"
    return connection.execute(query, (pattern,)).fetchall()
```

## Proposed label

Drops LIKE escaping, so literal underscore and percent prefixes match unrelated names even though SQL parameters remain bound.

## Setup checks

```python
import sqlite3
connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE users (id INTEGER, name TEXT)')
connection.executemany('INSERT INTO users VALUES (?, ?)', [(1,'A_ONE'), (2,'AXONE'), (3,'BETA'), (4,'A%TWO'), (5,'A!THREE')])
```

## Regression checks

```python
assert m.prefix_users(connection, 'B') == [(3,)]
```

## Trigger checks

```python
assert m.prefix_users(connection, 'A_') == [(1,)]
assert m.prefix_users(connection, 'A%') == [(4,)]
assert m.prefix_users(connection, 'A!') == [(5,)]
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
