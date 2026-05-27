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
        path = task.params.get("path", "") or os.path.expanduser("~/Desktop/output.txt")
        content = task.params.get("content", "")
        if not content:
            return Result(task.id, True, summary="已理解文档生成需求，请等待 LLM 生成内容后保存")
        FileOps.write(path, content)
        return Result(task.id, True, summary=f"文件已保存: {path}", data=path)
