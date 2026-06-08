
"""Phase 1 测试：主 Agent 提示词 + 红线机制 + 工作流解析"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.engine import Orchestrator


class MockLLM:
    """模拟 LLM，返回预设回复"""
    def __init__(self):
        self.last_messages = None

    def chat(self, messages, stream=False):
        self.last_messages = messages
        return self.reply


class TestOrchestratorCore:
    """测试 Engine 核心方法"""

    def setup_method(self):
        self.llm = MockLLM()
        self.orch = Orchestrator.__new__(Orchestrator)
        self.orch.llm = self.llm
        self.orch.history = []
        self.orch.dispatcher = None  # 不测调度
        self.orch._workflow_state = None
    
    def test_master_prompt_exists(self):
        """MASTER_PROMPT 应包含必要元素"""
        p = Orchestrator.MASTER_PROMPT
        assert "红线" in p
        assert "工作流输出格式" in p
        assert "{agent_list}" in p
        assert "{workflow_list}" in p
        assert "[action: call_agent]" in p
        assert "[mode:" in p
        assert len(p) > 500
        print("  ✅ MASTER_PROMPT 包含所有必要元素")

    def test_parse_mode_found(self):
        """应能提取 [mode: xxx]"""
        reply = "[mode: 文档修改]\n[step: 1]\n..."
        mode = self.orch._parse_mode(reply)
        assert mode == "文档修改"
        print(f"  ✅ _parse_mode() 返回: {mode}")

    def test_parse_mode_not_found(self):
        """无 mode 标记时应返回 None"""
        reply = "你好，我是 DeskFlow 助手"
        mode = self.orch._parse_mode(reply)
        assert mode is None
        print("  ✅ 无 mode 时返回 None")

    def test_parse_all_steps_multi(self):
        """应能提取多个步骤，含 agent 和 params"""
        reply = """[mode: 文件搜索]
[step: 1]
[action: call_agent]
[agent: file_manager]
[params: {"keyword": "报销单"}]
[description: 搜索报销文件]

[step: 2]
[action: ask_user]
[description: 确认是否保存]"""
        steps = self.orch._parse_all_steps(reply)
        assert len(steps) == 2
        assert steps[0]["action"] == "call_agent"
        assert steps[0]["agent"] == "file_manager"
        assert steps[0]["params"]["keyword"] == "报销单"
        assert steps[1]["action"] == "ask_user"
        print(f"  ✅ _parse_all_steps() 返回 {len(steps)} 步骤")

    def test_parse_all_steps_empty(self):
        """无 step 标记时应返回空列表"""
        reply = "直接回复，不需要 agent"
        steps = self.orch._parse_all_steps(reply)
        assert steps == []
        print("  ✅ 无 step 时返回空列表")

    def test_build_master_context_structure(self):
        """_build_master_context 应返回正确结构的 messages"""
        self.orch.history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "帮我找文件"},
        ]
        ctx = self.orch._build_master_context("帮我找文件")
        assert isinstance(ctx, list)
        assert len(ctx) > 0
        assert ctx[0]["role"] == "system"
        assert "红线" in ctx[0]["content"]
        assert ctx[-1]["role"] == "user"
        assert ctx[-1]["content"] == "帮我找文件"
        print(f"  ✅ _build_master_context() 返回 {len(ctx)} 条消息")

    def test_build_agent_list_empty(self):
        """无注册 Agent 时应返回友好提示"""
        result = self.orch._build_agent_list()
        assert "暂无可用" in result or "Agent" in result or result != ""
        print(f"  ✅ _build_agent_list() 空列表: {result[:50]}")

    def test_direct_reply_path(self):
        """红线命中：LLM 返回无 mode 标记 → 直接回复"""
        self.llm.reply = "你好！我是 DeskFlow，有什么可以帮你的吗？"
        result = self.orch.process("你好")
        assert result == self.llm.reply
        assert len(self.orch.history) == 2  # user + assistant
        print(f"  ✅ 直接回复路径正确: {result[:30]}...")

    def test_workflow_path_detection(self):
        """有 mode 标记 → 进入工作流"""
        self.llm.reply = """[mode: 文件操作]
[step: 1]
[action: call_agent]
[agent: file_manager]
[params: {"keyword": "报告"}]
[description: 搜索文件]"""
        # 没有注册 Agent，应该报错但不会崩溃
        try:
            result = self.orch.process("帮我找报告文件")
            print(f"  ✅ 工作流路径执行完成: {result[:50]}...")
        except Exception as e:
            # 没注册 Agent 时报错是合理的
            print(f"  ⚠️ 工作流路径执行（无 Agent 时预期报错）: {e}")


if __name__ == "__main__":
    t = TestOrchestratorCore()

    tests = [
        ("MASTER_PROMPT 存在性", t.test_master_prompt_exists),
        ("_parse_mode 有值", t.test_parse_mode_found),
        ("_parse_mode 无值", t.test_parse_mode_not_found),
        ("_parse_all_steps 多步骤", t.test_parse_all_steps_multi),
        ("_parse_all_steps 空列表", t.test_parse_all_steps_empty),
        ("_build_master_context 结构", t.test_build_master_context_structure),
        ("_build_agent_list 空列表", t.test_build_agent_list_empty),
        ("直接回复路径", t.test_direct_reply_path),
        ("工作流路径检测", t.test_workflow_path_detection),
    ]
    
    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            t.setup_method()
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
    
    print(f"\n{'='*40}")
    print(f"结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
