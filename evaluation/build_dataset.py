"""Build a small, original development set; no external packages or services."""
import difflib
import hashlib
import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parent
VERSION = "pilot-v1"


def code(text):
    return dedent(text).strip() + "\n"


# Each seed has working base code, a correct refactor, a one-defect refactor,
# normal regression checks, and a focused check that exposes the defect.
# These are development fixtures, not independent real-world PRs.
SEEDS = [
    dict(
        family="pagination", category="correctness", severity="medium",
        title="Refactor pagination helper",
        contract="page(items, number, size): number is zero-based and size is positive; return up to size items.",
        base="""
            def page(items, number, size):
                return items[number * size:(number + 1) * size]
        """,
        clean="""
            def page(items, number, size):
                start = number * size
                stop = start + size
                return items[start:stop]
        """,
        bad_line="stop = start + size - 1", good_line="stop = start + size",
        regression="assert m.page([], 0, 2) == []",
        trigger="assert m.page([10, 20, 30, 40], 1, 2) == [30, 40]",
        description="The exclusive slice endpoint is reduced by one, omitting the final item of each full page.",
    ),
    dict(
        family="mutable_default", category="state_management", severity="medium",
        title="Simplify collection helper",
        contract="collect(item, items=None): append to the provided list, or a fresh list if omitted; return a copy.",
        base="""
            def collect(item, items=None):
                if items is None:
                    items = []
                items.append(item)
                return items[:]
        """,
        clean="""
            def collect(item, items=None):
                if items is None:
                    items = list()
                items.append(item)
                return list(items)
        """,
        bad_line="def collect(item, items=[]):", good_line="def collect(item, items=None):",
        regression="assert m.collect('b', ['a']) == ['a', 'b']",
        trigger="assert m.collect('first') == ['first']\nassert m.collect('second') == ['second']",
        description="The mutable default list retains items across independent calls, mixing caller state.",
    ),
    dict(
        family="empty_aggregate", category="data_handling", severity="medium",
        title="Refactor average calculation",
        contract="average(values): finite numeric inputs; return their mean, or None for an empty list.",
        base="""
            def average(values):
                if len(values) == 0:
                    return None
                return sum(values) / len(values)
        """,
        clean="""
            def average(values):
                count = len(values)
                if count == 0:
                    return None
                return sum(values) / count
        """,
        bad_line="if count < 0:", good_line="if count == 0:",
        regression="assert m.average([2, 4, 6]) == 4",
        trigger="assert m.average([]) is None",
        description="The empty-input guard can never be true; averaging an empty list raises ZeroDivisionError.",
    ),
    dict(
        family="expiration", category="boundary_condition", severity="high",
        title="Refactor expiration comparison",
        contract="is_expired(now, expires_at): timestamps use the same unit; validity ends exactly at expires_at.",
        base="""
            def is_expired(now, expires_at):
                return now >= expires_at
        """,
        clean="""
            def is_expired(now, expires_at):
                remaining = expires_at - now
                return remaining <= 0
        """,
        bad_line="return remaining < 0", good_line="return remaining <= 0",
        regression="assert not m.is_expired(9, 10)\nassert m.is_expired(11, 10)",
        trigger="assert m.is_expired(10, 10)",
        description="The strict comparison treats a credential as valid at its exact expiration timestamp.",
    ),
    dict(
        family="sql_parameterization", category="security", severity="high",
        title="Refactor account lookup",
        contract="lookup(connection, name): return only rows whose name exactly equals the untrusted input; users has columns id and name.",
        base="""
            def lookup(connection, name):
                return connection.execute('SELECT id FROM users WHERE name = ?', (name,)).fetchall()
        """,
        clean="""
            def lookup(connection, name):
                query = 'SELECT id FROM users WHERE name = ?'
                cursor = connection.execute(query, (name,))
                return cursor.fetchall()
        """,
        good_line="cursor = connection.execute(query, (name,))",
        bad_line="cursor = connection.execute(query.replace('?', \"'\" + name + \"'\"))",
        setup="""
            import sqlite3
            connection = sqlite3.connect(':memory:')
            connection.execute('CREATE TABLE users (id INTEGER, name TEXT)')
            connection.executemany('INSERT INTO users VALUES (?, ?)', [(1, 'alice'), (2, 'bob')])
        """,
        regression="assert m.lookup(connection, 'alice') == [(1,)]",
        trigger="assert m.lookup(connection, \"' OR 1=1 --\") == []",
        description="Interpolating untrusted input into SQL lets a crafted name return all users instead of an exact match.",
    ),
    dict(
        family="ownership_check", category="security", severity="high",
        title="Simplify document access helper",
        contract="read_document(documents, doc_id, user_id): existing documents are dictionaries; only their owner may read the body; others get PermissionError.",
        base="""
            def read_document(documents, doc_id, user_id):
                document = documents[doc_id]
                if document['owner_id'] == user_id:
                    return document['body']
                raise PermissionError('Access denied')
        """,
        clean="""
            def read_document(documents, doc_id, user_id):
                document = documents[doc_id]
                if document['owner_id'] != user_id:
                    raise PermissionError('Access denied')
                return document['body']
        """,
        good_line="if document['owner_id'] != user_id:",
        bad_line="if user_id is None:",
        setup="documents = {'report': {'owner_id': 'alice', 'body': 'private'}}",
        regression="assert m.read_document(documents, 'report', 'alice') == 'private'",
        trigger="""
            denied = False
            try:
                m.read_document(documents, 'report', 'bob')
            except PermissionError:
                denied = True
            assert denied, 'Non-owner could read a private document'
        """,
        description="Checking only that a user is present removes ownership authorization, allowing other users to read private documents.",
    ),
    dict(
        family="preprocessing_leakage", category="ml_data_leakage", severity="high",
        title="Refactor numeric feature centering",
        contract="center(train, test): train is nonempty; subtract the training mean from both lists without fitting on test data.",
        base="""
            def center(train, test):
                mean = sum(train) / len(train)
                return [x - mean for x in train], [x - mean for x in test]
        """,
        clean="""
            def center(train, test):
                fitting_values = train
                offset = sum(fitting_values) / len(fitting_values)
                return [value - offset for value in train], [value - offset for value in test]
        """,
        good_line="fitting_values = train", bad_line="fitting_values = train + test",
        regression="assert m.center([2, 4], [3]) == ([-1, 1], [0])",
        trigger="assert m.center([2, 4], [100]) == ([-1, 1], [97])",
        description="Fitting the centering offset on train plus test leaks held-out information into training features.",
    ),
    dict(
        family="lookahead_bias", category="temporal_leakage", severity="high",
        title="Refactor historical price feature",
        contract="prior_mean(prices, index, window): at the start of index, use only the preceding window prices; index >= window > 0 and index < len(prices).",
        base="""
            def prior_mean(prices, index, window):
                return sum(prices[index-window:index]) / window
        """,
        clean="""
            def prior_mean(prices, index, window):
                start = index - window
                history = prices[start:index]
                return sum(history) / len(history)
        """,
        good_line="history = prices[start:index]", bad_line="history = prices[start+1:index+1]",
        regression="assert m.prior_mean([10, 10, 10], 2, 2) == 10",
        trigger="assert m.prior_mean([10, 20, 100], 2, 2) == 15",
        description="The shifted window includes the current price, which is unavailable at prediction time, introducing look-ahead bias.",
    ),
]


