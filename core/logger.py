"""DeskFlow 日志系统 — 文件日志 + 滚动轮转 + 查看/清理 API"""
import logging
import os
import re
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.expanduser("~/.deskflow")
LOG_PATH = os.path.join(LOG_DIR, "deskflow.log")


def setup_logger():
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 避免重复添加 handler
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return logging.getLogger("deskflow")

    # 文件 handler — 5MB 轮转，保留 3 个备份
    fh = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root.addHandler(fh)

    # 控制台 handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "\033[36m%(asctime)s\033[0m [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(ch)

    return logging.getLogger("deskflow")


logger = setup_logger()


def get_log_lines(count: int = 200, level: str = "", search: str = "") -> dict:
    """读取最近 N 行日志，支持按级别筛选和搜索关键词"""
    if not os.path.exists(LOG_PATH):
        return {"lines": [], "total_lines": 0, "file_size_mb": 0.0}

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
    except Exception:
        return {"lines": [], "total_lines": 0, "file_size_mb": 0.0}

    total = len(all_lines)
    size_mb = round(os.path.getsize(LOG_PATH) / (1024 * 1024), 2)

    # 筛选
    if level:
        level_tag = f"[{level}]"
        filtered = [l for l in all_lines if level_tag in l]
    else:
        filtered = all_lines

    if search:
        filtered = [l for l in filtered if search.lower() in l.lower()]

    # 取最近 N 行
    lines = [l.rstrip("\n\r") for l in filtered[-count:]]

    return {
        "lines": lines,
        "total_lines": total,
        "filtered_lines": len(filtered),
        "file_size_mb": size_mb,
        "file_path": LOG_PATH,
    }


def clear_logs() -> dict:
    """清空日志文件"""
    try:
        open(LOG_PATH, "w").close()
        logger.info("日志已手动清空")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
