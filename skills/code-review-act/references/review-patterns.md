# Review Patterns — Common Issues and Example Fixes

## 🔴 Security vulnerability patterns

### SQL injection

**Detection**: SQL built with f-strings or string concatenation

```python
# ❌ Problematic code
query = f"SELECT * FROM users WHERE id={user_id}"
cursor.execute(query)

# ✅ Corrected code
cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
```

**Django ORM version**:
```python
# ❌ Problematic code
User.objects.raw(f"SELECT * FROM users WHERE name='{name}'")

# ✅ Corrected code
User.objects.filter(name=name)
# Or
User.objects.raw("SELECT * FROM users WHERE name=%s", [name])
```

**Node.js version**:
```javascript
// ❌ Problematic code
db.query(`SELECT * FROM users WHERE id=${userId}`)

// ✅ Corrected code
db.query('SELECT * FROM users WHERE id = ?', [userId])
```

---

### Hardcoded secrets

**Detection**: secret strings embedded directly in code

```python
# ❌ Problematic code
API_KEY = "sk-1234567890abcdef"
DATABASE_PASSWORD = "mypassword123"

# ✅ Corrected code
import os
API_KEY = os.environ.get("API_KEY")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")
```

**Node.js version**:
```javascript
// ❌ Problematic code
const apiKey = "sk-1234567890abcdef"

// ✅ Corrected code
const apiKey = process.env.API_KEY
```

---

### XSS vulnerabilities

**Detection**: unescaped user input rendered as HTML

```javascript
// ❌ Problematic code
element.innerHTML = userInput

// ✅ Corrected code
element.textContent = userInput
// Or use DOMPurify
element.innerHTML = DOMPurify.sanitize(userInput)
```

**Python Flask version**:
```python
# ❌ Problematic code
return render_template_string(f"<h1>{user_input}</h1>")

# ✅ Corrected code
from markupsafe import escape
return render_template_string("<h1>{{ input }}</h1>", input=escape(user_input))
```

---

### Path traversal

**Detection**: user input used directly in file paths

```python
# ❌ Problematic code
with open(f"/uploads/{filename}") as f:
    return f.read()

# ✅ Corrected code
import os
safe_path = os.path.join("/uploads", os.path.basename(filename))
if not safe_path.startswith("/uploads/"):
    raise ValueError("Invalid path")
with open(safe_path) as f:
    return f.read()
```

---

## 🟠 Bug patterns

### Missing null checks

```python
# ❌ Problematic code
user = get_user(user_id)
print(user.name)  # user may be None

# ✅ Corrected code
user = get_user(user_id)
if user is None:
    raise ValueError(f"User {user_id} not found")
print(user.name)
```

**JavaScript version**:
```javascript
// ❌ Problematic code
const name = user.profile.name  // user or profile may be null

// ✅ Corrected code
const name = user?.profile?.name ?? 'Unknown'
```

---

### Unhandled exceptions

```python
# ❌ Problematic code
response = requests.get(url)
data = response.json()

# ✅ Corrected code
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.RequestException as e:
    logger.error(f"API request failed: {e}")
    raise
```

---

### N+1 queries

```python
# ❌ Problematic code
users = User.objects.all()
for user in users:
    print(user.profile.bio)  # Query the database on every iteration

# ✅ Corrected code
users = User.objects.select_related('profile').all()
for user in users:
    print(user.profile.bio)  # Use eagerly loaded data
```

---

## 🟡 Code-standard patterns

### Magic numbers

```python
# ❌ Problematic code
if retry_count > 3:
    return None

# ✅ Corrected code
MAX_RETRY_COUNT = 3
if retry_count > MAX_RETRY_COUNT:
    return None
```

### Overlong functions

```python
# ❌ Problematic code (function longer than 50 lines)
def process_order(order):
    # Validate
    # Calculate the price
    # Check inventory
    # Create records
    # Send notifications
    # ... 100 lines

# ✅ Corrected code (separate responsibilities)
def process_order(order):
    validate_order(order)
    price = calculate_price(order)
    check_inventory(order)
    record = create_order_record(order, price)
    notify_user(order, record)
    return record
```

---

## Review comment templates

### Security vulnerability comment

```markdown
🔴 **Security vulnerability: {vulnerability_type}**

**Issue**: {issue_description}

**Risk**: {potential_impact}

**Suggested fix**:
```{language}
{fix_code}
```

Reference: {documentation_link_optional}
```

### Bug Comment

```markdown
🟠 **Potential bug: {issue_type}**

**Issue**: {issue_description}

**Scenario**: when {trigger_condition}, {outcome}

**Suggestion**:
```{language}
{suggestion_code}
```
```

### Code-standard suggestion

```markdown
🟡 **Code-standard suggestion**

{suggestion_text}

```{language}
{example_code}
```
```
