"""总控引擎 - 聊天主循环 + Tool 执行层"""
import re
import os
import json
from orchestrator.scheduler import AgentDispatcher
from core.llm_gateway import LLMGateway

class Orchestrator:
    """用户唯一的入口，负责理解、分解、调度、整合"""

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

    MASTER_PROMPT = """\
你是 DeskFlow 的主控 Agent，位于工作流引擎的最上层，负责理解用户意图并决定响应方式。

## 核心规则（红线）

1. **直接回复（不进工作流）**
   - 闲聊、打招呼、感谢、情绪表达 → 直接友好回复
   - 常识性问题、简单知识问答 → 直接回答
   - 对自己的角色/能力询问 → 直接说明

2. **进入工作流模式**（你有这些能力，必须使用！）
   - 写文档、写报告、写总结、写介绍、写邮件、写方案 → 进入工作流
   - 保存文件、读取文件、搜索文件、分析 Excel → 进入工作流
   - 查询外部信息、搜索资料 → 进入工作流
   - 任何需要调用 SubAgent 的任务 → 进入工作流
   - 多步骤复杂任务 → 进入工作流

3. **需要用户确认的步骤**
   - 即将执行可能影响用户数据的操作前 → 先问用户确认
   - 意图不明确，需要用户补充信息时 → 先问清楚
   - 多个可选方案时 → 简要列出让用户选择

## 可用 SubAgent
{agent_list}

## 可用工作模式
{workflow_list}

## 工作流输出格式

当你判断需要进入工作流时，请按以下格式输出标记块：

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
- [mode: xxx] — 工作模式名称
- [step: N] — 步骤编号
- [action: call_agent] — 调 SubAgent
- [action: ask_user] — 需要用户确认
- [agent: xxx] — SubAgent 名称
- [params: xxx] — JSON 参数
- [description: xxx] — 步骤描述

## 输出规范
- 不进工作流 → 直接回复
- 需用户确认 → 输出 [action: ask_user]
- 调 SubAgent → 输出 [action: call_agent]
- 始终用中文回复
"""

    def __init__(self, llm: LLMGateway):
        self.llm = llm
        self.dispatcher = AgentDispatcher()
        self.history: list[dict] = []
        self.tools_enabled = False
        self._workflow_state: dict | None = None

    # =========================================================
    # 主入口
    # =========================================================

    def process(self, user_input: str) -> str:
        """主控入口：先检查暂停的工作流，再走红线判断"""
        self.history.append({"role": "user", "content": user_input})

        try:
            result = self._process_impl(user_input)
            if result is None:
                return "⚠️ 处理出错：返回结果为空，请重试"
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"⚠️ 处理异常: {str(e)}"

    def _process_impl(self, user_input: str) -> str | None:
        # 0. 检查是否有暂停的工作流
        if self._workflow_state is not None:
            return self._resume_workflow(user_input)

        # 1. 构建主 Agent 上下文
        context = self._build_master_context(user_input)

        # 2. 调 LLM
        reply = self.llm.chat(context, stream=False)

        # 3. 执行工具标记（如果有 [TOOL: xxx] 但没有工作流模式）
        tool_results = self._execute_tools(reply)
        if tool_results:
            for r in tool_results:
                context.append({"role": "system", "content": r})
            reply = self.llm.chat(context, stream=False)
            # 递归检查：LLM 可能在工具执行后又输出新模式
            if self._parse_mode(reply):
                return self._run_workflow(context, reply)

        # 4. 检查是否有工作流标记
        if not self._parse_mode(reply):
            self.history.append({"role": "assistant", "content": reply})
            return reply

        # 5. 进入工作流循环
        result = self._run_workflow(context, reply)
        if result is None:
            return "⚠️ 工作流返回空"
        return result

    def _run_workflow(self, context: list, reply: str) -> str:
        """执行工作流循环，支持并行和 ask_user 暂停"""
        mode = self._parse_mode(reply)
        context.append({"role": "assistant", "content": reply})

        max_steps = 10
        for step_idx in range(max_steps):
            # 解析 LLM 输出的步骤
            steps = self._parse_all_steps(reply)

            # LLM 没输出步骤 → 尝试从预定义模板加载
            if not steps and mode:
                steps = self._load_workflow_template(mode)

            if not steps:
                break

            # 过滤掉 llm_decide（由 LLM 自行决定，不执行具体动作）
            steps = [s for s in steps if s["action"] != "llm_decide"]
            if not steps:
                break

            # 检查是否有 ask_user 步骤
            ask_steps = [s for s in steps if s["action"] == "ask_user"]
            if ask_steps:
                # 先执行 ask_user 前面的所有 call_agent 步骤（可并行）
                pre_steps = [s for s in steps if s["action"] == "call_agent"]
                if pre_steps:
                    results = self._batch_execute_agents(pre_steps)
                    for r_text in results:
                        context.append({"role": "user", "content": r_text})
                    # 把结果喂给 LLM
                    reply = self.llm.chat(context, stream=False)
                    context.append({"role": "assistant", "content": reply})
                    # 执行工具标记
                    tool_results2 = self._execute_tools(reply)
                    for r in tool_results2:
                        context.append({"role": "system", "content": r})
                    # 重新解析
                    steps = self._parse_all_steps(reply)
                    ask_steps = [s for s in steps if s["action"] == "ask_user"]

                # 处理 ask_user
                if not ask_steps:
                    break
                first_ask = ask_steps[0]
                self._workflow_state = {
                    "context": context,
                    "step": step_idx,
                    "mode": mode,
                }
                desc = first_ask.get("description", "请确认是否继续？")
                self.history.append({"role": "assistant", "content": reply})
                return (
                    f"{reply}\n\n"
                    f"---\n"
                    f"⏸️ 等待您确认: {desc}\n"
                    f'回复 "确认" 继续，或 "取消" 中止'
                )

            # 没有 ask_user → 执行所有 call_agent 步骤（并行）
            call_steps = [s for s in steps if s["action"] == "call_agent"]
            if not call_steps:
                break

            results = self._batch_execute_agents(call_steps)
            for r_text in results:
                context.append({"role": "user", "content": r_text})

            # LLM 决定下一步
            reply = self.llm.chat(context, stream=False)
            context.append({"role": "assistant", "content": reply})

            # 执行工具标记（如果 LLM 在流程中用了 [TOOL: ...]）
            tool_results = self._execute_tools(reply)
            for r in tool_results:
                context.append({"role": "system", "content": r})

            # 检查是否还有步骤
            next_steps = self._parse_all_steps(reply)
            if not next_steps and not tool_results:
                break
        else:
            # 循环正常结束（未 break），说明达到最大步数
            reply += "\n\n⚠️ 工作流已达到最大步数限制（10步），如需继续请重新发起。"

        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _resume_workflow(self, user_input: str) -> str:
        """恢复暂停的工作流。短输入精确匹配确认/取消，长输入交给 LLM 判断。"""
        confirm_phrases = {"确认", "可以", "继续", "好", "嗯", "是的", "执行", "对", "行", "ok", "好的", "可以啊", "没问题", "干吧", "搞吧"}
        cancel_phrases = {"不行", "不要", "取消", "中止", "停止", "算了", "不做了", "别做了", "不用了", "重来", "撤销", "退回", "换一个", "改一下"}

        text = user_input.strip()
        text_lower = text.lower()

        context = self._workflow_state["context"]
        mode = self._workflow_state.get("mode", "")

        # 短输入（≤6字符）：精确匹配
        if len(text) <= 6:
            if text in confirm_phrases or text_lower in confirm_phrases:
                self._workflow_state = None
                context.append({"role": "user", "content": "用户已确认，请继续执行下一步"})
                reply = self.llm.chat(context, stream=False)
                result = self._run_workflow(context, reply)
                return result if result is not None else "⚠️ 工作流恢复后返回空"

            if text in cancel_phrases or text_lower in cancel_phrases:
                self._workflow_state = None
                self.history.append({"role": "assistant", "content": "已取消当前操作"})
                return "好的，已取消当前操作。还有什么需要帮忙的吗？"

        # 长输入（>6字符）：检查是否以确认/取消短语开头
        for kw in confirm_phrases:
            if text.startswith(kw) and len(text) <= len(kw) + 10:
                self._workflow_state = None
                context.append({"role": "user", "content": f"用户已确认并补充：{user_input}"})
                reply = self.llm.chat(context, stream=False)
                result = self._run_workflow(context, reply)
                return result if result is not None else "⚠️ 工作流恢复后返回空"

        for kw in cancel_phrases:
            if text.startswith(kw) and len(text) <= len(kw) + 10:
                self._workflow_state = None
                self.history.append({"role": "assistant", "content": "已取消当前操作"})
                return "好的，已取消当前操作。还有什么需要帮忙的吗？"

        # 其他情况：当作普通对话，保留工作流状态
        context.append({"role": "user", "content": user_input})
        reply = self.llm.chat(context, stream=False)
        context.append({"role": "assistant", "content": reply})
        self._workflow_state["context"] = context
        self.history.append({"role": "assistant", "content": reply})
        return reply

    # =========================================================
    # 上下文构建
    # =========================================================

    def _build_master_context(self, user_input: str) -> list:
        agent_list = self._build_agent_list()
        workflow_list = self._build_workflow_list()
        system_content = self.MASTER_PROMPT.format(
            agent_list=agent_list, workflow_list=workflow_list
        )
        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.history[-8:])
        return messages

    def _build_agent_list(self) -> str:
        dispatcher = getattr(self, "dispatcher", None)
        if dispatcher is None or not hasattr(dispatcher, "_agents") or not dispatcher._agents:
            return "（暂无可用 SubAgent）"
        lines = []
        for name, agent in dispatcher._agents.items():
            desc = getattr(agent, "description", name)
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)

    def _build_workflow_list(self) -> str:
        try:
            from orchestrator.workflows import get_workflow_list_text
            return get_workflow_list_text()
        except ImportError:
            return "（暂无预设工作模式，由你自行编排）"

    def _load_workflow_template(self, mode: str) -> list[dict]:
        """从预定义模板加载步骤，LLM 未输出步骤时作为兜底"""
        try:
            from orchestrator.workflows import match_workflow
            wf = match_workflow(mode)
            if wf:
                return [
                    {
                        "step": i + 1,
                        "action": step["action"],
                        "agent": step.get("agent", ""),
                        "params": {},
                        "description": step.get("description", ""),
                    }
                    for i, step in enumerate(wf["steps"])
                ]
        except ImportError:
            pass
        return []

    # =========================================================
    # LLM 输出解析
    # =========================================================

    def _parse_mode(self, reply: str) -> str | None:
        m = re.search(r'\[mode:\s*(.+?)\]', reply)
        return m.group(1).strip() if m else None

    def _has_action(self, reply: str, action: str) -> bool:
        return f"[action: {action}]" in reply

    def _extract_description(self, reply: str) -> str | None:
        m = re.search(r'\[description:\s*(.+?)\]', reply)
        return m.group(1).strip() if m else None

    def _parse_all_steps(self, reply: str) -> list[dict]:
        """从 LLM 回复中提取所有工作流步骤"""
        steps = []
        parts = reply.split("[step:")
        for part in parts[1:]:
            step_num = part.split("]")[0].strip() if "]" in part else ""
            body = part[len(step_num) + 1:].strip() if step_num else part
            if not step_num:
                continue
            action_m = re.search(r'\[action:\s*(\w+)\]', body)
            agent_m = re.search(r'\[agent:\s*(.+?)\]', body)
            desc_m = re.search(r'\[description:\s*(.+?)\]', body)
            params = {}
            params_m = re.search(r'\[params:\s*(\{.*?\})\]', body)
            if params_m:
                try:
                    params = json.loads(params_m.group(1))
                except json.JSONDecodeError:
                    pass
            steps.append({
                "step": int(step_num) if step_num.isdigit() else 0,
                "action": action_m.group(1) if action_m else None,
                "agent": agent_m.group(1).strip() if agent_m else None,
                "params": params,
                "description": desc_m.group(1).strip() if desc_m else "",
            })
        return steps

    def _batch_execute_agents(self, steps: list[dict]) -> list[str]:
        """并行执行一批 Agent 调用，跳过未注册的 agent"""
        if self.dispatcher is None:
            unknown = [s.get("agent", "?") for s in steps]
            return [f"⚠️ Agent 调度器未初始化，已跳过: {', '.join(unknown)}"]

        valid_steps = [s for s in steps
                       if s.get("agent") and self.dispatcher.select(s.get("agent"))]
        if not valid_steps:
            unknown = [s.get("agent", "?") for s in steps]
            return [f"⚠️ 以下 Agent 未注册，已跳过: {', '.join(unknown)}"]

        if len(valid_steps) == 1:
            s = valid_steps[0]
            result = self.dispatcher.dispatch(s["agent"], s.get("params", {}), "")
            return [f'[{s["description"]}]\n{result.summary if result.success else result.error}']

        from concurrent.futures import ThreadPoolExecutor, as_completed
        results_text = []
        with ThreadPoolExecutor(max_workers=min(len(valid_steps), 5)) as executor:
            future_map = {
                executor.submit(
                    self.dispatcher.dispatch, s["agent"], s.get("params", {}), ""
                ): s
                for s in valid_steps
            }
            for future in as_completed(future_map):
                s = future_map[future]
                try:
                    result = future.result()
                    text = f'[{s["description"]}]\n{result.summary if result.success else result.error}'
                except Exception as e:
                    text = f'[{s["description"]}]\n❌ 执行失败: {e}'
                results_text.append(text)
        return results_text


    # =========================================================
    # 旧版兼容：Tool 执行
    # =========================================================

    def _build_context(self, user_input: str, agent_results: list) -> list:
        messages = [{
            "role": "system",
            "content": (
                "你是 DeskFlow 桌面助手，用中文回答。简洁专业。\n\n"
                + self.TOOL_DEFINITIONS
                + "\n当用户要求保存/读取/搜索文件时，请使用上述工具。不需要工具时正常回复即可。"
            )
        }]
        messages.extend(self.history[-6:])
        for r in agent_results:
            if r.success:
                messages.append({"role": "system", "content": f"[已执行: {r.summary}]"})
            else:
                messages.append({"role": "system", "content": f"[执行结果: {r.error}]"})
        return messages

    def _execute_tools(self, reply: str) -> list:
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
        params = {}
        for line in body.split("\n"):
            line = line.strip()
            if ":" in line:
                key, val = line.split(":", 1)
                params[key.strip()] = val.strip()
        return params

    def _resolve_safe_path(self, raw_path: str, write: bool = False) -> str:
        """解析并验证路径安全性。write=True 时限制更严格（仅用户目录）。"""
        path = os.path.expanduser(raw_path)
        if not path:
            raise ValueError("路径为空")
        real = os.path.realpath(path)

        home = os.path.realpath(os.path.expanduser("~"))
        allowed = [home]

        if not write:
            # 读操作额外允许临时目录
            import tempfile
            allowed.append(os.path.realpath(tempfile.gettempdir()))

        for root in allowed:
            if real.startswith(root + os.sep) or real == root:
                return real

        raise ValueError(f"路径超出允许范围: {raw_path}")

    def _tool_save_file(self, params: dict) -> str:
        try:
            path = self._resolve_safe_path(
                params.get("path", "~/Desktop/output.txt"), write=True
            )
        except ValueError as e:
            return f"❌ 保存失败: {e}"
        content = params.get("content", "")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ 文件已保存: {path} ({len(content)} 字符)"

    def _tool_search_file(self, params: dict) -> str:
        keyword = params.get("keyword", "")
        raw_path = params.get("path", "~")
        try:
            search_root = self._resolve_safe_path(raw_path, write=False)
        except ValueError:
            search_root = os.path.realpath(os.path.expanduser("~"))
        if not os.path.isdir(search_root):
            return f"❌ 目录不存在: {raw_path}"
        results = []
        for root, dirs, files in os.walk(search_root):
            for f in files:
                if keyword.lower() in f.lower():
                    results.append(os.path.join(root, f))
            if len(results) >= 10:
                break
        if results:
            return f"找到 {len(results)} 个文件:\n" + "\n".join(results[:5])
        return f"未找到包含 '{keyword}' 的文件"

    def _tool_read_file(self, params: dict) -> str:
        raw_path = params.get("path", "")
        if not raw_path:
            return "❌ 未指定文件路径"
        try:
            path = self._resolve_safe_path(raw_path, write=False)
        except ValueError as e:
            return f"❌ 读取失败: {e}"
        if not os.path.exists(path):
            return f"❌ 文件不存在: {path}"
        from core.file_ops import FileOps
        content = FileOps.read(path)
        if len(content) > 2000:
            content = content[:2000] + "\n...(截断)"
        return f"📄 {os.path.basename(path)}:\n{content}"

    def _tool_analyze_excel(self, params: dict) -> str:
        raw_path = params.get("path", "")
        if not raw_path:
            return "❌ 未指定文件路径"
        try:
            path = self._resolve_safe_path(raw_path, write=False)
        except ValueError as e:
            return f"❌ 分析失败: {e}"
        if not os.path.exists(path):
            return f"❌ 文件不存在: {path}"
        import pandas as pd
        try:
            df = pd.read_excel(path) if not path.endswith(".csv") else pd.read_csv(path)
            return (
                f"📊 {os.path.basename(path)}: {len(df)}行×{len(df.columns)}列\n"
                f"列名: {list(df.columns)}\n"
                f"预览:\n{df.head(5).to_string()}"
            )
        except Exception as e:
            return f"❌ 读取失败: {e}"
