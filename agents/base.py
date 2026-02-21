"""
agents/base.py — エージェント基底クラス
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import json


class AgentRole(Enum):
    LEAD = "claude"
    CONTEXT = "gemini"
    LOGIC = "openai"


class MessageType(Enum):
    REPORT = "REPORT"
    FEEDBACK = "FEEDBACK"
    REQUEST = "REQUEST"
    DONE = "DONE"
    ERROR = "ERROR"


class Phase(Enum):
    REQUIREMENTS = "REQUIREMENTS"
    DESIGN = "DESIGN"
    IMPLEMENTATION = "IMPLEMENTATION"
    REVIEW = "REVIEW"
    DONE = "DONE"


@dataclass
class AgentMessage:
    agent: str
    phase: Phase
    msg_type: MessageType
    content: str
    next_action: str = "NONE"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        return f"""```
AGENT: {self.agent}
PHASE: {self.phase.value}
TYPE: {self.msg_type.value}
CONTENT:
  {self.content.replace(chr(10), chr(10) + '  ')}
NEXT_ACTION: {self.next_action}
TIMESTAMP: {self.timestamp}
```"""

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "phase": self.phase.value,
            "type": self.msg_type.value,
            "content": self.content,
            "next_action": self.next_action,
            "timestamp": self.timestamp,
        }


@dataclass
class TaskItem:
    id: str
    name: str
    assignee: AgentRole
    status: str  # PENDING, IN_PROGRESS, DONE, BLOCKED, REVIEW
    depends_on: list[str] = field(default_factory=list)
    priority: str = "MEDIUM"
    result: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BaseAgent(ABC):
    """すべてのエージェントの基底クラス"""

    def __init__(self, name: str, role: AgentRole, config: dict = None):
        self.name = name
        self.role = role
        self.config = config or {}
        self.message_history: list[AgentMessage] = []

    @abstractmethod
    def process(self, task: TaskItem, context: str = "") -> AgentMessage:
        """タスクを処理してメッセージを返す"""
        pass

    def _create_message(
        self,
        phase: Phase,
        msg_type: MessageType,
        content: str,
        next_action: str = "NONE",
    ) -> AgentMessage:
        msg = AgentMessage(
            agent=self.name,
            phase=phase,
            msg_type=msg_type,
            content=content,
            next_action=next_action,
        )
        self.message_history.append(msg)
        return msg

    def get_constitution(self, agents_md_path: str) -> str:
        """AGENTS.mdから憲法を読み込む"""
        try:
            with open(agents_md_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "Constitution file not found."

    def provide_feedback(self, proposal: str) -> str:
        """フォロワーシップ原則に基づくフィードバック（オーバーライド可能）"""
        return f"[{self.name}] No feedback at this time."
