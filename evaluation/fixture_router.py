"""GitHub-shaped fixture tools with per-case memory and no network access."""
import copy
import hashlib
import importlib.util
import json
import re
import tempfile
import time
from pathlib import PurePosixPath, Path

from .runtime import ALL_TOOL_DEFINITIONS, PROJECT, ToolRouter
from .example_execution import EXAMPLE_TOOL, execute_sources


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def blob_sha(content):
    payload = content.encode()
    return hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()


def validate_input(row):
    allowed = {"case_id", "pr", "base_files", "head_files", "changed_files"}
    if set(row) != allowed:
        raise ValueError("Fixture input must contain only the five model-visible fields")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", row["case_id"]):
        raise ValueError("Invalid case ID")
    if set(row["pr"]) != {"title", "body"}:
        raise ValueError("PR metadata must contain only title and body")
    if any(not isinstance(text, str) for text in row["pr"].values()):
        raise ValueError("PR title and body must be text")
    for revision in ("base_files", "head_files"):
        if not isinstance(row[revision], dict) or not row[revision]:
            raise ValueError("Expected nonempty source snapshot")
        for path, content in row[revision].items():
            validate_path(path)
            if not isinstance(content, str):
                raise ValueError("Source content must be plain text")
    if not isinstance(row["changed_files"], list):
        raise ValueError("Expected changed-file list")
    for change in row["changed_files"]:
        if set(change) != {"filename", "status", "patch"}:
            raise ValueError("Unexpected changed-file metadata")
        if change["filename"] not in (row["base_files"].keys() | row["head_files"].keys()):
            raise ValueError("Changed file missing from snapshots")


