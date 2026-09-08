"""Host adapter for declarative, audited-fixture execution; no generated Python."""
import hashlib
import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .execution_registry import APPROVED_SOURCE_HASHES
from .execution_contract import callable_help, signatures

WORKER = Path(__file__).with_name("example_worker.py")
EXAMPLE_TOOL = {
    "name": "execute_example",
    "description": "Run your JSON function-call examples on both the original base and head fixture. Returns actual values or exception types, not gold answers or a correctness grade. Each revision starts fresh; calls within one plan share state. Only audited original fixture code is supported. Max 12 calls per plan, 4 plans per review. No Python snippets, filesystem or network access. For SQL use sqlite_rows and {$ref: connection}; for shared JSON objects use values and {$ref: name}.",
    "input_schema": {"type": "object", "properties": {
        "owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"},
        "calls": {"type": "array", "items": {"type": "object", "properties": {
            "function": {"type": "string"}, "args": {"type": "array", "items": {}},
            "kwargs": {"type": "object"}}, "required": ["function"]}},
        "values": {"type": "object"},
        "sqlite_rows": {"type": "array", "items": {"type": "array", "items": {}}}},
        "required": ["owner", "repo", "path", "calls"]}}


def example_tool_for(row):
    tool = copy.deepcopy(EXAMPLE_TOOL)
    sources = {path: source for path, source in row['head_files'].items()
               if path in row['base_files'] and all(hashlib.sha256(s.encode()).hexdigest()
               in APPROVED_SOURCE_HASHES for s in (source, row['base_files'][path]))}
    names = sorted({name for source in sources.values() for name in signatures(source)})
    props = tool['input_schema']['properties']
    props['path']['enum'] = sorted(sources)
    props['calls']['minItems'], props['calls']['maxItems'] = 1, 12
    props['calls']['items']['properties']['function']['enum'] = names
    props['calls']['items']['additionalProperties'] = False
    tool['description'] += ' calls[].function is a SOURCE FUNCTION, never execute_example or get_file_contents. Available head signatures: ' + json.dumps({p: callable_help(s) for p, s in sources.items()})
    return tool


def execute_sources(base, head, plan):
    for source in (base, head):
        if hashlib.sha256(source.encode()).hexdigest() not in APPROVED_SOURCE_HASHES:
            return {"error": "Execution supports only audited original fixture sources"}
    results = {}
    for revision, source in (("base", base), ("head", head)):
        payload = json.dumps({"source": source, "plan": plan}, allow_nan=False)
        if len(payload.encode()) > 32768:
            return {"error": "Example request exceeds 32 KiB"}
        # The subprocess receives no inherited API key, personal memory or files.
        # Only registry-approved function code and JSON values can execute.
        with tempfile.TemporaryDirectory(prefix="review-example-") as directory:
            try:
                result = subprocess.run([sys.executable, "-I", str(WORKER)],
                    input=payload, text=True, capture_output=True, cwd=directory,
                    env={"PATH": os.defpath, "PYTHONHASHSEED": "0"}, timeout=3, close_fds=True)
            except subprocess.TimeoutExpired:
                results[revision] = {"error": "Example exceeded the 3-second process limit"}
                continue
        if result.returncode != 0 or len(result.stdout.encode()) > 24577:
            results[revision] = {"error": "Example worker failed or exceeded its output limit"}
        else:
            try:
                results[revision] = json.loads(result.stdout)
            except (ValueError, TypeError):
                results[revision] = {"error": "Invalid example-worker output"}
    if any("error" in results[rev] for rev in ("base", "head")):
        results["error"] = "At least one revision could not execute the plan"
        results['basis'] = 'Plan failed; do not treat validation errors as fixture behavior or evidence of a defect.'
        results['callables'] = {'base': callable_help(base), 'head': callable_help(head)}
    else:
        results['basis'] = 'Executed audited fixture code. Check the PR preconditions and base/head difference before alleging an introduced defect; an exception alone is not a defect.'
    return results
