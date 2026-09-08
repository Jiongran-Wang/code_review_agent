"""Allow `python -m evaluation.run` from this project's root."""
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT.parent))

from code_review_agent.agent.runner import AgentRunner
from code_review_agent.agent.llm_client import LLMClient
from code_review_agent.agent.skill_loader import SkillLoader
from code_review_agent.agent.tool_router import ALL_TOOL_DEFINITIONS, ToolRouter
from code_review_agent.trajectory.schemas import LLMResponse

