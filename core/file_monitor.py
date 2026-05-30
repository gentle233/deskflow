"""DeskFlow 文件监控 — watchdog 驱动，监听文件变化"""
import os
import threading
import time
from collections import deque
from datetime import datetime

from core.config import load_config, update_config
from core.logger import logger

# 默认监控目录（仅桌面/文档/下载存在时生效）
DEFAULT_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
]

_MAX_EVENTS = 500


class _EventHandler:
    """watchdog 事件处理器"""

    def __init__(self, callback):
        self.callback = callback

    def dispatch(self, event):
        """watchdog 会调用 dispatch"""
        if event.is_directory:
            return
        src = event.src_path
        if hasattr(event, 'dest_path'):
            # moved 事件有两个路径
            self.callback("moved", src, os.path.dirname(src), event.dest_path)
        elif event.event_type == "created":
            self.callback("created", src, os.path.dirname(src))
        elif event.event_type == "modified":
            self.callback("modified", src, os.path.dirname(src))
        elif event.event_type == "deleted":
            self.callback("deleted", src, os.path.dirname(src))


class FileMonitor:
    """文件监控服务（单例）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._observer = None
        self._running = False
        self._events = deque(maxlen=_MAX_EVENTS)
        self._event_lock = threading.Lock()
        self._watch_thread = None
        self._handler = _EventHandler(self._on_event)

    # ── 公开 API ──────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watched_dirs(self) -> list:
        """返回当前监控的目录列表"""
        config = load_config()
        dirs = config.get("monitor_dirs", [])
        # 确保默认目录存在
        if not dirs:
            dirs = [d for d in DEFAULT_DIRS if os.path.isdir(d)]
            if not dirs:
                dirs = [os.path.expanduser("~")]
        return dirs

    def start(self):
        """启动监控"""
        if self._running:
            return False
        dirs = self.watched_dirs
        if not dirs:
            logger.warning("文件监控: 没有可监控的目录")
            return False

        self._running = True
        self._watch_thread = threading.Thread(
            target=self._run_observer, args=(list(dirs),), daemon=True
        )
        self._watch_thread.start()
        logger.info("文件监控已启动 — 监控 %d 个目录", len(dirs))
        for d in dirs:
            logger.info("  监控目录: %s", d)
        return True

    def stop(self):
        """停止监控"""
        self._running = False
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None
        logger.info("文件监控已停止")

    def restart(self):
        """重启监控（目录变更后调用）"""
        self.stop()
        time.sleep(0.3)
        return self.start()

    def add_directory(self, path: str) -> dict:
        """添加监控目录"""
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            return {"status": "error", "error": f"目录不存在: {path}"}
        config = load_config()
        dirs = config.get("monitor_dirs", [])
        # 如果还没有自定义目录，先加载默认
        if not dirs:
            dirs = [d for d in DEFAULT_DIRS if os.path.isdir(d)]
        if path in dirs:
            return {"status": "error", "error": "该目录已在监控中"}
        dirs.append(path)
        update_config("monitor_dirs", dirs)
        self.restart()
        logger.info("文件监控: 添加目录 %s", path)
        return {"status": "ok"}

    def remove_directory(self, path: str) -> dict:
        """移除监控目录"""
        path = os.path.abspath(os.path.expanduser(path))
        config = load_config()
        dirs = config.get("monitor_dirs", [])
        if path not in dirs:
            return {"status": "error", "error": "该目录不在监控列表中"}
        dirs.remove(path)
        update_config("monitor_dirs", dirs)
        self.restart()
        logger.info("文件监控: 移除目录 %s", path)
        return {"status": "ok"}

    def get_events(self, count: int = 50, event_type: str = "", search: str = "") -> list:
        """获取最近的事件（从新到旧）"""
        with self._event_lock:
            all_events = list(self._events)
        # 按时间倒序（最新在前）
        all_events.reverse()

        # 筛选
        if event_type:
            all_events = [e for e in all_events if e["event_type"] == event_type]
        if search:
            all_events = [e for e in all_events if search.lower() in e["file_path"].lower()]

        return all_events[:count]

    def get_status(self) -> dict:
        """获取监控状态摘要"""
        with self._event_lock:
            event_count = len(self._events)
        dirs = self.watched_dirs
        return {
            "running": self._running,
            "watched_dirs": dirs,
            "event_count": event_count,
        }

    # ── 内部 ──────────────────────────────────────────────────

    def _run_observer(self, dirs: list):
        """在子线程中运行 watchdog Observer"""
        try:
            from watchdog.observers import Observer

            self._observer = Observer()
            for d in dirs:
                if os.path.isdir(d):
                    self._observer.schedule(self._handler, path=d, recursive=False)
            self._observer.start()
            while self._running:
                time.sleep(0.5)
            self._observer.stop()
            self._observer.join(timeout=2)
        except ImportError:
            logger.error("watchdog 未安装，文件监控不可用")
            self._running = False
        except Exception as e:
            logger.error("文件监控异常: %s", e)
            self._running = False

    def _on_event(self, event_type: str, file_path: str, folder_path: str, dest_path: str = ""):
        """事件回调（由 EventHandler 调用）"""
        if not self._running:
            return
        now = datetime.now().isoformat(timespec="seconds")
        size = 0
        try:
            if event_type != "deleted" and os.path.isfile(file_path):
                size = os.path.getsize(file_path)
        except Exception:
            pass

        event = {
            "timestamp": now,
            "event_type": event_type,
            "file_path": file_path,
            "folder_path": folder_path,
            "file_name": os.path.basename(file_path),
            "file_size": size,
            "dest_path": dest_path,
        }
        with self._event_lock:
            self._events.append(event)

        # 日志记录（简短版本）
        if event_type == "created":
            logger.info("📄 新文件: %s", os.path.basename(file_path))
        elif event_type == "modified":
            pass  # 修改事件太频繁，不记日志避免刷屏
        elif event_type == "deleted":
            logger.info("🗑 删除: %s", os.path.basename(file_path))
        elif event_type == "moved":
            logger.info("📦 移动: %s → %s",
                        os.path.basename(file_path),
                        os.path.basename(dest_path) if dest_path else "?")


# 全局单例
_monitor = None


def get_monitor() -> FileMonitor:
    global _monitor
    if _monitor is None:
        _monitor = FileMonitor()
    return _monitor
