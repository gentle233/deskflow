"""快捷指令管理"""
import json
import os

SHORTCUTS_PATH = os.path.expanduser("~/.deskflow/shortcuts.json")

DEFAULT_SHORTCUTS = [
    {"trigger": "/date", "command": "今天是几月几号？请告诉我今天的日期", "desc": "查询日期"},
    {"trigger": "/time", "command": "现在几点了？", "desc": "查询时间"},
    {"trigger": "/weather", "command": "今天天气怎么样？", "desc": "查询天气"},
    {"trigger": "/help", "command": "你能做什么？介绍一下你的功能", "desc": "查看帮助"},
]


def load_shortcuts() -> list:
    if not os.path.exists(SHORTCUTS_PATH):
        os.makedirs(os.path.dirname(SHORTCUTS_PATH), exist_ok=True)
        save_shortcuts(DEFAULT_SHORTCUTS)
        return list(DEFAULT_SHORTCUTS)
    with open(SHORTCUTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_shortcuts(shortcuts: list):
    os.makedirs(os.path.dirname(SHORTCUTS_PATH), exist_ok=True)
    with open(SHORTCUTS_PATH, "w", encoding="utf-8") as f:
        json.dump(shortcuts, f, ensure_ascii=False, indent=2)


def add_shortcut(trigger: str, command: str, desc: str = "") -> dict:
    shortcuts = load_shortcuts()
    shortcuts = [s for s in shortcuts if s["trigger"] != trigger]
    shortcuts.append({"trigger": trigger, "command": command, "desc": desc or command[:20]})
    save_shortcuts(shortcuts)
    return {"status": "ok", "shortcuts": shortcuts}


def delete_shortcut(trigger: str) -> dict:
    shortcuts = load_shortcuts()
    shortcuts = [s for s in shortcuts if s["trigger"] != trigger]
    save_shortcuts(shortcuts)
    return {"status": "ok", "shortcuts": shortcuts}
