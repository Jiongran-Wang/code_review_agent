"""
Configuration for the Code Review Agent.
All values can be overridden via environment variables.

Quick start:
  export OPENAI_API_KEY=sk-...           # required
  export OPENAI_MODEL=gpt-4o             # optional, default: gpt-4o
  export OPENAI_BASE_URL=https://...     # optional, for custom endpoints
  export GITHUB_TOKEN=ghp_...            # required for GitHub access

Custom endpoint examples:
  # Azure OpenAI
  OPENAI_BASE_URL=https://<resource>.openai.azure.com/openai/deployments/<deployment>
  # Local (Ollama)
  OPENAI_BASE_URL=http://localhost:11434/v1  OPENAI_API_KEY=ollama
  # DeepSeek / Qwen / other OpenAI-compatible APIs
  OPENAI_BASE_URL=https://api.deepseek.com/v1
"""
import os
from pathlib import Path


class Config:
    # LLM (OpenAI-compatible)
    ANTHROPIC_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    ANTHROPIC_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o")
    THINKING_BUDGET: int = int(os.environ.get("THINKING_BUDGET", "8000"))
    MAX_TOKENS: int = int(os.environ.get("MAX_TOKENS", "16000"))
    ENABLE_THINKING: bool = os.environ.get("ENABLE_THINKING", "false").lower() != "false"

    # GitHub
    GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

    # Paths
    TRAJECTORIES_DIR: Path = Path(os.environ.get("TRAJECTORIES_DIR", "./trajectories"))
    EXPORTS_DIR: Path = Path(os.environ.get("EXPORTS_DIR", "./exports"))

    # Execution
    DRY_RUN: bool = os.environ.get("DRY_RUN", "false").lower() == "true"
    MAX_WORKERS: int = int(os.environ.get("MAX_WORKERS", "1"))
