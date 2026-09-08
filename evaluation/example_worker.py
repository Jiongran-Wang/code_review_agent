"""Execute audited fixture code with bounded JSON calls in a fresh process.

This is NOT a general sandbox for arbitrary Python. The hash gate and
declarative interface are essential; do not replace them with model-written code.
"""
import ast
import copy
import hashlib
import json
import math
import re
import resource
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from execution_registry import APPROVED_SOURCE_HASHES
from execution_contract import InvalidPlan, bind_calls

MAX_INPUT_BYTES = 32768
MAX_OUTPUT_BYTES = 24576


def bounded_json(value, depth=0):
    if depth > 8:
        raise ValueError("JSON nesting too deep")
    if value is None or type(value) is bool:
        return
    if type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > 1e9:
            raise ValueError("Numeric input out of bounds")
    elif isinstance(value, str):
        if len(value) > 2048:
            raise ValueError("String input too long")
    elif isinstance(value, (list, dict)):
        if len(value) > 128:
            raise ValueError("Collection too large")
        for item in (value if isinstance(value, list) else list(value.keys()) + list(value.values())):
            bounded_json(item, depth + 1)
    else:
        raise ValueError("Only JSON data is accepted")


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) - {"calls", "values", "sqlite_rows"}:
        raise ValueError("Unexpected example plan fields")
    bounded_json(plan)
    calls = plan.get("calls")
    if not isinstance(calls, list) or not 1 <= len(calls) <= 12:
        raise ValueError("Supply between 1 and 12 function calls")
    values = plan.get("values", {})
    if not isinstance(values, dict) or any(not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,31}", name)
                                         or name == "connection" for name in values):
        raise ValueError("Named values need simple names; connection is reserved")
    for call in calls:
        if (not isinstance(call, dict) or set(call) - {"function", "args", "kwargs"}
                or not isinstance(call.get("function"), str)
                or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,63}", call["function"])
                or not isinstance(call.get("args", []), list)
                or not isinstance(call.get("kwargs", {}), dict)):
            raise ValueError("Each call needs a function name and JSON args/kwargs")
    rows = plan.get("sqlite_rows", [])
    if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != 2
            or type(row[0]) is not int or not isinstance(row[1], str) for row in rows):
        raise ValueError("sqlite_rows must contain [integer id, string name] rows")


def run(source, plan):
    if hashlib.sha256(source.encode()).hexdigest() not in APPROVED_SOURCE_HASHES:
        raise ValueError("Source is not in the audited fixture registry")
    try:
        validate_plan(plan)
    except ValueError as exc:
        raise InvalidPlan(str(exc)) from None
    bind_calls(source, plan['calls'])
    # State is reset between base/head workers, but shared across calls in a plan.
    state = copy.deepcopy(plan.get("values", {}))
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    connection.executemany("INSERT INTO users VALUES (?, ?)", plan.get("sqlite_rows", []))
    # Injected SQL is part of the vulnerability fixtures. Bound its work and
    # prohibit SQL extensions/file operations even though the DB is in memory.
    for category, limit in ((sqlite3.SQLITE_LIMIT_LENGTH, 8192),
                            (sqlite3.SQLITE_LIMIT_SQL_LENGTH, 8192),
                            (sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 40),
                            (sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 10)):
        connection.setlimit(category, limit)
    progress = [0]
    def sql_progress():
        progress[0] += 1
        return progress[0] > 100  # At most about 10,000 VM operations per plan.
    connection.set_progress_handler(sql_progress, 100)
    connection.set_authorizer(lambda action, arg1, arg2, db, origin:
        sqlite3.SQLITE_OK if action == sqlite3.SQLITE_SELECT or
        (action == sqlite3.SQLITE_READ and arg1 == "users") else sqlite3.SQLITE_DENY)
    namespace = {}
    exec(compile(source, "audited_fixture.py", "exec"), namespace)
    functions = {node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}

    def resolve(value):
        if isinstance(value, dict):
            if set(value) == {"$ref"}:
                name = value["$ref"]
                if name == "connection":
                    return connection
                if not isinstance(name, str) or name not in state:
                    raise InvalidPlan("Unknown named value; define it in values before using $ref")
                return state[name]
            return {key: resolve(v) for key, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        return value

    outputs = []
    try:
        # Validate references for the entire plan before invoking any function.
        resolved = [(call['function'], resolve(call.get('args', [])),
                     resolve(call.get('kwargs', {}))) for call in plan['calls']]
        for name, args, kwargs in resolved:
            try:
                value = namespace[name](*args, **kwargs)
                # Snapshot return/state now; later calls can mutate the objects.
                observation = {"return": value, "exception": None, "values_after": state}
                observation = json.loads(json.dumps(observation, allow_nan=False))
            except Exception as exc:
                observation = {"exception": type(exc).__name__}
            outputs.append(observation)
    finally:
        connection.close()
    return {"observations": outputs}


def main():
    # No file output and limited CPU/open descriptors. Bounded plans plus exact
    # source identities constrain memory; these limits alone are not a sandbox.
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("Example request too large")
        request = json.loads(raw)
        result = run(request["source"], request["plan"])
        encoded = json.dumps(result, allow_nan=False)
        if len(encoded.encode()) > MAX_OUTPUT_BYTES:
            raise ValueError("Example result exceeds output limit")
    except InvalidPlan as exc:
        encoded = json.dumps({'error': str(exc)[:800], 'error_code': 'invalid_plan'})
    except Exception:
        encoded = json.dumps({"error": "Example execution rejected or output could not be encoded"})
    print(encoded)


if __name__ == "__main__":
    main()
