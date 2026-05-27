"""意图识别 + 任务分解 — LLM驱动版"""
import json
import re

class IntentRouter:
    """基于 LLM 的意图识别，支持复杂任务分解。
    不依赖规则关键词，能理解自然语言的深层需求。
    """

    CAPABILITIES_PROMPT = """你是 DeskFlow 的任务分解专家。你的工作是理解用户的一句话，将其拆解成可执行的子任务。

可用 Agent 及能力列表：

1. file_search: 文件搜索、目录扫描
   - 用户说"帮我找""桌面上有没有""最近的文件"
   - params: {"keyword": "搜索关键词", "path": "搜索目录(可选)"}

2. doc_read: 文档读取（Word/PDF/TXT）
   - 用户说"打开这篇文档""看看这个pdf""读一下这个文件"
   - 文件已通过上传附着在消息中

3. doc_write: 文档生成（Word/报告/通知/邮件）
   - 用户说"帮我写一份""生成报告""写个通知/邮件/申请"

4. excel_analyze: 表格分析和数据汇总
   - 用户说"汇总一下""分析数据""统计一下""整理报表"

5. web_search: 联网搜索
   - 用户说"查一下""搜一搜""最近的新闻""搜索"

6. chat: 普通对话（没有明确任务的闲聊）
   - 用户说"你好""今天天气""你是谁"等通用对话

输出格式（严格 JSON，不要 markdown 包裹）：
{
  "reasoning": "简短分析用户意图的思路",
  "tasks": [
    {
      "type": "任务类型",
      "description": "这个子任务要做什么",
      "params": {}
    }
  ]
}

示例1：
用户：帮我找一下上个月的报销单
输出：{"reasoning": "用户需要查找文件", "tasks": [{"type": "file_search", "description": "找上个月的报销单", "params": {"keyword": "报销"}}]}

示例2：
用户：帮我汇总一下桌面上的销售报表，然后写个总结报告
输出：{"reasoning": "需要先读文件再生成报告", "tasks": [{"type": "excel_analyze", "description": "分析销售报表", "params": {}}, {"type": "doc_write", "description": "写销售总结报告", "params": {}}]}

示例3：
用户：你好，今天天气怎么样
输出：{"reasoning": "普通闲聊，不需要工具", "tasks": [{"type": "chat", "description": "普通对话", "params": {}}]}

重要规则：
- 简单问题（闲聊）只输出一个 chat 任务
- 复杂任务按逻辑顺序输出多个子任务
- 不要输出用户看不到的内部信息
- 严格遵守 JSON 格式"""

    def __init__(self, llm=None):
        self.llm = llm
        # 保留规则匹配作为兜底
        self.fallback_rules = [
            (r"(找|搜索|查找|有没有).*(文件|文档|excel|word|pdf)", "file_search", "文件搜索"),
            (r"(打开|读|看看).*(文档|word|pdf|文件)", "doc_read", "文档读取"),
            (r"(写|生成|制作|起草).*(报告|文档|邮件|通知|申请|总结|方案|纪要|函)", "doc_write", "文档生成"),
            (r"(汇总|分析|统计|整理|计算).*(excel|表格|报表|数据|销售|报销|支出|收入)", "excel_analyze", "表格分析"),
            (r"(查|搜).*(网|信息|资料|新闻|价格|天气|股票)", "web_search", "网络搜索"),
            (r"(调|写|发).*(邮件|mail)", "mail", "邮件处理"),
        ]

    def route(self, text: str) -> list:
        # 先尝试 LLM 路由
        if self.llm:
            try:
                return self._llm_route(text)
            except Exception as e:
                print(f"[IntentRouter] LLM routing failed: {e}, fallback to rules")
        # 兜底：规则匹配
        return self._rule_route(text)

    def _llm_route(self, text: str) -> list:
        messages = [
            {"role": "system", "content": self.CAPABILITIES_PROMPT},
            {"role": "user", "content": text},
        ]
        reply = self.llm.chat(messages, stream=False)
        # 去除可能的 markdown 代码块包裹
        reply = reply.strip()
        if reply.startswith("```"):
            reply = reply.split("\n", 1)[-1]
            reply = reply.rsplit("\n", 1)[0]
        if reply.endswith("```"):
            reply = reply[:-3]
        reply = reply.strip()
        data = json.loads(reply)
        return data.get("tasks", [])

    def _rule_route(self, text: str) -> list:
        text_lower = text.lower()
        for pattern, task_type, desc in self.fallback_rules:
            if re.search(pattern, text_lower):
                return [{"type": task_type, "description": desc, "params": {"keyword": text}}]
        return [{"type": "chat", "description": "普通对话", "params": {}}]
