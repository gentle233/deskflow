"""配置管理 - 用 JSON 文件存储"""
import json
import os

CONFIG_PATH = os.path.expanduser("~/.deskflow/config.json")

DEFAULT_CONFIG = {
    "provider": "deepseek",
    "api_key": "",
    "model": "",
    "language": "zh-CN",
    "theme": "light",
    "output_dir": os.path.expanduser("~/Desktop"),
    "first_run": True,
    "search_provider": "ddgs",
    "bing_api_key": "",
}

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def update_config(key: str, value):
    config = load_config()
    config[key] = value
    save_config(config)
