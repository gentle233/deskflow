"""文件管家 Agent - 文件搜索/监控"""
import os
from agents.base_agent import BaseAgent, Task, Result

class FileManagerAgent(BaseAgent):
    name = "file_manager"
    description = "文件查找、目录扫描、文件监控"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("file_search", "scan_dir", "get_file_info")

    def execute(self, task: Task) -> Result:
        if task.type == "file_search":
            return self._search(task)
        elif task.type == "scan_dir":
            return self._scan(task)
        elif task.type == "get_file_info":
            return self._info(task)
        return Result(task.id, False, error=f"不支持的任务类型: {task.type}")

    def _search(self, task: Task) -> Result:
        keyword = task.params.get("keyword", "")
        folder = task.params.get("path", os.path.expanduser("~"))
        results = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if keyword.lower() in f.lower():
                    results.append(os.path.join(root, f))
            if len(results) >= 20:
                break
        return Result(
            task.id, True,
            summary=f"找到 {len(results)} 个相关文件",
            data=results,
        )

    def _scan(self, task: Task) -> Result:
        path = task.params.get("path", os.path.expanduser("~"))
        items = os.listdir(path)
        return Result(task.id, True, summary=f"目录下有 {len(items)} 个项目", data=items)

    def _info(self, task: Task) -> Result:
        path = task.params.get("path", "")
        if not os.path.exists(path):
            return Result(task.id, False, error="文件不存在")
        stat = os.stat(path)
        info = {
            "name": os.path.basename(path),
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_dir": os.path.isdir(path),
        }
        return Result(task.id, True, summary=f"文件: {info['name']}, {info['size']} bytes", data=info)
