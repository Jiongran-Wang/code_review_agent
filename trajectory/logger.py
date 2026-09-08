"""
Real-time trajectory recorder.
Writes each step immediately to JSONL file.
"""
import json
import time
from pathlib import Path
from typing import Any, Optional

from .schemas import (
    SessionStartRecord, SessionEndRecord,
    UserRecord, AssistantRecord,
    LLMResponse, ToolUseBlock,
    new_uuid, now_iso,
)


class TrajectoryLogger:
    def __init__(self, output_dir: Path, session_id: str, pr: str):
        output_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.pr = pr
        self.output_path = output_dir / f"trace_{session_id}.jsonl"
        self._file = open(self.output_path, "w", encoding="utf-8")
        self._last_uuid: Optional[str] = None

        # Stats tracking
        self._start_time = time.time()
        self._llm_calls = 0
        self._tool_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Write session start
        self._write(SessionStartRecord(
            session_id=session_id,
            pr=pr,
        ).to_dict())

    def log_user_input(self, content: str) -> str:
        """Log the initial user task message."""
        record = UserRecord(content=content, parent_uuid=self._last_uuid)
        self._write(record.to_dict())
        self._last_uuid = record.uuid
        return record.uuid

    def log_assistant(self, response: LLMResponse) -> str:
        """Log assistant response (thinking + text + tool_use blocks)."""
        self._llm_calls += 1
        self._total_input_tokens += response.usage.get("input_tokens", 0)
        self._total_output_tokens += response.usage.get("output_tokens", 0)

        record = AssistantRecord(
            content=response.content,
            stop_reason=response.stop_reason,
            usage=response.usage,
            parent_uuid=self._last_uuid,
        )
        self._write(record.to_dict())
        self._last_uuid = record.uuid
        return record.uuid

    def log_tool_result(self, tool_use: ToolUseBlock, result: Any) -> str:
        """Log a tool result as a user message."""
        self._tool_calls += 1

        # Normalize result to string
        if isinstance(result, (dict, list)):
            result_text = json.dumps(result, ensure_ascii=False)
        else:
            result_text = str(result)

        tool_result_content = [
            {"type": "tool_result", "tool_use_id": tool_use.id,
             "content": [{"type": "text", "text": result_text}]}
        ]
        record = UserRecord(content=tool_result_content, parent_uuid=self._last_uuid)
        self._write(record.to_dict())
        self._last_uuid = record.uuid
        return record.uuid

    def close(self, extra_stats: Optional[dict] = None) -> dict:
        """Write session_end and close file. Returns final stats."""
        stats = {
            "llm_calls": self._llm_calls,
            "tool_calls": self._tool_calls,
            "duration_ms": int((time.time() - self._start_time) * 1000),
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
        }
        if extra_stats:
            stats.update(extra_stats)

        self._write(SessionEndRecord(
            session_id=self.session_id,
            stats=stats,
        ).to_dict())
        self._file.flush()
        self._file.close()
        return stats

    def _write(self, record: dict) -> None:
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._file.closed:
            self.close()
