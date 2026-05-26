"""网络搜索 Agent"""
from agents.base_agent import BaseAgent, Task, Result

class WebSearchAgent(BaseAgent):
    name = "web_search"
    description = "联网搜索、网页摘要"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("web_search", "fetch_url")

    def execute(self, task: Task) -> Result:
        if task.type == "web_search":
            return self._search(task)
        return Result(task.id, False, error=f"不支持: {task.type}")

    def _search(self, task: Task) -> Result:
        keyword = task.params.get("keyword", "")
        try:
            from ddgs import DuckDuckGoSearch
            ddgs = DuckDuckGoSearch()
            results = list(ddgs.text(keyword, max_results=5))
            summary = f"搜索 '{keyword}' 获得 {len(results)} 条结果"
            return Result(task.id, True, summary=summary, data=results)
        except ImportError:
            return Result(task.id, False, error="搜索模块未安装，请执行 pip install ddgs")
        except Exception as e:
            return Result(task.id, False, error=f"搜索失败: {e}")
