"""
DeskFlow 自动学习 — 采集器
3 路采集：文件监听(watchdog) + 剪贴板轮询 + 窗口焦点
"""
import os
import threading
import time
import platform

from autolearn.models import log_event

# 监听的目标文件夹（用户桌面/文档/下载）
WATCH_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
]

# 全局运行标志
_running = False
_observers = []


# ══════════════════════════════════════════════════════════════════════
# 1) Watchdog 文件监听
# ══════════════════════════════════════════════════════════════════════

class FileWatcher:
    """监听文件操作"""

    def __init__(self):
        self.observer = None
        self._setup_watchdog()

    def _setup_watchdog(self):
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def on_modified(self, event):
                    if not event.is_directory and _running:
                        self._log_event('file_modified', event)

                def on_created(self, event):
                    if not event.is_directory and _running:
                        self._log_event('file_created', event)

                def on_deleted(self, event):
                    if not event.is_directory and _running:
                        self._log_event('file_deleted', event)

                @staticmethod
                def _log_event(etype, event):
                    fpath = event.src_path
                    folder = os.path.dirname(fpath)
                    # 只记录常见办公文档
                    ext = os.path.splitext(fpath)[1].lower()
                    if ext in ('.xlsx', '.xls', '.docx', '.doc', '.pptx', '.ppt',
                               '.pdf', '.txt', '.csv', '.md', '.py', '.js', '.html',
                               '.json', '.yaml', '.yml', '.xml'):
                        log_event(etype, source='watchdog',
                                  file_path=fpath, folder_path=folder)

            self.handler = _Handler()
            self.observer = Observer()

            valid_dirs = [d for d in WATCH_DIRS if os.path.isdir(d)]
            for d in valid_dirs:
                self.observer.schedule(self.handler, path=d, recursive=False)
            if not valid_dirs:
                # fallback: 监听用户目录
                home = os.path.expanduser("~")
                self.observer.schedule(self.handler, path=home, recursive=False)
        except ImportError:
            self.observer = None

    def start(self):
        if self.observer:
            self.observer.start()
            _observers.append(self.observer)

    def stop(self):
        if self.observer:
            self.observer.stop()


# ══════════════════════════════════════════════════════════════════════
# 2) 剪贴板轮询
# ══════════════════════════════════════════════════════════════════════

class ClipboardPoller:
    """轮询剪贴板变化"""

    def __init__(self, interval=5.0):
        self.interval = interval
        self._thread = None
        self._last_text = ""

    def start(self):
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        import pyperclip
        self._last_text = ""
        while _running:
            try:
                new_text = pyperclip.paste()
                if new_text and new_text != self._last_text and len(new_text) > 3:
                    self._last_text = new_text
                    log_event('clipboard', source='clipboard_poll',
                              text_snippet=new_text[:300])
            except Exception:
                pass  # 剪贴板不可用时静默跳过
            time.sleep(self.interval)

    def stop(self):
        pass  # 线程是 daemon，随进程退出


# ══════════════════════════════════════════════════════════════════════
# 3) 窗口焦点轮询
# ══════════════════════════════════════════════════════════════════════

class WindowFocusTracker:
    """轮询当前活跃窗口"""

    def __init__(self, interval=30.0):
        self.interval = interval
        self._thread = None
        self._last_title = ""

    def start(self):
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        while _running:
            try:
                title = self._get_active_window()
                if title and title != self._last_title:
                    self._last_title = title
                    log_event('app_focus', source='focus_poll',
                              text_snippet=title[:200])
            except Exception:
                pass
            time.sleep(self.interval)

    @staticmethod
    def _get_active_window() -> str:
        system = platform.system()
        try:
            if system == 'Windows':
                import win32gui
                return win32gui.GetWindowText(win32gui.GetForegroundWindow())
            elif system == 'Linux':
                import subprocess
                result = subprocess.run(
                    ['xdotool', 'getactivewindow', 'getwindowname'],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
            elif system == 'Darwin':
                import subprocess
                result = subprocess.run(
                    ['osascript', '-e',
                     'tell application "System Events" to get name of first process whose frontmost is true'],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
        except Exception:
            return ''
        return ''

    def stop(self):
        pass


# ══════════════════════════════════════════════════════════════════════
# 总控
# ══════════════════════════════════════════════════════════════════════

def start_collectors():
    """启动所有采集器"""
    global _running
    if _running:
        return
    _running = True

    watcher = FileWatcher()
    clipboard = ClipboardPoller()
    focus = WindowFocusTracker()

    watcher.start()
    clipboard.start()
    focus.start()

    return watcher, clipboard, focus


def stop_collectors():
    """停止所有采集器"""
    global _running
    _running = False
    for obs in _observers:
        try:
            obs.stop()
        except Exception:
            pass
    _observers.clear()
