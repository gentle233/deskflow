"""文档处理 Agent - 读/写 Word/PDF/TXT"""
import os
from agents.base_agent import BaseAgent, Task, Result
from core.file_ops import FileOps

class DocumentAgent(BaseAgent):
    name = "document"
    description = "文档读取、摘要、生成报告"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("doc_read", "doc_write", "doc_summarize")

    def execute(self, task: Task) -> Result:
        if task.type == "doc_read":
            return self._read(task)
        elif task.type == "doc_write":
            return self._write(task)
        return Result(task.id, False, error=f"不支持: {task.type}")

    def _read(self, task: Task) -> Result:
        path = task.params.get("path", "")
        if not os.path.exists(path):
            return Result(task.id, False, error="文件不存在")
        content = FileOps.read(path)
        preview = content[:500] + "..." if len(content) > 500 else content
        return Result(task.id, True, summary=f"已读取文档: {os.path.basename(path)}", data=content)

    def _write(self, task: Task) -> Result:
        # 文档生成由 tool layer 处理（engine.py 中的 save_file tool）
        # 这里只做标记，让 LLM 知道可以调用 save_file 工具
        return Result(task.id, True, summary="文档生成任务已接收，由 LLM 通过 save_file 工具执行")
