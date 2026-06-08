"""Orchestrator 引擎单元测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator.engine import Orchestrator


class MockLLM:
    def __init__(self):
        self.reply = ""
        self.last_messages = None

    def chat(self, messages, stream=False):
        self.last_messages = messages
        return self.reply


def test_parse_all_steps():
    orch = Orchestrator.__new__(Orchestrator)
    reply = """[mode: 文档修改]
[step: 1]
[action: call_agent]
[agent: document]
[params: {"topic": "test"}]
[description: 读取文档]

[step: 2]
[action: ask_user]
[description: 确认修改方案]"""

    steps = orch._parse_all_steps(reply)
    assert len(steps) == 2, f"Expected 2 steps, got {len(steps)}"
    assert steps[0]["action"] == "call_agent"
    assert steps[0]["agent"] == "document"
    assert steps[0]["params"] == {"topic": "test"}
    assert steps[0]["step"] == 1
    assert steps[1]["action"] == "ask_user"
    assert steps[1]["step"] == 2
    print("OK: _parse_all_steps")


def test_parse_mode():
    orch = Orchestrator.__new__(Orchestrator)
    assert orch._parse_mode("[mode: 数据分析]") == "数据分析"
    assert orch._parse_mode("hello world") is None
    assert orch._parse_mode("[mode:  文档写作  ]\n[step: 1]") == "文档写作"
    print("OK: _parse_mode")


def test_execute_tools_save():
    orch = Orchestrator.__new__(Orchestrator)
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "deskflow_test.txt")
    reply = f"""[TOOL: save_file]
path: {tmp}
content: hello test
[/TOOL]"""
    results = orch._execute_tools(reply)
    assert len(results) == 1
    assert "已保存" in results[0]
    assert os.path.exists(tmp)
    with open(tmp, "r") as f:
        assert f.read() == "hello test"
    os.remove(tmp)
    print("OK: _execute_tools save_file")


def test_execute_tools_unknown():
    orch = Orchestrator.__new__(Orchestrator)
    reply = """[TOOL: nonexistent]
some content
[/TOOL]"""
    results = orch._execute_tools(reply)
    assert len(results) == 1
    assert "未知工具" in results[0]
    print("OK: _execute_tools unknown tool")


def test_resume_workflow_confirm():
    orch = Orchestrator.__new__(Orchestrator)
    orch._workflow_state = {
        "context": [{"role": "system", "content": "test"}],
        "step": 1,
        "mode": "文档写作",
    }
    llm = MockLLM()
    llm.reply = "好的，已为您完成"
    orch.llm = llm
    orch.history = []
    orch.dispatcher = None

    result = orch._resume_workflow("确认")
    assert result is not None
    assert orch._workflow_state is None  # state cleared
    print("OK: _resume_workflow confirm")


def test_resume_workflow_cancel():
    orch = Orchestrator.__new__(Orchestrator)
    orch._workflow_state = {
        "context": [{"role": "system", "content": "test"}],
        "step": 1,
        "mode": "文档写作",
    }
    llm = MockLLM()
    orch.llm = llm
    orch.history = []
    orch.dispatcher = None

    result = orch._resume_workflow("取消")
    assert result is not None
    assert "已取消" in result
    assert orch._workflow_state is None
    print("OK: _resume_workflow cancel")


def test_build_agent_list():
    orch = Orchestrator.__new__(Orchestrator)
    orch.dispatcher = None
    result = orch._build_agent_list()
    assert "暂无可用" in result
    print("OK: _build_agent_list empty")


def test_direct_reply():
    llm = MockLLM()
    llm.reply = "你好！有什么可以帮你的？"
    orch = Orchestrator(llm)
    result = orch.process("你好")
    assert result == llm.reply
    assert len(orch.history) == 2  # user + assistant
    print("OK: direct reply path")


if __name__ == "__main__":
    tests = [
        ("_parse_all_steps", test_parse_all_steps),
        ("_parse_mode", test_parse_mode),
        ("_execute_tools save_file", test_execute_tools_save),
        ("_execute_tools unknown tool", test_execute_tools_unknown),
        ("_resume_workflow confirm", test_resume_workflow_confirm),
        ("_resume_workflow cancel", test_resume_workflow_cancel),
        ("_build_agent_list empty", test_build_agent_list),
        ("direct reply path", test_direct_reply),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*40}")
    print(f"Result: {passed} passed, {failed} failed, {len(tests)} total")
