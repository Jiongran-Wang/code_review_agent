# Code Review Checklist

Complete code-review checklist, ordered by priority.

## 🔴 Security — Required

### SQL injection
- [ ] All database queries use parameterization or an ORM
- [ ] No SQL built with f-strings or string concatenation
- [ ] User input is validated and escaped

### XSS (cross-site scripting)
- [ ] User input is not rendered directly as HTML
- [ ] Template-engine autoescaping is used
- [ ] Uses of `innerHTML`/`dangerouslySetInnerHTML` are reviewed

### Authentication and authorization
- [ ] API endpoints have appropriate authentication checks
- [ ] Permissions are checked in the service layer, not only the UI
- [ ] No insecure direct object references (IDOR)

### Sensitive data
- [ ] No hardcoded passwords, API keys, or tokens
- [ ] Sensitive configuration is read from environment variables or a secrets manager
- [ ] Logs contain no sensitive information

### Dependency security
- [ ] New dependencies have no known high-severity vulnerabilities
- [ ] Dependency versions are pinned

---

## 🟠 Bugs and Logic — Important

### Null handling
- [ ] Potentially None/null variables are checked
- [ ] Array/list access has boundary checks
- [ ] External API responses have error handling

### Error handling
- [ ] Exceptions are caught and handled correctly
- [ ] Error messages do not expose internal implementation details
- [ ] Critical database operations are protected by transactions

### Concurrency and race conditions
- [ ] Shared resources have appropriate locking
- [ ] Database operations avoid race conditions
- [ ] Operations are idempotent and safe to retry

### Business logic
- [ ] Boundary conditions are considered: zero, negative, and very large values
- [ ] State-machine transitions are correct
- [ ] Calculations have no overflow risk

---

## 🟡 Style and Standards — Suggestions

### Naming
- [ ] Variable and function names clearly express intent
- [ ] Names follow language and project conventions
- [ ] Constants replace magic numbers

### Function design
- [ ] Functions have one responsibility, preferably ≤ 50 lines
- [ ] Parameter counts are reasonable, preferably ≤ 5
- [ ] Return types are consistent

### Comments and documentation
- [ ] Complex logic has explanatory comments
- [ ] Public APIs have documentation comments
- [ ] TODO/FIXME comments link to corresponding issues

### Test coverage
- [ ] New features have unit tests
- [ ] Boundary conditions are covered
- [ ] Test names describe their scenarios

---

## 🟢 Performance — Optional

### Database queries
- [ ] No N+1 queries
- [ ] Indexes are used appropriately
- [ ] Large datasets use pagination

### Caching
- [ ] Frequently read data has a caching strategy
- [ ] Cache invalidation is correct

### Resource management
- [ ] Files and connections are closed correctly
- [ ] Large files are processed as streams
- [ ] No memory-leak risk

---

## Scope of automatic fixes

The following issues can be fixed automatically:
- SQL injection: replace with parameterized queries
- Hardcoded secrets: read from environment variables
- Simple missing null checks
- Code-style issues: formatting

The following require manual handling:
- Business-logic errors
- Architectural issues
- Complex permission design
- Performance-optimization choices
