"""总控单元测试"""
import sys; sys.path.insert(0, "..")
from orchestrator.intent_router import IntentRouter

def test_intent_router():
    router = IntentRouter()
    tasks = router.route("帮我找一下月报")
    assert any(t["type"] == "file_search" for t in tasks)
    print("OK: intent_router")

def test_normal_chat():
    router = IntentRouter()
    tasks = router.route("你好，今天天气怎么样")
    assert len(tasks) == 1 and tasks[0]["type"] == "chat"
    print("OK: normal chat")

if __name__ == "__main__":
    test_intent_router()
    test_normal_chat()
    print("All tests passed")
