"""网络搜索 Agent — 支持 DuckDuckGo + 必应搜索 API"""
from agents.base_agent import BaseAgent, Task, Result
from core.config import load_config


class WebSearchAgent(BaseAgent):
    name = "web_search"
    description = "联网搜索（支持 DuckDuckGo / 必应）"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("web_search", "fetch_url")

    def execute(self, task: Task) -> Result:
        if task.type == "web_search":
            return self._search(task)
        return Result(task.id, False, error=f"不支持: {task.type}")

    def _search(self, task: Task) -> Result:
        keyword = task.params.get("keyword", "")
        if not keyword:
            keyword = task.params.get("q", "") or task.context
        if not keyword:
            return Result(task.id, False, error="未提供搜索关键词")

        config = load_config()
        provider = config.get("search_provider", "ddgs")

        if provider == "bing":
            return self._search_bing(keyword, config)
        else:
            return self._search_ddgs(keyword)

    def _search_ddgs(self, keyword: str) -> Result:
        try:
            from ddgs import DuckDuckGoSearch
            ddgs = DuckDuckGoSearch()
            results = list(ddgs.text(keyword, max_results=5))
            if not results:
                return Result("", True, summary=f"搜索 '{keyword}' 无结果", data=[])
            summary = f"搜索 '{keyword}' 获得 {len(results)} 条结果"
            return Result("", True, summary=summary, data=results)
        except ImportError:
            return Result("", False, error="DuckDuckGo 模块未安装: pip install ddgs")
        except Exception as e:
            return Result("", False, error=f"DDGS 搜索失败: {e}")

    def _search_bing(self, keyword: str, config: dict) -> Result:
        api_key = config.get("bing_api_key", "")
        if not api_key:
            return Result("", False, error="未配置必应 API Key，请在设置中填写")

        import requests
        try:
            headers = {"Ocp-Apim-Subscription-Key": api_key}
            params = {"q": keyword, "count": 5, "mkt": "zh-CN"}
            resp = requests.get(
                "https://api.bing.microsoft.com/v7.0/search",
                headers=headers, params=params, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            web_pages = data.get("webPages", {}).get("value", [])
            results = []
            for item in web_pages:
                results.append({
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                })

            if not results:
                return Result("", True, summary=f"必应搜索 '{keyword}' 无结果", data=[])

            summary = f"必应搜索 '{keyword}' 获得 {len(results)} 条结果"
            return Result("", True, summary=summary, data=results)

        except requests.exceptions.HTTPError as e:
            if "401" in str(e):
                return Result("", False, error="必应 API Key 无效，请检查设置")
            return Result("", False, error=f"必应搜索请求失败: {e}")
        except requests.exceptions.Timeout:
            return Result("", False, error="必应搜索超时，请检查网络")
        except Exception as e:
            return Result("", False, error=f"必应搜索失败: {e}")
