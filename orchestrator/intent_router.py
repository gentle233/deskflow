"""意图识别 + 任务分解"""
import re

class IntentRouter:
    """基于规则的意图识别，后期可升级为 LLM 驱动"""

    RULES = [
        (r"(\u627e|\u641c\u7d22|\u67e5\u627e|\u6709\u6ca1\u6709).*(\u6587\u4ef6|\u6587\u6863|excel|word|pdf)",
         "file_search", "文件搜索"),
        (r"(\u6253\u5f00|\u8bfb|\u770b\u770b).*(\u6587\u6863|word|pdf|\u6587\u4ef6)",
         "doc_read", "文档读取"),
        (r"(\u6c47\u603b|\u5206\u6790|\u7edf\u8ba1|\u6574\u7406).*(excel|\u8868\u683c|\u62a5\u8868|\u6570\u636e)",
         "excel_analyze", "表格分析"),
        (r"(\u641c|\u67e5).*(\u7f51|\u4fe1\u606f|\u8d44\u6599|\u65b0\u95fb|\u4ef7\u683c)",
         "web_search", "网络搜索"),
        (r"(\u5199|\u751f\u6210|\u5236\u4f5c).*(\u62a5\u544a|\u6587\u6863|\u90ae\u4ef6|\u901a\u77e5|\u6458\u8981)",
         "doc_write", "文档生成"),
    ]

    def route(self, text: str) -> list:
        """识别意图，返回任务列表"""
        tasks = []
        for pattern, task_type, desc in self.RULES:
            if re.search(pattern, text.lower()):
                tasks.append({
                    "type": task_type,
                    "description": desc,
                    "params": {"keyword": text},
                })
        if not tasks:
            tasks.append({
                "type": "chat",
                "description": "普通聊天",
                "params": {},
            })
        return tasks
