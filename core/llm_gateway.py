"""LLM API 统一网关 - 支持多提供商流式输出"""
import json
import requests
from typing import Optional, Callable

class LLMGateway:
    """封装 LLM API 调用，支持流式输出和多提供商"""

    PROVIDERS = {
        "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
        "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
        "moonshot": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-auto"},
        "zhipu": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
        "tongyi": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-turbo"},
    }

    def __init__(self, provider: str = "deepseek", api_key: str = ""):
        if provider not in self.PROVIDERS:
            raise ValueError(f"不支持的提供商: {provider}，支持: {list(self.PROVIDERS.keys())}")
        self.provider = provider
        self.api_key = api_key
        self.base_url = self.PROVIDERS[provider]["base_url"]
        self.model = self.PROVIDERS[provider]["model"]

    def chat(self, messages: list, stream: bool = False,
             on_token: Optional[Callable] = None) -> str:
        """发送聊天请求，支持流式和非流式"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers, json=payload, stream=stream, timeout=120
        )
        if resp.status_code == 401:
            raise PermissionError("API Key 无效或未设置，请检查设置中的 API Key")
        elif resp.status_code == 429:
            raise ConnectionError("API 请求过于频繁，请稍后再试")
        elif resp.status_code >= 400:
            raise ConnectionError(f"API 请求失败 (HTTP {resp.status_code}): {resp.text[:100]}")
        resp.raise_for_status()

        if stream:
            full = ""
            for line in resp.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                full += delta
                                if on_token:
                                    on_token(delta)
                        except json.JSONDecodeError:
                            pass
            return full
        else:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
