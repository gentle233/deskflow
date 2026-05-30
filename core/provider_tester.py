"""DeskFlow 多提供商测试 — 验证各 LLM API 连通性"""
import time
import requests

from core.config import get_provider_key
from core.logger import logger

# 已知提供商列表（与 LLMGateway 保持一致）
PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "desc": "DeepSeek V3/V4",
    },
    "tongyi": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-turbo",
        "desc": "阿里 Qwen 系列",
    },
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "desc": "智谱清言",
    },
    "moonshot": {
        "name": "Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-auto",
        "desc": "月之暗面",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "desc": "GPT 系列",
    },
}


def list_providers() -> list[dict]:
    """列出所有提供商及当前 API Key 状态"""
    result = []
    for key, info in PROVIDERS.items():
        stored_key = get_provider_key(key)
        has_key = bool(stored_key)
        result.append({
            "id": key,
            "name": info["name"],
            "model": info["model"],
            "desc": info["desc"],
            "has_key": has_key,
            "key_preview": stored_key[:8] + "..." + stored_key[-4:] if stored_key else "",
        })
    return result


def test_provider(provider: str, api_key: str = "") -> dict:
    """测试指定提供商的 API 连通性"""
    if provider not in PROVIDERS:
        return {"status": "error", "error": f"未知提供商: {provider}"}

    info = PROVIDERS[provider]
    key = api_key or get_provider_key(provider)
    if not key:
        return {"status": "error", "error": "未配置 API Key"}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # 智谱使用不同的 headers
    if provider == "zhipu":
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    payload = {
        "model": info["model"],
        "messages": [{"role": "user", "content": "说一个字"}],
        "stream": False,
        "max_tokens": 10,
    }

    url = f"{info['base_url']}/chat/completions"

    start = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        elapsed = round(time.time() - start, 2)

        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            model_used = data.get("model", info["model"])
            return {
                "status": "ok",
                "latency": elapsed,
                "model": model_used,
                "reply": content.strip(),
            }
        elif resp.status_code == 401:
            return {"status": "error", "error": "API Key 无效", "latency": elapsed}
        elif resp.status_code == 429:
            return {"status": "error", "error": "请求过于频繁", "latency": elapsed}
        else:
            detail = resp.text[:150]
            return {"status": "error", "error": f"HTTP {resp.status_code}", "detail": detail, "latency": elapsed}

    except requests.exceptions.ConnectionError:
        elapsed = round(time.time() - start, 2)
        return {"status": "error", "error": "连接失败（网络不通或URL错误）", "latency": elapsed}
    except requests.exceptions.Timeout:
        return {"status": "error", "error": "请求超时（15秒）", "latency": 15.0}
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {"status": "error", "error": str(e)[:100], "latency": elapsed}


def test_all_providers() -> list[dict]:
    """测试所有已配置 Key 的提供商"""
    results = []
    for pid in PROVIDERS:
        key = get_provider_key(pid)
        if key:
            logger.info("测试提供商: %s", pid)
            result = test_provider(pid, key)
            result["provider_id"] = pid
            result["provider_name"] = PROVIDERS[pid]["name"]
            results.append(result)
        else:
            results.append({
                "provider_id": pid,
                "provider_name": PROVIDERS[pid]["name"],
                "status": "skip",
                "error": "未配置 Key",
            })
    return results
