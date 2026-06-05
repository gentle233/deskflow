"""工作模式注册表 - 预定义工作流模板"""
from typing import TypedDict, NotRequired


class WorkflowStep(TypedDict):
    action: str  # call_agent | ask_user | llm_decide
    agent: NotRequired[str]  # SubAgent 名称（call_agent 时必填）
    description: str  # 步骤描述


class Workflow(TypedDict):
    name: str  # 可读名称
    trigger: str  # 触发条件描述
    steps: list[WorkflowStep]  # 步骤列表


WORKFLOWS: dict[str, Workflow] = {
    "document_edit": {
        "name": "文档修改",
        "trigger": "用户想要修改、编辑、更新现有文档/报告/文件的内容",
        "steps": [
            {"action": "call_agent", "agent": "document", "description": "读取并总结文档当前内容"},
            {"action": "call_agent", "agent": "document", "description": "根据用户需求设计修改方案"},
            {"action": "ask_user", "description": "展示修改方案，询问用户是否确认"},
            {"action": "call_agent", "agent": "document", "description": "执行修改"},
        ]
    },
    "data_analysis": {
        "name": "数据分析",
        "trigger": "用户要分析、汇总、统计 Excel/CSV 表格数据",
        "steps": [
            {"action": "call_agent", "agent": "excel_agent", "description": "读取并解析表格数据"},
            {"action": "call_agent", "agent": "excel_agent", "description": "进行数据分析和统计"},
            {"action": "ask_user", "description": "展示分析结果，询问是否需要生成报告"},
            {"action": "call_agent", "agent": "document", "description": "生成分析报告（如需）"},
        ]
    },
    "information_search": {
        "name": "信息搜索",
        "trigger": "用户要查资料、搜索信息、了解某个话题或新闻",
        "steps": [
            {"action": "call_agent", "agent": "web_search", "description": "搜索相关信息"},
            {"action": "ask_user", "description": "展示搜索结果，询问是否需要进一步搜索或总结"},
        ]
    },
    "email_operation": {
        "name": "邮件处理",
        "trigger": "用户需要读取、搜索、发送或摘要邮件",
        "steps": [
            {"action": "call_agent", "agent": "mail", "description": "执行邮件操作（读/搜/发/摘要）"},
            {"action": "ask_user", "description": "展示邮件结果，询问是否需要更多操作"},
        ]
    },
    "file_operation": {
        "name": "文件操作",
        "trigger": "用户要查找、整理、移动、删除文件或目录",
        "steps": [
            {"action": "call_agent", "agent": "file_manager", "description": "搜索文件/目录"},
            {"action": "ask_user", "description": "展示搜索结果，询问要执行什么操作"},
        ]
    },
    "free_form": {
        "name": "自由模式",
        "trigger": "用户的复杂需求不在以上模式中，由你自行编排",
        "steps": [
            {"action": "llm_decide", "description": "由 LLM 自行决定调用哪些 Agent 及执行顺序"},
        ]
    },
}


def get_workflow_list_text() -> str:
    """生成供 MASTER_PROMPT 使用的工作模式列表文本"""
    lines = []
    for key, wf in WORKFLOWS.items():
        lines.append(f"  - {wf['name']}（{wf['trigger']}）")
        for i, step in enumerate(wf["steps"], 1):
            agent = f" → agent: {step['agent']}" if "agent" in step else ""
            lines.append(f"    步骤{i}: {step['description']}{agent}")
    return "\n".join(lines)


def get_workflow_by_name(name: str) -> Workflow | None:
    """按名称查找工作模式"""
    for wf in WORKFLOWS.values():
        if wf["name"] == name or any(keyword in name for keyword in [wf["name"]]):
            return wf
    return None


def match_workflow(llm_mode_name: str) -> Workflow | None:
    """根据 LLM 输出的 mode 名称匹配工作模式"""
    # 精确匹配
    if llm_mode_name in WORKFLOWS:
        return WORKFLOWS[llm_mode_name]
    # 模糊匹配（中英文名称）
    for key, wf in WORKFLOWS.items():
        if wf["name"] == llm_mode_name:
            return wf
        if llm_mode_name in wf["name"] or wf["name"] in llm_mode_name:
            return wf
    return None
