"""
Pipeline orchestrator: coordinates the 4-phase code review pipeline.

Phase 1: Triage   — classify PR, decide auto vs human
Phase 2: Analyze  — collect PR data (diff, commits, memory rules)
Phase 3: Review   — LLM analysis of code quality
Phase 4: Act      — submit GitHub review + optional fix PR
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..agent.runner import AgentRunner
from ..agent.llm_client import LLMClient
from ..agent.tool_router import ToolRouter
from ..agent.skill_loader import SkillLoader
from ..tools.github_tools import GitHubTools
from ..tools.memory_tools import get_all_summary, get_repo_patterns
from ..trajectory.schemas import AgentResult


@dataclass
class ReviewResult:
    pr: str
    decision: str = ""
    issues_found: int = 0
    fix_pr_number: Optional[int] = None
    human_required: bool = False
    skip_reason: str = ""
    session_id: str = ""
    stats: dict = field(default_factory=dict)
    error: Optional[str] = None


def parse_pr_identifier(pr_input: str) -> tuple[str, str, int]:
    """
    Parse PR identifier into (owner, repo, pr_number).

    Supports:
    - "owner/repo #42"
    - "owner/repo PR 42"
    - "github.com/owner/repo/pull/42"
    - "https://github.com/owner/repo/pull/42"
    """
    # URL format
    url_match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_input)
    if url_match:
        return url_match.group(1), url_match.group(2), int(url_match.group(3))

    # "owner/repo #42" or "owner/repo PR 42"
    short_match = re.search(r"([^/\s]+)/([^/\s#]+)\s*(?:#|PR\s+)(\d+)", pr_input, re.IGNORECASE)
    if short_match:
        return short_match.group(1), short_match.group(2), int(short_match.group(3))

    raise ValueError(
        f"Cannot parse PR identifier: {pr_input!r}\n"
        "Expected format: owner/repo #42 or https://github.com/owner/repo/pull/42"
    )


class ReviewOrchestrator:
    """
    Drives the full code review pipeline using the AgentRunner.
    The LLM (via AgentRunner) handles all phases guided by the skill system prompt.
    """

    def __init__(
        self,
        github_token: str = "",
        anthropic_api_key: str = "",
        model: str = "",
        trajectories_dir: Optional[Path] = None,
        dry_run: bool = False,
        enable_thinking: bool = True,
    ):
        self.trajectories_dir = trajectories_dir or Path("./trajectories")
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)

        # Build components
        llm_client = LLMClient(
            api_key=anthropic_api_key,
            model=model or None,
            enable_thinking=enable_thinking,
        )
        tool_router = ToolRouter(github_token=github_token, dry_run=dry_run)
        skill_loader = SkillLoader()

        self.runner = AgentRunner(
            llm_client=llm_client,
            tool_router=tool_router,
            skill_loader=skill_loader,
            trajectories_dir=self.trajectories_dir,
            skill_name="code-review",
        )

    def review(self, pr_input: str) -> ReviewResult:
        """
        Run a full code review for the given PR.

        Args:
            pr_input: PR identifier (e.g. "owner/repo #42" or GitHub URL)
        """
        try:
            owner, repo, pr_number = parse_pr_identifier(pr_input)
        except ValueError as e:
            return ReviewResult(pr=pr_input, error=str(e))

        pr_label = f"{owner}/{repo}#{pr_number}"
        task = f"review {owner}/{repo} #{pr_number}"

        result: AgentResult = self.runner.run(task=task, pr=pr_label)

        return ReviewResult(
            pr=pr_label,
            decision=result.stats.get("decision", ""),
            issues_found=result.stats.get("issues_found", 0),
            session_id=result.session_id,
            stats=result.stats,
        )

    def batch_review(
        self,
        pr_list: list[str],
        max_workers: int = 1,
    ) -> list[ReviewResult]:
        """
        Review multiple PRs. Sequential by default (max_workers=1).
        Set max_workers > 1 for concurrent execution.
        """
        if max_workers <= 1:
            return [self.review(pr) for pr in pr_list]

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.review, pr) for pr in pr_list]
            return [f.result() for f in futures]

    def generate_health_report(self, repo: str) -> str:
        """
        Generate a markdown health report for a repository based on
        accumulated cross-PR pattern statistics in memory.

        Args:
            repo: Repository in "owner/repo" format.

        Returns:
            Markdown-formatted health report string.
        """
        from datetime import datetime, timezone

        patterns = get_repo_patterns(repo)

        if not patterns:
            return (
                f"# Code Health Report: {repo}\n\n"
                f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n\n"
                "No pattern data available yet. Run some PR reviews first to accumulate data.\n"
            )

        # Sort patterns by occurrence_count descending
        patterns_sorted = sorted(
            patterns,
            key=lambda r: r["content"].get("occurrence_count", 0),
            reverse=True,
        )

        # Group by severity
        by_severity: dict[str, list] = {"critical": [], "high": [], "medium": [], "low": []}
        for p in patterns_sorted:
            sev = p["content"].get("severity", "low")
            if sev in by_severity:
                by_severity[sev].append(p)
            else:
                by_severity["low"].append(p)

        total_issues = sum(p["content"].get("occurrence_count", 0) for p in patterns)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# Code Health Report: {repo}",
            f"",
            f"*Generated: {now_str}*",
            f"",
            f"## Summary",
            f"",
            f"- **Total issue occurrences tracked**: {total_issues}",
            f"- **Distinct patterns**: {len(patterns)}",
            f"- **Critical patterns**: {len(by_severity['critical'])}",
            f"- **High severity patterns**: {len(by_severity['high'])}",
            f"",
        ]

        # Severity sections
        severity_labels = {
            "critical": "🔴 Critical",
            "high": "🟠 High",
            "medium": "🟡 Medium",
            "low": "🟢 Low",
        }

        for sev, label in severity_labels.items():
            items = by_severity[sev]
            if not items:
                continue
            lines.append(f"## {label} Severity Patterns")
            lines.append("")
            lines.append("| Pattern | Category | Occurrences | Trend | Last Seen |")
            lines.append("|---------|----------|-------------|-------|-----------|")
            for p in items:
                c = p["content"]
                pattern_name = c.get("pattern_name", "unknown")
                category = c.get("category", "unknown")
                count = c.get("occurrence_count", 0)
                trend = c.get("trend", "stable")
                last_seen = c.get("last_seen", "")[:10] if c.get("last_seen") else "unknown"
                trend_icon = "📈" if trend == "increasing" else ("🆕" if trend == "new" else "➡️")
                lines.append(f"| `{pattern_name}` | {category} | {count} | {trend_icon} {trend} | {last_seen} |")
            lines.append("")

        # Top affected files
        all_files: dict[str, int] = {}
        for p in patterns:
            for f in p["content"].get("affected_files", []):
                all_files[f] = all_files.get(f, 0) + p["content"].get("occurrence_count", 0)

        if all_files:
            top_files = sorted(all_files.items(), key=lambda x: x[1], reverse=True)[:10]
            lines.append("## Top Affected Files")
            lines.append("")
            lines.append("| File | Issue Count |")
            lines.append("|------|-------------|")
            for file_path, count in top_files:
                lines.append(f"| `{file_path}` | {count} |")
            lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")
        if by_severity["critical"]:
            lines.append("1. 🚨 **Immediate action required**: Address all critical security patterns")
        if by_severity["high"]:
            top_high = by_severity["high"][0]["content"]
            lines.append(
                f"2. 🔧 **High priority**: `{top_high.get('pattern_name')}` "
                f"has occurred {top_high.get('occurrence_count')} times — consider adding a linter rule"
            )
        lines.append("3. 📋 Consider adding pre-commit hooks to catch recurring patterns automatically")
        lines.append("4. 📚 Schedule a team knowledge-sharing session on the top issue categories")
        lines.append("")
        lines.append("---")
        lines.append(f"*Report generated by Code Review Agent*")

        return "\n".join(lines)
