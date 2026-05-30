"""Agent 基类 - 统一接口规范"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Task:
    id: str
    type: str  # file_search | doc_read | excel_analyze | web_search | ...
    description: str
    params: dict = field(default_factory=dict)
    context: str = ""

@dataclass
class Result:
    task_id: str
    success: bool
    summary: str = ""       # 给总控看的摘要，不超过 200 字
    data: any = None         # 完整数据
    error: Optional[str] = None

class BaseAgent:
    name: str = "base"
    description: str = ""

    def can_handle(self, task: Task) -> bool:
        return False

    def get_capability_description(self) -> str:
        """返回 Agent 的能力描述，用于主 Agent 的可用工具列表"""
        return f"  - {self.name}: {self.description}"

    def execute(self, task: Task) -> Result:
        raise NotImplementedError
