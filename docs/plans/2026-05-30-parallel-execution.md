# 多任务并行执行 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 让 DeskFlow 能同时执行多个独立 Agent 任务（如"搜索资料+分析报表"同时跑），遇到依赖任务再串行。

**Architecture:** 在 engine.py 的 process() 中引入 ThreadPoolExecutor。intent_router.py 的 LLM prompt 增加 parallel_groups 字段标记可并行的任务组。scheduler.py 增加 batch_dispatch() 方法。

**Tech Stack:** Python 3.11, concurrent.futures.ThreadPoolExecutor, asyncio (可选 fallback)

---

### Task 1: 修改 IntentRouter — LLM prompt 增加并行标记

**Objective:** 让 LLM 在任务分解时输出哪些任务可以并行执行

**Files:**
- Modify: `orchestrator/intent_router.py` (CAPABILITIES_PROMPT 和 route 方法)

**修改内容：**

1. 在 CAPABILITIES_PROMPT 的示例2中，增加 parallel_groups 字段：

原输出格式：
```json
{
  "reasoning": "...",
  "tasks": [...]
}
```

新输出格式：
```json
{
  "reasoning": "...",
  "parallel_groups": [
    ["task_1", "task_2"],  
    ["task_3"]
  ],
  "tasks": [
    {"id": "task_1", "type": "excel_analyze", "description": "分析销售报表", "params": {}},
    {"id": "task_2", "type": "web_search", "description": "搜索行业数据", "params": {"keyword": "行业趋势"}},
    {"id": "task_3", "type": "doc_write", "description": "写总结报告", "params": {}}
  ]
}
```

解释：parallel_groups 表示哪些 task_id 可以同时执行。
- task_1 和 task_2 没有依赖关系 → 放在同一组，并行执行
- task_3 依赖前面两个的结果 → 在下一组，串行执行

2. `_llm_route()` 返回时改为返回 `(tasks, parallel_groups)` 元组

3. `route()` 方法返回 `(tasks, parallel_groups)` 

**验证：**
- 调用 `route("帮我分析报表然后写总结")` 应返回 parallel_groups
- 调用 `route("你好")` 返回单组
- 向后兼容：无 parallel_groups 时兜底为全串行

---

### Task 2: 修改 Scheduler — 增加 batch_dispatch 方法

**Objective:** 支持批量并行派发 Agent 任务

**Files:**
- Modify: `orchestrator/scheduler.py`

**代码：**

在 AgentDispatcher 类中增加方法：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_dispatch(self, tasks: list[tuple]) -> list[Result]:
    """并行执行一批独立任务"
    Args:
        tasks: [(task_type, params, context), ...]
    Returns:
        list[Result]
    """
    if len(tasks) == 1:
        # 单个任务不用开线程
        t = tasks[0]
        return [self.dispatch(t[0], t[1], t[2])]
    
    results = []
    with ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as executor:
        future_map = {
            executor.submit(self.dispatch, t[0], t[1], t[2]): t
            for t in tasks
        }
        for future in as_completed(future_map):
            try:
                results.append(future.result())
            except Exception as e:
                t = future_map[future]
                results.append(Result("", False, error=f"任务执行失败: {e}"))
    return results
```

**验证：**
- 单任务：返回单个 Result 列表
- 多任务：返回按完成顺序的结果列表
- 异常：单个失败不阻塞其他任务

---

### Task 3: 修改 Engine — 并行执行 Agent 任务

**Objective:** Orchestrator.process() 中按 parallel_groups 分组执行

**Files:**
- Modify: `orchestrator/engine.py`

**修改内容：**

1. `__init__` 中无需新增属性（复用已有 dispatcher）

2. `process()` 方法修改核心逻辑：

```python
def process(self, user_input: str) -> str:
    self.history.append({"role": "user", "content": user_input})

    # 1. 意图识别（获取任务 + 并行分组）
    tasks, parallel_groups = self.router.route(user_input)
    agent_results = []
    
    # 2. 按组执行（组内并行，组间串行）
    task_map = {t["id"]: t for t in tasks if t["type"] != "chat"}
    
    if parallel_groups:
        for group_ids in parallel_groups:
            group_tasks = []
            for tid in group_ids:
                if tid in task_map:
                    t = task_map[tid]
                    group_tasks.append((t["type"], t["params"], user_input))
            
            if not group_tasks:
                continue
            
            # 并行执行这一组
            batch_results = self.dispatcher.batch_dispatch(group_tasks)
            agent_results.extend(batch_results)
    else:
        # 旧版兼容：全串行
        for t in tasks:
            if t["type"] == "chat":
                continue
            result = self.dispatcher.dispatch(t["type"], t["params"], user_input)
            agent_results.append(result)

    # 3-4. 构建上下文 + LLM 调用 + Tool 执行（不变）
    ... # 保持现有代码不变
```

3. `_build_context()` 无需修改（已支持多个 agent_results）

**验证：**
- "帮我找文件" → 单任务，行为不变
- "搜资料+分析报表" → 两个独立任务并行执行
- "你好" → 闲聊，不走 Agent

---

### Task 4: 验证 + 测试

**Objective:** 确保并行执行正确工作，无回归

**Files:**
- Modify: `tests/test_orchestrator.py`

**测试用例：**

1. `test_parallel_independent_tasks` — 两个独立任务并行执行
2. `test_sequential_dependent_tasks` — 依赖任务保持串行
3. `test_single_task_no_change` — 单任务行为不变
4. `test_chat_no_agent` — 闲聊不走 Agent
5. `test_parallel_error_isolation` — 一个失败不影响其他

**验证命令：**
```bash
cd ~/deskflow
python -m pytest tests/ -v
python -m pytest tests/test_orchestrator.py -v
```

---

### Task 5: 更新 TODO.md

**Objective:** 标记"多任务并行执行"为已完成

**Files:**
- Modify: `TODO.md`

将 `- [ ] 多任务并行执行` 改为 `- [x] 多任务并行执行`

---