def make_records():
    inputs, labels = [], []
    for seed in SEEDS:
        base, clean = code(seed["base"]), code(seed["clean"])
        if clean.count(seed["good_line"]) != 1:
            raise ValueError("Mutation must target exactly one line")
        buggy = clean.replace(seed["good_line"], seed["bad_line"])
        for variant, head in (("clean", clean), ("defect", buggy)):
            case_id = hashlib.sha256((VERSION + seed["family"] + variant).encode()).hexdigest()[:12]
            patch = "".join(difflib.unified_diff(
                base.splitlines(True), head.splitlines(True),
                fromfile="a/module.py", tofile="b/module.py",
            ))
            inputs.append({
                "case_id": case_id,
                "pr": {"title": seed["title"], "body": seed["contract"]},
                "base_files": {"module.py": base},
                "head_files": {"module.py": head},
                "changed_files": [{"filename": "module.py", "status": "modified", "patch": patch}],
            })
            line = next((i for i, text in enumerate(head.splitlines(), 1)
                         if text.strip() == seed["bad_line"]), None)
            issues = [] if variant == "clean" else [{
                "issue_id": case_id + ":1", "file": "module.py",
                "line_start": line, "line_end": line,
                "category": seed["category"], "severity": seed["severity"],
                "description": seed["description"],
            }]
            labels.append({
                "case_id": case_id, "version": VERSION, "split": "dev",
                "group_id": seed["family"], "variant": variant,
                "provenance": "original assistant-authored controlled mutation; not human-validated",
                "difficulty": "small single-file fixture; uncalibrated",
                "issues": issues,
                "oracle": {"setup": code(seed.get("setup", "")),
                           "regression": code(seed["regression"]),
                           "trigger": code(seed["trigger"])},
                "reference_head_files": {"module.py": clean},
            })
    return sorted(inputs, key=lambda x: x["case_id"]), sorted(labels, key=lambda x: x["case_id"])


def main():
    inputs, labels = make_records()
    target = ROOT / "data"
    target.mkdir(exist_ok=True)
    for name, records in (("inputs.jsonl", inputs), ("labels.jsonl", labels)):
        (target / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    print(f"Built {len(inputs)} dev PR cases from {len(SEEDS)} paired seeds in {target}")


if __name__ == "__main__":
    main()
