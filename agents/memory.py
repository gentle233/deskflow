"""记忆管家 Agent - 用户画像/习惯学习"""
import json
import os
from agents.base_agent import BaseAgent, Task, Result

MEMORY_PATH = os.path.expanduser("~/.deskflow/memory.json")

class MemoryAgent(BaseAgent):
    name = "memory"
    description = "用户偏好记忆、工作习惯学习"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("recall", "learn", "get_profile")

    def execute(self, task: Task) -> Result:
        if task.type == "recall":
            return self._recall(task)
        elif task.type == "learn":
            return self._learn(task)
        elif task.type == "get_profile":
            return Result(task.id, True, data=self._load())
        return Result(task.id, False, error=f"不支持: {task.type}")

    def _load(self) -> dict:
        if not os.path.exists(MEMORY_PATH):
            os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
            default = {"common_paths": [], "frequent_tasks": [], "preferences": {}}
            with open(MEMORY_PATH, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict):
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _recall(self, task: Task) -> Result:
        profile = self._load()
        key = task.params.get("key", "")
        result = profile.get(key, profile)
        return Result(task.id, True, summary="已读取用户记忆", data=result)

    def _learn(self, task: Task) -> Result:
        key = task.params.get("key", "")
        value = task.params.get("value")
        profile = self._load()
        profile[key] = value
        self._save(profile)
        return Result(task.id, True, summary=f"已记住: {key}")
