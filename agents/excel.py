"""表格分析 Agent - Excel 读取/统计"""
import os
import pandas as pd
from agents.base_agent import BaseAgent, Task, Result

class ExcelAgent(BaseAgent):
    name = "excel_agent"
    description = "Excel 分析、统计汇总"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("excel_read", "excel_analyze", "excel_merge")

    def execute(self, task: Task) -> Result:
        if task.type == "excel_read":
            return self._read(task)
        elif task.type == "excel_analyze":
            return self._analyze(task)
        return Result(task.id, False, error=f"不支持: {task.type}")

    def _read(self, task: Task) -> Result:
        path = task.params.get("path", "")
        if not os.path.exists(path):
            return Result(task.id, False, error="文件不存在")
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
        info = f"行数: {len(df)}, 列数: {len(df.columns)}, 列名: {list(df.columns)}"
        return Result(task.id, True, summary=info, data=df.to_dict(orient="records"))

    def _analyze(self, task: Task) -> Result:
        data = task.params.get("data", [])
        if not data:
            return Result(task.id, False, error="无数据可分析")
        df = pd.DataFrame(data)
        summary = df.describe(include="all").to_dict()
        return Result(task.id, True, summary=f"分析完成: {len(df)} 条记录", data=summary)
