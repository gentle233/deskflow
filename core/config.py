"""配置管理 - 用 JSON 文件存储"""
import json
import os

CONFIG_PATH = os.path.expanduser("~/.deskflow/config.json")

DEFAULT_CONFIG = {
    "provider": "deepseek",
    "api_key": "",
    "model": "",
    "provider_keys": {},
    "language": "zh-CN",
    "theme": "light",
    "output_dir": os.path.expanduser("~/Desktop"),
    "first_run": True,
    "search_provider": "ddgs",
    "bing_api_key": "",
    "email": {
        "enabled": False,
        "provider": "QQ邮箱",
        "imap_server": "imap.qq.com",
        "imap_port": 993,
        "smtp_server": "smtp.qq.com",
        "smtp_port": 465,
        "use_ssl": True,
        "email": "",
        "password": "",
        "password_encoded": False,
    },
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 确保新字段存在
    if "provider_keys" not in cfg:
        cfg["provider_keys"] = {}
    if "model" not in cfg:
        cfg["model"] = ""
    return cfg


def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def update_config(key: str, value):
    config = load_config()
    config[key] = value
    save_config(config)


def get_provider_key(provider: str) -> str:
    """获取指定提供商的 API Key"""
    config = load_config()
    keys = config.get("provider_keys", {})
    return keys.get(provider, "")


def set_provider_key(provider: str, key: str):
    """保存指定提供商的 API Key"""
    config = load_config()
    keys = config.get("provider_keys", {})
    keys[provider] = key
    config["provider_keys"] = keys
    # 同步到 api_key（兼容旧代码）
    if provider == config.get("provider"):
        config["api_key"] = key
    save_config(config)
