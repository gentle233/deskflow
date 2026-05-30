"""总控引擎 - 聊天主循环 + Tool 执行层"""
import re
import os
from orchestrator.intent_router import IntentRouter
from orchestrator.scheduler import AgentDispatcher
from core.llm_gateway import LLMGateway

class Orchestrator:
    """用户唯一的入口，负责理解、分解、调度、整合"""

    # =====================================================
    # Tool 定义区 — Agent 通过这里操作外部系统
    # =====================================================
    TOOL_DEFINITIONS = """
你有以下工具可以使用。当需要执行实际操作时，在回复中按格式输出：

1. 保存文件到本地
   ```
   [TOOL: save_file]
   path: ~/Desktop/output.txt
   content: 文件内容写在这里
   [/TOOL]
   ```

2. 搜索文件
   ```
   [TOOL: search_file]
   keyword: 关键词
   path: ~/               (可选，默认桌面)
   [/TOOL]
   ```

3. 读取文件内容
   ```
   [TOOL: read_file]
   path: ~/Desktop/xxx.txt
   [/TOOL]
   ```

4. 分析 Excel
   ```
   [TOOL: analyze_excel]
   path: ~/Desktop/xxx.xlsx
   [/TOOL]
   """

    # =====================================================
    # 主控 Agent System Prompt — 红线 + 工作流输出格式
    # =====================================================
    MASTER_PROMPT = """\
你是 DeskFlow 的主控 Agent，位于工作流引擎的最上层，负责理解用户意图并决定响应方式。

## 核心规则（红线）

1. **直接回复（不进工作流）**
   - 闲聊、打招呼、感谢、情绪表达 → 直接友好回复
   - 常识性问题、简单知识问答 → 直接回答
   - 对自己的角色/能力询问 → 直接说明
   - 任何不需要工具、不需要查信息、不需要多步骤的请求 → 直接回复，不进工作流

2. **进入工作流模式**
   - 需要操作文件（保存/读取/搜索/分析 Excel）→ 进入工作流
   - 需要查询外部信息、调用工具 → 进入工作流
   - 需要多步骤推理或分解执行的复杂任务 → 进入工作流
   - 需要调用 SubAgent 完成特定领域任务 → 进入工作流

3. **需要用户确认的步骤**
   - 即将执行可能影响用户数据的操作前 → 先问用户确认
   - 意图不明确，需要用户补充信息时 → 先问清楚
   - 多个可选方案时 → 简要列出让用户选择

## 可用 SubAgent
{agent_list}

## 可用工作模式
{workflow_list}

## 工作流输出格式

当你判断需要进入工作流时，请按以下格式输出标记块，每行一个标记，引擎会逐行解析并执行：

[mode: 模式名称]
[step: 1]
[action: call_agent]
[agent: agent_name]
[params: {{"key": "value"}}]
[description: 描述]

如需多步工作流，依次输出多个步骤：

[mode: 多步工作流]
[step: 1]
[action: call_agent]
[agent: agent_name]
[params: {{"key1": "value1"}}]
[description: 第一步描述]

[step: 2]
[action: call_agent]
[agent: agent_name]
[params: {{"key2": "value2"}}]
[description: 第二步描述]

### 格式说明
- `[mode: ...]` — 工作模式名称，如 "文件操作"、"数据分析"、"信息查询"
- `[step: N]` — 当前步骤编号，从 1 开始
- `[action: call_agent]` — 动作类型，目前固定为 call_agent
- `[agent: ...]` — 要调用的 SubAgent 名称，必须来自可用 SubAgent 列表
- `[params: ...]` — JSON 格式的参数，传递给 SubAgent
- `[description: ...]` — 当前步骤的简要描述，用于日志和用户可见反馈

## 输出规范

- 如不进工作流 → 直接输出普通回复，简洁自然
- 如需用户确认 → 先输出问题等待用户回答，不进工作流
- 如需进入工作流 → 输出上述标记格式，引擎执行完会返回结果，你根据结果继续处理
- 始终使用中文回复（除非用户用其他语言提问）
"""

    # =====================================================
    # 主控 Agent System Prompt — 红线 + 工作流输出格式
    

    def __init__(self, llm: LLMGateway):
        self.llm = llm
        self.router = IntentRouter(llm=llm)
        self.dispatcher = AgentDispatcher()
        self.history: list[dict] = []
        self.tools_enabled = False  # 第一次调用时自动开启

    def process(self, user_input: str) -> str:
        """主控入口：先走红线判断，再进工作流循环"""
        self.history.append({"role": "user", "content": user_input})

        # 1. 构建主 Agent 上下文（含 MASTER_PROMPT）
        context = self._build_master_context(user_input)

        # 2. 先调一次 LLM，看是直接回复还是进工作流
        reply = self.llm.chat(context, stream=False)

        # 3. 检查是否有工作流标记
        mode = self._parse_mode(reply)
        if not mode:
            # 红线命中：直接回复
            self.history.append({"role": "assistant", "content": reply})
            return reply

        # 4. 进入工作流循环（最多 10 步）
        context.append({"role": "assistant", "content": reply})
        for step_idx in range(10):
            agent_call = self._parse_agent_call(reply)
            if not agent_call:
                break  # 没有 agent 调用了，结束工作流

            # 执行 SubAgent
            agent_name = agent_call["agent"]
            params = agent_call.get("params", {})
            result = self.dispatcher.dispatch(agent_name, params, user_input)

            # 把结果喂回 LLM
            result_text = f"[SubAgent 执行结果]\n{result.summary if result.success else result.error}"
            context.append({"role": "user", "content": result_text})

            # LLM 决定下一步
            reply = self.llm.chat(context, stream=False)
            context.append({"role": "assistant", "content": reply})

            # 检查是否还有下一步
            if not self._parse_agent_call(reply):
                break

        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _build_master_context(self, user_input: str) -> list:
        """构建主 Agent 上下文：MASTER_PROMPT + 历史 + 当前输入"""
        agent_list = self._build_agent_list()
        workflow_list = self._build_workflow_list()

        system_content = self.MASTER_PROMPT.format(
            agent_list=agent_list,
            workflow_list=workflow_list
        )

        messages = [{"role": "system", "content": system_content}]
        # 带上最近 4 轮对话历史
        messages.extend(self.history[-8:])
        return messages

    def _build_agent_list(self) -> str:
        """动态生成可用 SubAgent 列表"""
        dispatcher = getattr(self, 'dispatcher', None)
        if dispatcher is None or not hasattr(dispatcher, '_agents') or not dispatcher._agents:
            return "（暂无可用 SubAgent）"
        lines = []
        for name, agent in self.dispatcher._agents.items():
            desc = getattr(agent, 'description', name)
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)

    def _build_workflow_list(self) -> str:
        """动态生成可用工作模式列表"""
        try:
            from orchestrator.workflows import get_workflow_list_text
            return get_workflow_list_text()
        except ImportError:
            return "（暂无预设工作模式，由你自行编排）"

    def _parse_mode(self, reply: str) -> str | None:
        """从 LLM 回复中提取 [mode: xxx]"""
        m = re.search(r'\[mode:\s*(.+?)\]', reply)
        return m.group(1).strip() if m else None

    def _parse_agent_call(self, reply: str) -> dict | None:
        """从 LLM 回复中提取 agent 调用参数"""
        # 查找 [action: call_agent] 块
        action_match = re.search(r'\[action:\s*call_agent\]', reply)
        if not action_match:
            return None

        # 提取 agent 名称
        agent_match = re.search(r'\[action:\s*call_agent\]\s*\n\s*\[agent:\s*(.+?)\]', reply)
        agent_name = agent_match.group(1).strip() if agent_match else None
        if not agent_name:
            return None

        # 提取 params
        params = {}
        params_match = re.search(r'\[params:\s*(\{.*?\})\]', reply)
        if params_match:
            try:
                import json
                params = json.loads(params_match.group(1))
            except json.JSONDecodeError:
                pass

        return {"agent": agent_name, "params": params}

    def _build_context(self, user_input: str, agent_results: list) -> list:
        """旧版上下文构建（保留兼容）"""
        messages = [{
            "role": "system",
            "content": "你是 DeskFlow 桌面助手，用中文回答。简洁专业。\n\n"
                       + self.TOOL_DEFINITIONS
                       + "\n当用户要求保存/读取/搜索文件时，请使用上述工具。不需要工具时正常回复即可。"
        }]
        messages.extend(self.history[-6:])
        for r in agent_results:
            if r.success:
                messages.append({"role": "system", "content": f"[已执行: {r.summary}]"})
            else:
                messages.append({"role": "system", "content": f"[执行结果: {r.error}]"})
        return messages

    def _execute_tools(self, reply: str) -> list:
        """解析 LLM 回复中的 tool 调用并执行（保留兼容）"""
        results = []
        pattern = r'\[TOOL:\s*(\w+)\](.*?)\[/TOOL\]'
        for match in re.finditer(pattern, reply, re.DOTALL):
            tool_name = match.group(1).strip()
            tool_body = match.group(2).strip()
            params = self._parse_tool_params(tool_body)
            if tool_name == "save_file":
                result = self._tool_save_file(params)
            elif tool_name == "search_file":
                result = self._tool_search_file(params)
            elif tool_name == "read_file":
                result = self._tool_read_file(params)
            elif tool_name == "analyze_excel":
                result = self._tool_analyze_excel(params)
            else:
                result = f"未知工具: {tool_name}"
            results.append(result)
        return results

    def _parse_tool_params(self, body: str) -> dict:
        """解析 tool 参数块"""
        params = {}
        for line in body.split("\n"):
            line = line.strip()
            if ":" in line:
                key, val = line.split(":", 1)
                params[key.strip()] = val.strip()
        return params

    def _tool_save_file(self, params: dict) -> str:
        path = os.path.expanduser(params.get("path", "~/Desktop/output.txt"))
        content = params.get("content", "")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ 文件已保存: {path} ({len(content)} 字符)"

    def _tool_search_file(self, params: dict) -> str:
        keyword = params.get("keyword", "")
        path = os.path.expanduser(params.get("path", "~"))
        results = []
        for root, dirs, files in os.walk(path):
            for f in files:
                if keyword.lower() in f.lower():
                    results.append(os.path.join(root, f))
            if len(results) >= 10:
                break
        if results:
            return f"找到 {len(results)} 个文件:\n" + "\n".join(results[:5])
        return f"未找到包含 '{keyword}' 的文件"

    def _tool_read_file(self, params: dict) -> str:
        path = os.path.expanduser(params.get("path", ""))
        if not os.path.exists(path):
            return f"❌ 文件不存在: {path}"
        from core.file_ops import FileOps
        content = FileOps.read(path)
        if len(content) > 2000:
            content = content[:2000] + "\n...(截断)"
        return f"📄 {os.path.basename(path)}:\n{content}"

    def _tool_analyze_excel(self, params: dict) -> str:
        path = os.path.expanduser(params.get("path", ""))
        if not os.path.exists(path):
            return f"❌ 文件不存在: {path}"
        import pandas as pd
        try:
            df = pd.read_excel(path) if not path.endswith(".csv") else pd.read_csv(path)
            return f"📊 {os.path.basename(path)}: {len(df)}行×{len(df.columns)}列\n列名: {list(df.columns)}\n预览:\n{df.head(5).to_string()}"
        except Exception as e:
            return f"❌ 读取失败: {e}"