def validate_path(path):
    if (not isinstance(path, str) or not path or "\\" in path
            or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
        raise ValueError("Expected a repository-relative path")


class FixtureRouter:
    MAX_PATCH_CHARS = ToolRouter.MAX_PATCH_CHARS
    MAX_FILE_CONTENT_CHARS = ToolRouter.MAX_FILE_CONTENT_CHARS
    _truncate_result = ToolRouter._truncate_result

    def __init__(self, row, memory_records=None, execution_enabled=False, verification_version='v1'):
        validate_input(row)
        self.row = copy.deepcopy(row)
        self.owner, self.repo, self.pull_number = "benchmark", row["case_id"], 1
        self.branches = {"main": copy.deepcopy(row["base_files"]),
                         "candidate": copy.deepcopy(row["head_files"])}
        self.revisions = {digest(files): copy.deepcopy(files) for files in self.branches.values()}
        self.calls, self.reviews, self.comments, self.fix_prs, self.writes = [], [], [], [], []
        self._definitions = {d["name"]: d for d in ALL_TOOL_DEFINITIONS}
        self.execution_enabled, self.execution_attempts = execution_enabled, 0
        self.execution_duration_ms = 0
        self.allowed_tools = None
        self.verification_version = verification_version
        if execution_enabled:
            from .example_execution import example_tool_for
            self._definitions[EXAMPLE_TOOL["name"]] = example_tool_for(row) if verification_version in ('v2', 'v3') else EXAMPLE_TOOL

        # Execute an independent copy of the existing memory implementation.
        # Only its globals change; production module globals and personal memory
        # are never touched. All six tool behaviors reuse the production code.
        self._temp = tempfile.TemporaryDirectory(prefix="review-evaluation-memory-")
        spec = importlib.util.spec_from_file_location(
            "evaluation_case_memory", PROJECT / "tools/memory_tools.py")
        self._memory_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self._memory_module)
        self._memory_module.MEMORY_FILE = Path(self._temp.name) / "memory.jsonl"
        self._memory_module.BUILTIN_RULES = []
        self._memory_module.MEMORY_FILE.write_text("".join(
            json.dumps(record) + "\n" for record in copy.deepcopy(memory_records or [])))
        self._memory = self._memory_module.MemoryTools()

    def close(self):
        self._temp.cleanup()

    @property
    def tool_definitions(self):
        return copy.deepcopy(list(self._definitions.values()))

    def _files(self, ref=None):
        ref = ref or "main"  # Match GitHub's default-branch behavior.
        if ref in self.branches:
            return self.branches[ref]
        if ref in self.revisions:
            return self.revisions[ref]
        raise ValueError("Unknown branch or revision")

    def _check_args(self, name, args):
        schema = self._definitions[name]["input_schema"]
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be an object")
        if set(schema.get("required", [])) - args.keys():
            raise ValueError("Missing required tool arguments")
        if args.keys() - schema["properties"].keys():
            raise ValueError("Unexpected tool arguments")
        types = {"string": str, "integer": int, "array": list, "object": dict}
        for key, value in args.items():
            prop = schema["properties"][key]
            if type(value) is not types[prop["type"]]:
                raise ValueError(f"Incorrect type for {key}")
            if "enum" in prop and value not in prop["enum"]:
                raise ValueError(f"Invalid value for {key}")
        if name.startswith("memory_"):
            if "repo" in args and args["repo"] != f"{self.owner}/{self.repo}":
                raise ValueError("Memory repository outside this case")
        elif args.get("owner") != self.owner or args.get("repo") != self.repo:
            raise ValueError("Repository outside this case")
        for number in ("pull_number", "issue_number"):
            if number in args and args[number] != self.pull_number:
                raise ValueError("PR outside this case")

    def execute(self, tool_name, tool_input):
        try:
            if self.allowed_tools is not None and tool_name not in self.allowed_tools:
                raise ValueError('Investigation is closed; use only the currently advertised finalization tools')
            if tool_name not in self._definitions:
                raise ValueError("Unknown tool; use the exact advertised tool name")
            self._check_args(tool_name, tool_input)
            result = self._execute(tool_name, copy.deepcopy(tool_input))
            result = self._truncate_result(tool_name, copy.deepcopy(result))
        except Exception as exc:
            result = {"error": str(exc), "tool": tool_name}
        self.calls.append({"tool": tool_name, "input": copy.deepcopy(tool_input),
                           "result": copy.deepcopy(result)})
        return result

    def _execute(self, name, args):
        if name == "execute_example":
            if self.execution_attempts >= 4:
                raise ValueError("Example execution limit reached: four plans per review")
            self.execution_attempts += 1
            validate_path(args["path"])
            if any(args["path"] not in self.row[rev] for rev in ("base_files", "head_files")):
                raise ValueError("Example path must exist in both original snapshots")
            plan = {k: args[k] for k in ("calls", "values", "sqlite_rows") if k in args}
            started = time.monotonic()
            try:
                return execute_sources(self.row["base_files"][args["path"]], self.row["head_files"][args["path"]], plan)
            finally:
                self.execution_duration_ms += int((time.monotonic() - started) * 1000)
        if name.startswith("memory_"):
            if name == "memory_get_all" and args.get("max_tokens", 3000) < 1:
                raise ValueError("Memory budget must be positive")
            return getattr(self._memory, name)(**args)
        if name == "get_pull_request_files":
            files = copy.deepcopy(self.row["changed_files"])
            for entry in files:
                lines = entry["patch"].splitlines()
                entry["additions"] = sum(s.startswith("+") and not s.startswith("+++") for s in lines)
                entry["deletions"] = sum(s.startswith("-") and not s.startswith("---") for s in lines)
                entry["changes"] = entry["additions"] + entry["deletions"]
            return files
        if name == "get_pull_request":
            changes = self._execute("get_pull_request_files", args)
            return {"number": 1, **self.row["pr"], "state": "open", "draft": False,
                    "author": "fixture-author", "base_branch": "main", "head_branch": "candidate",
                    "head_sha": digest(self.branches["candidate"]), "merged": False,
                    "changed_files": len(changes), "additions": sum(c["additions"] for c in changes),
                    "deletions": sum(c["deletions"] for c in changes),
                    "html_url": f"https://fixture.invalid/{self.owner}/{self.repo}/pull/1"}
        if name == "list_commits":
            files = self._files(args.get("sha"))
            if args.get("per_page", 10) < 1:
                raise ValueError("per_page must be positive")
            return [{"sha": digest(files), "message": self.row["pr"]["title"],
                     "author": "fixture-author", "date": "2026-01-01T00:00:00Z"}]
        if name == "get_file_contents":
            validate_path(args["path"])
            files = self._files(args.get("branch"))
            if args["path"] not in files:
                raise ValueError("File not present in this snapshot")
            content = files[args["path"]]
            return {"path": args["path"], "sha": blob_sha(content), "content": content,
                    "encoding": "base64", "size": len(content.encode())}
        if name == "get_pull_request_status":
            return {"state": "pending", "statuses": []}  # Hidden checks are not public CI.
        if name == "detect_test_framework":
            files = self._files(args.get("branch"))
            inspected = [p for p in ("requirements.txt", "pyproject.toml", "package.json") if p in files]
            framework = "pytest" if any("pytest" in files[p] for p in inspected) else "unknown"
            return {"language": "python" if any(p.endswith(".py") for p in files) else "unknown",
                    "frameworks": [framework] if framework != "unknown" else [],
                    "primary_framework": framework, "config_files_checked": inspected}
        if name == "create_pull_request_review":
            # Location errors are preserved for evaluator scoring, not silently dropped.
            for comment in args.get("comments", []):
                if (not isinstance(comment, dict) or not isinstance(comment.get("body"), str)
                        or not isinstance(comment.get("path"), str) or type(comment.get("line")) is not int):
                    raise ValueError("Inline comments require path, line and body")
            self.reviews.append(args)
            return {"id": len(self.reviews), "state": args["event"], "body": args["body"]}
        if name == "add_issue_comment":
            self.comments.append(args)
            return {"id": len(self.comments), "html_url": "https://fixture.invalid/comment"}
        if name == "create_branch":
            branch = args["branch"]
            if not branch or branch in self.branches or branch in self.revisions:
                raise ValueError("Branch already exists or name is empty")
            files = copy.deepcopy(self._files(args.get("from_branch")))
            self.branches[branch] = files
            self.revisions[digest(files)] = copy.deepcopy(files)
            return {"ref": "refs/heads/" + branch, "sha": digest(files)}
        if name == "create_or_update_file":
            path, branch = args["path"], args["branch"]
            validate_path(path)
            if branch in ("main", "candidate") or branch not in self.branches:
                raise ValueError("Write only to a newly created fix branch")
            files = self.branches[branch]
            if path in files and args.get("sha") != blob_sha(files[path]):
                raise ValueError("Missing or stale file SHA")
            if path not in files and args.get("sha"):
                raise ValueError("SHA provided for nonexistent file")
            files[path] = args["content"]
            self.revisions[digest(files)] = copy.deepcopy(files)
            self.writes.append(args)
            return {"path": path, "sha": blob_sha(files[path]), "commit_sha": digest(files)}
        if name == "create_pull_request":
            self._files(args["head"])
            self._files(args["base"])
            if args["head"] in ("main", "candidate") or args["base"] != "candidate":
                raise ValueError("Fix PR must target candidate from a new branch")
            self.fix_prs.append({**args, "files": copy.deepcopy(self._files(args["head"]))})
            return {"number": len(self.fix_prs) + 1, "title": args["title"],
                    "head": args["head"], "base": args["base"],
                    "html_url": "https://fixture.invalid/fix"}
        raise ValueError("Unimplemented tool")

    def artifacts(self):
        return copy.deepcopy({"tool_calls": self.calls, "submitted_reviews": self.reviews,
                              "issue_comments": self.comments, "file_writes": self.writes,
                              "fix_prs": self.fix_prs, "memory": self._memory_module.load_all()})
