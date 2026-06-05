"""配置相关路由"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.config import load_config, save_config, update_config, set_provider_key
from core.llm_gateway import LLMGateway
from core.provider_tester import list_providers, test_provider, test_all_providers
from core.logger import logger

router = APIRouter()


@router.get("/api/config")
def get_config():
    """查看当前配置（隐藏 API Key 全文）"""
    config = load_config()
    safe = dict(config)
    key = safe.get("api_key", "")
    if key:
        safe["api_key"] = key[:8] + "..." + key[-4:]
    return JSONResponse(safe)


@router.post("/api/setup")
def setup():
    """首次配置"""
    data = request.json
    update_config("provider", data.get("provider", "deepseek"))
    update_config("api_key", data.get("api_key", ""))
    update_config("first_run", False)
    _init_orchestrator()
    return JSONResponse({"status": "ok"})


@router.get("/api/provider/check")
def check_provider():
    """检查 API 连接状态"""
    config = load_config()
    if not config.get("api_key"):
        return JSONResponse({"status": "error", "message": "未配置 API Key"})
    try:
        llm = LLMGateway(config.get("provider"), config.get("api_key"))
        llm.chat([{"role": "user", "content": "说一个字"}])
        return JSONResponse({"status": "ok", "message": "连接正常"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


@router.post("/api/config/search")
def save_search_config():
    """保存搜索设置"""
    data = request.json
    if not data:
        return JSONResponse({"status": "error", "error": "无数据"})
    provider = data.get("search_provider", "ddgs")
    if provider not in ("ddgs", "bing"):
        return JSONResponse({"status": "error", "error": "不支持的搜索提供商"})
    update_config("search_provider", provider)
    if provider == "bing" and data.get("bing_api_key"):
        update_config("bing_api_key", data["bing_api_key"])
    return JSONResponse({"status": "ok"})


@router.get("/api/providers")
def api_providers_list():
    """列出所有提供商及 Key 状态"""
    return JSONResponse(list_providers())


@router.post("/api/providers/test")
def api_providers_test():
    """测试指定提供商"""
    data = request.json or {}
    provider = data.get("provider", "")
    api_key = data.get("api_key", "")
    if not provider:
        return JSONResponse({"status": "error", "error": "请指定提供商"}), 400
    result = test_provider(provider, api_key)
    return JSONResponse(result)


@router.post("/api/providers/test-all")
def api_providers_test_all():
    """测试所有已配置 Key 的提供商"""
    results = test_all_providers()
    return JSONResponse(results)


@router.post("/api/providers/set")
def api_providers_set():
    """切换当前使用的提供商"""
    data = request.json or {}
    provider = data.get("provider", "")
    api_key = data.get("api_key", "")
    model = data.get("model", "")

    # 验证提供商
    valid = ["deepseek", "openai", "moonshot", "zhipu", "tongyi"]
    if provider not in valid:
        return JSONResponse({"status": "error", "error": f"不支持的提供商: {provider}"}), 400

    # 保存 Key 并切换
    if api_key:
        set_provider_key(provider, api_key)
    # 先更新提供商名称，再同步 Key（set_provider_key 内部会检查 provider 是否匹配）
    update_config("provider", provider)
    if not api_key:
        from core.config import get_provider_key
        existing = get_provider_key(provider)
        if existing:
            set_provider_key(provider, existing)
    if model:
        update_config("model", model)

    # 重新初始化 orchestrator
    _init_orchestrator()
    logger.info("已切换到提供商: %s", provider)
    return JSONResponse({"status": "ok", "provider": provider})
