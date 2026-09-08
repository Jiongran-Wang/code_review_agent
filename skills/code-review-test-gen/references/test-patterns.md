# Test Patterns — Framework Templates and Best Practices by Language

## Python — pytest

### Basic structure

```python
import pytest
from unittest.mock import patch, MagicMock

# Module under test
from myapp.services.user import UserService


class TestUserService:
    """Unit tests for UserService."""

    def setup_method(self):
        """Initialize before each test."""
        self.service = UserService()

    def test_get_user_success(self):
        """Happy path: retrieve a user successfully."""
        user = self.service.get_user(user_id=1)
        assert user is not None
        assert user.id == 1

    def test_get_user_not_found(self):
        """Boundary condition: user does not exist."""
        with pytest.raises(UserNotFoundError):
            self.service.get_user(user_id=99999)

    def test_get_user_invalid_id(self):
        """Boundary condition: invalid ID."""
        with pytest.raises(ValueError):
            self.service.get_user(user_id=-1)

    def test_get_user_with_none_id(self):
        """Boundary condition: None value."""
        with pytest.raises(TypeError):
            self.service.get_user(user_id=None)

    @patch("myapp.services.user.database")
    def test_get_user_db_error(self, mock_db):
        """Error path: database error."""
        mock_db.query.side_effect = DatabaseError("Connection failed")
        with pytest.raises(ServiceError):
            self.service.get_user(user_id=1)
```

### Mock external dependencies

```python
# Mock the database
@patch("myapp.db.session")
def test_create_user(self, mock_session):
    mock_session.add.return_value = None
    mock_session.commit.return_value = None
    result = self.service.create_user(name="Alice", email="alice@example.com")
    assert result.name == "Alice"
    mock_session.add.assert_called_once()

# Mock HTTP requests
@patch("requests.get")
def test_fetch_external_data(self, mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": "value"}
    )
    result = self.service.fetch_data(url="https://api.example.com")
    assert result == {"data": "value"}

# Mock the filesystem
@patch("builtins.open", create=True)
def test_read_config(self, mock_open):
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = MagicMock(return_value=False)
    mock_open.return_value.read.return_value = '{"key": "value"}'
    config = self.service.read_config("/path/to/config.json")
    assert config["key"] == "value"
```

### Fixtures

```python
@pytest.fixture
def user_service():
    """Shared fixture."""
    service = UserService(db_url="sqlite:///:memory:")
    yield service
    service.cleanup()

@pytest.fixture
def sample_user():
    return {"id": 1, "name": "Alice", "email": "alice@example.com"}

def test_update_user(user_service, sample_user):
    user_service.create_user(**sample_user)
    result = user_service.update_user(1, name="Bob")
    assert result.name == "Bob"
```

---

## Python — unittest

```python
import unittest
from unittest.mock import patch, MagicMock


class TestUserService(unittest.TestCase):

    def setUp(self):
        self.service = UserService()

    def test_get_user_success(self):
        user = self.service.get_user(user_id=1)
        self.assertIsNotNone(user)
        self.assertEqual(user.id, 1)

    def test_get_user_not_found(self):
        self.assertRaises(UserNotFoundError, self.service.get_user, user_id=99999)

    def tearDown(self):
        self.service.cleanup()


if __name__ == "__main__":
    unittest.main()
```

---

## JavaScript — Jest

### Basic structure

```javascript
// user.service.test.js
const { UserService } = require('./user.service');

describe('UserService', () => {
  let service;

  beforeEach(() => {
    service = new UserService();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('getUser', () => {
    test('should return user when found', async () => {
      const user = await service.getUser(1);
      expect(user).toBeDefined();
      expect(user.id).toBe(1);
    });

    test('should throw UserNotFoundError when user does not exist', async () => {
      await expect(service.getUser(99999)).rejects.toThrow('User not found');
    });

    test('should throw TypeError when id is null', async () => {
      await expect(service.getUser(null)).rejects.toThrow(TypeError);
    });
  });
});
```

