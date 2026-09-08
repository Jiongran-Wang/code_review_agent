"""
Trajectory data structure definitions.
Compatible with Claude Code's JSONL conversation format.
"""
from dataclasses import dataclass, field
from typing import Any, Optional
import uuid
import time


def new_uuid() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


# ─── Content block types ────────────────────────────────────────────────────

@dataclass
class ThinkingBlock:
    thinking: str
    type: str = "thinking"

    def to_dict(self) -> dict:
        return {"type": self.type, "thinking": self.thinking}


@dataclass
class TextBlock:
    text: str
    type: str = "text"

    def to_dict(self) -> dict:
        return {"type": self.type, "text": self.text}


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"

    def to_dict(self) -> dict:
        return {"type": self.type, "id": self.id, "name": self.name, "input": self.input}


@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: list[dict]  # [{"type": "text", "text": "..."}]
    type: str = "tool_result"

    def to_dict(self) -> dict:
        return {"type": self.type, "tool_use_id": self.tool_use_id, "content": self.content}


# ─── LLM Response ────────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    content: list[dict]           # Raw content blocks from Anthropic API
    stop_reason: str              # "end_turn" | "tool_use"
    usage: dict                   # {"input_tokens": N, "output_tokens": N}
    model: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Extract concatenated text from content blocks."""
        parts = []
        for block in self.content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts)

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        """Extract tool_use blocks."""
        result = []
        for block in self.content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                result.append(ToolUseBlock(
                    id=block["id"],
                    name=block["name"],
                    input=block["input"]
                ))
        return result


# ─── Trajectory records ──────────────────────────────────────────────────────

@dataclass
class SessionStartRecord:
    session_id: str
    pr: str                       # "owner/repo#42"
    timestamp: str = field(default_factory=now_iso)
    type: str = "session_start"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "pr": self.pr,
            "timestamp": self.timestamp,
        }


@dataclass
class UserRecord:
    content: Any                  # str or list of content blocks
    uuid: str = field(default_factory=new_uuid)
    parent_uuid: Optional[str] = None
    type: str = "user"

    def to_dict(self) -> dict:
        d = {
            "type": self.type,
            "uuid": self.uuid,
            "message": {"role": "user", "content": self.content},
        }
        if self.parent_uuid:
            d["parentUuid"] = self.parent_uuid
        return d


@dataclass
class AssistantRecord:
    content: list[dict]           # thinking + text + tool_use blocks
    stop_reason: str
    usage: dict
    uuid: str = field(default_factory=new_uuid)
    parent_uuid: Optional[str] = None
    type: str = "assistant"

    def to_dict(self) -> dict:
        d = {
            "type": self.type,
            "uuid": self.uuid,
            "message": {
                "role": "assistant",
                "content": self.content,
                "stop_reason": self.stop_reason,
                "usage": self.usage,
            },
        }
        if self.parent_uuid:
            d["parentUuid"] = self.parent_uuid
        return d


@dataclass
class SessionEndRecord:
    session_id: str
    stats: dict
    timestamp: str = field(default_factory=now_iso)
    type: str = "session_end"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "stats": self.stats,
        }


# ─── Agent result ─────────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    messages: list[dict]
    final_response: str
    session_id: str
    stats: dict = field(default_factory=dict)
