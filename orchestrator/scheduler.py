"""Agent 调度器 - 分配任务、收集结果"""
from agents.base_agent import BaseAgent, Task, Result
from typing import List
from uuid import uuid4

class AgentDispatcher:
    """Agent 注册与调度"""

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        self._agents[agent.name] = agent

    def select(self, task_type: str) -> BaseAgent | None:
        for agent in self._agents.values():
            if agent.can_handle(Task(id="", type=task_type, description="")):
                return agent
        return None

    def dispatch(self, task_type: str, params: dict, context: str = "") -> Result:
        agent = self.select(task_type)
        if not agent:
            return Result("", False, error=f"没有 Agent 能处理: {task_type}")
        task = Task(id=str(uuid4())[:8], type=task_type, description="", params=params, context=context)
        return agent.execute(task)
