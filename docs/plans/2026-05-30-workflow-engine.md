# DeskFlow 工作流引擎 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan phase-by-phase.

**Goal:** 给 DeskFlow 注入工作流引擎——主 Agent 前置提示词 + 红线机制 + 工作模式 + SubAgent 逐级调度

## Phase 1: 主 Agent 提示词 + 红线机制（基础）

### Task 1.1: 设计主 Agent System Prompt

**Files:** Modify: `orchestrator/engine.py`

在 Orchestrator 中新增 MASTER_PROMPT 常量，定义：
- 核心规则（红线）：直接能答的→直接聊，不进工作流
- 需要工具/信息的→进入工作流模式
- 工作流输出格式：[mode: 名称] [step: N] [action: call_agent] [agent: xxx] [params: {}]
- {agent_list} 运行时动态填充

验证：用户说"你好"→直接回复无mode标记；说"帮我找文件"→输出mode+step

### Task 1.2: 重写 Engine.process()

**Files:** Modify: `orchestrator/engine.py`

新流程：
1. _build_master_context() 组装含 MASTER_PROMPT 的 messages
2. 调 LLM
3. _parse_mode(reply) 检查是否有 mode 标记→无则直接回复
4. 有 mode→进入最多10步的工作流循环
5. _parse_agent_call(reply) 提取 agent 调用参数
6. dispatcher.dispatch() 执行 SubAgent
7. 结果喂回 LLM→继续

新增 helper: _parse_mode(), _parse_agent_call(), _build_master_context()

### Task 1.3: Agent 列表动态注入

**Files:** Modify: agents/base_agent.py, orchestrator/engine.py

- BaseAgent 增加 get_capability_description()
- 各 Agent 实现该方法返回有意义的描述
- Engine 初始化时自动收集 _build_agent_list()

### Task 1.4: 测试 Phase 1

**Files:** Modify: tests/test_orchestrator.py

测试用例：直接回复/进入工作流/agent调用解析/未知agent处理

---

## Phase 2: 工作模式定义

### Task 2.1: 设计工作模式注册表

**Files:** Create: orchestrator/workflows.py

预定义模式：document_edit, data_analysis, information_search, free_form
每种模式含：name, trigger, steps[]

### Task 2.2: 工作模式匹配

MASTER_PROMPT 中注入 {workflow_list}
LLM 自动匹配最合适的模式，按 steps 执行

---

## Phase 3: 用户确认机制

### Task 3.1: ask_user 步骤处理

Engine 识别 ask_user 步骤，保存工作流状态，暂停等用户确认
用户确认后恢复，用户否定后回退

---

## Phase 4: 并行 + 收尾

### Task 4.1: 并行 SubAgent
### Task 4.2: 更新 TODO + Wiki
