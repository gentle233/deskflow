"""总控引擎 - 聊天主循环"""
from orchestrator.intent_router import IntentRouter
from core.llm_gateway import LLMGateway
from orchestrator.scheduler import AgentDispatcher
from core.llm_gateway import LLMGateway

class Orchestrator:
    """用户唯一的入口，负责理解、分解、调度、整合"""

    def __init__(self, llm: LLMGateway):
        self.llm = llm
        self.router = IntentRouter(llm=llm)
        self.dispatcher = AgentDispatcher()
        self.history: list[dict] = []

    def process(self, user_input: str) -> str:
        """处理用户输入，返回最终回复"""
        self.history.append({"role": "user", "content": user_input})

        # 1. 意图识别
        tasks = self.router.route(user_input)

        # 2. 执行任务（chat类型直接跳过，让LLM自己回复）
        agent_results = []
        for t in tasks:
            if t["type"] == "chat":
                continue
            result = self.dispatcher.dispatch(t["type"], t["params"], user_input)
            agent_results.append(result)

        # 3. LLM 整合
        context = self._build_context(user_input, agent_results)
        try:
            reply = self.llm.chat(context, stream=False)
        except Exception as e:
            reply = f"❌ {str(e)}"

        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _build_context(self, user_input: str, agent_results: list) -> list:
        """构建 LLM 上下文"""
        messages = [{
            "role": "system",
            "content": "你是 DeskFlow 桌面助手，用中文回答。简洁专业。\n\n你有以下能力：\n- file_search: 搜索和查找文件\n- doc_read: 读取文档内容\n- doc_write: 生成和保存文档\n- excel_analyze: 分析Excel数据\n- web_search: 联网搜索信息\n\n当用户提出需求时，先利用以上能力获取信息，然后给出完整回复。如果自己无法回答，请如实告知。"
        }]
        messages.extend(self.history[-6:])  # 只保留最近 3 轮
        # 附加 Agent 执行结果
        for r in agent_results:
            if r.success:
                messages.append({"role": "system", "content": f"[Agent: {r.summary}]"})
            else:
                messages.append({"role": "system", "content": f"[Agent 错误: {r.error}]"})
        return messages