### Mock external dependencies

```javascript
// Mock the module
jest.mock('../database', () => ({
  query: jest.fn(),
}));

const db = require('../database');

test('should handle database error', async () => {
  db.query.mockRejectedValue(new Error('Connection failed'));
  await expect(service.getUser(1)).rejects.toThrow('Database error');
});

// Mock fetch
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ data: 'value' }),
  })
);

test('should fetch external data', async () => {
  const result = await service.fetchData('https://api.example.com');
  expect(result).toEqual({ data: 'value' });
  expect(fetch).toHaveBeenCalledWith('https://api.example.com');
});
```

---

## TypeScript — Jest + ts-jest

```typescript
// user.service.spec.ts
import { UserService } from './user.service';
import { UserNotFoundError } from './errors';

jest.mock('../database');
import { database } from '../database';

describe('UserService', () => {
  let service: UserService;

  beforeEach(() => {
    service = new UserService();
    jest.clearAllMocks();
  });

  it('should return user when found', async () => {
    const user = await service.getUser(1);
    expect(user).toBeDefined();
    expect(user.id).toBe(1);
  });

  it('should throw UserNotFoundError when user does not exist', async () => {
    await expect(service.getUser(99999)).rejects.toThrow(UserNotFoundError);
  });

  it('should handle database errors gracefully', async () => {
    (database.query as jest.Mock).mockRejectedValue(new Error('DB error'));
    await expect(service.getUser(1)).rejects.toThrow('Service error');
  });
});
```

---

## Go — testing package

```go
// user_service_test.go
package user

import (
    "testing"
    "errors"
)

func TestGetUser_Success(t *testing.T) {
    service := NewUserService(mockDB)
    user, err := service.GetUser(1)
    if err != nil {
        t.Fatalf("expected no error, got %v", err)
    }
    if user.ID != 1 {
        t.Errorf("expected user ID 1, got %d", user.ID)
    }
}

func TestGetUser_NotFound(t *testing.T) {
    service := NewUserService(mockDB)
    _, err := service.GetUser(99999)
    if !errors.Is(err, ErrUserNotFound) {
        t.Errorf("expected ErrUserNotFound, got %v", err)
    }
}

func TestGetUser_InvalidID(t *testing.T) {
    service := NewUserService(mockDB)
    _, err := service.GetUser(-1)
    if err == nil {
        t.Error("expected error for negative ID, got nil")
    }
}

// Table-driven tests
func TestGetUser_TableDriven(t *testing.T) {
    tests := []struct {
        name    string
        userID  int
        wantErr bool
    }{
        {"valid user", 1, false},
        {"user not found", 99999, true},
        {"negative id", -1, true},
        {"zero id", 0, true},
    }

    service := NewUserService(mockDB)
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            _, err := service.GetUser(tt.userID)
            if (err != nil) != tt.wantErr {
                t.Errorf("GetUser(%d) error = %v, wantErr %v", tt.userID, err, tt.wantErr)
            }
        })
    }
}
```

---

## General best practices

### Test naming

| Language | Format | Example |
|------|------|------|
| Python | `test_<func>_<scenario>` | `test_get_user_not_found` |
| JS/TS | `should <behavior> when <condition>` | `should throw error when user not found` |
| Go | `Test<Func>_<Scenario>` | `TestGetUser_NotFound` |

### Coverage targets

- New business logic: ≥ 80% line coverage
- Security-related code: ≥ 95% line coverage
- Utility functions: ≥ 90% line coverage

### Required scenarios

1. ✅ Happy path
2. ✅ Null/zero/None input
3. ✅ Boundary values (maximum and minimum)
4. ✅ Error/exception paths
5. ✅ Concurrency scenarios, if applicable

### Mocking principles

1. **Mock only external dependencies**: databases, HTTP, filesystem, and time
2. **Do not mock the code under test**
3. **Verify mock calls**: confirm correct arguments and call counts
4. **Reset mocks for each test** to prevent interference between tests
