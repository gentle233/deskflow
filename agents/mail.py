"""邮件处理 Agent - 第二版实现"""
from agents.base_agent import BaseAgent, Task, Result

class MailAgent(BaseAgent):
    name = "mail"
    description = "邮件读取/发送/摘要（第二版）"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("mail_read", "mail_send", "mail_summarize")

    def execute(self, task: Task) -> Result:
        return Result(task.id, False, error="邮件功能尚未实现，敬请期待 v0.3")
