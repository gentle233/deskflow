"""DeskFlow 桌面窗口启动器 — 用 PyWebView 显示原生窗口"""

import sys
import os
import threading
import time
import traceback
from datetime import datetime

# ── 启动日志：所有输出追到文件，console=False 时也能排查 ──
LOG_DIR = os.path.join(os.path.expanduser("~"), ".deskflow")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "run.log")


def _log(msg: str):
    """写启动日志"""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass  # 日志写失败也不能崩


def _init_logging():
    """将 stdout/stderr 重定向到日志，并设全局异常钩子"""
    # 劫持 print
    class LogWriter:
        def write(self, text):
            if text.strip():
                _log(text.strip())
        def flush(self):
            pass

    sys.stdout = LogWriter()
    sys.stderr = LogWriter()

    # 全局未捕获异常 → 写日志
    def global_excepthook(exc_type, exc_value, exc_tb):
        _log("💥 未捕获异常:")
        for line in traceback.format_exception(exc_type, exc_value, exc_tb):
            _log("  " + line.rstrip())
        os._exit(1)

    sys.excepthook = global_excepthook

    _log("=" * 50)
    _log("🚀 DeskFlow 启动...")


# ── 保证可导入项目模块 ──
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# 全局引用，防止 GC
_flask_thread = None
_window = None


def _wait_for_flask(host="127.0.0.1", port=7788, timeout=15):
    """等待 Flask 服务器就绪"""
    import urllib.request
    import urllib.error
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f"http://{host}:{port}/", timeout=2)
            return True
        except urllib.error.URLError as e:
            _log(f"  Flask 未就绪... ({e.reason})")
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)
    return False


def _start_flask():
    """在后台线程中启动 Flask"""
    try:
        _log("  Flask 启动中...")
        from main import app, init_deskflow
        init_deskflow()
        _log("  Flask 初始化完成，开始监听 7788 端口")
        app.run(host="127.0.0.1", port=7788, debug=False, use_reloader=False)
    except Exception as e:
        _log(f"❌ Flask 线程崩溃: {e}")
        for line in traceback.format_exc().split("\n"):
            _log(f"  {line}")


def _on_closed():
    """窗口关闭时退出"""
    _log("🛑 窗口已关闭")
    os._exit(0)


def main():
    global _flask_thread, _window

    _init_logging()

    # ── 启动 Flask ──
    _flask_thread = threading.Thread(target=_start_flask, daemon=True)
    _flask_thread.start()

    # ── 等待 Flask 就绪 ──
    _log("  等待 Flask 就绪...")
    if not _wait_for_flask():
        _log("❌ Flask 启动超时 (15s)，退出")
        sys.exit(1)
    _log("✅ Flask 就绪")

    # ── 打开 PyWebView 窗口 ──
    try:
        import webview
        _log("  PyWebView 已加载")
    except ImportError as e:
        _log(f"❌ 无法导入 PyWebView: {e}")
        _log("  ⚠ 尝试用浏览器回退方案...")
        import webbrowser
        webbrowser.open("http://127.0.0.1:7788/")
        _log("✅ 已在浏览器中打开，手动关闭终端退出")
        # 进程保持运行
        while True:
            time.sleep(10)
        return

    # 图标路径
    icon_path = os.path.join(BASE, "ui", "icons", "deskflow.ico")

    # 判断是否首次运行
    from core.config import load_config
    config = load_config()
    start_url = "http://127.0.0.1:7788/settings" if not config.get("first_run") else "http://127.0.0.1:7788/"
    _log(f"  首屏 URL: {start_url}")

    # 创建窗口
    _log("  创建窗口...")
    _window = webview.create_window(
        "DeskFlow - 桌面智能助手",
        start_url,
        width=1100,
        height=750,
        resizable=True,
        icon=icon_path,
        easy_drag=True,
    )

    # 启动（tray 托盘模式）
    _log("✅ 窗口已创建，等待用户操作")
    _log("=" * 50)
    webview.start(
        tray=True,
        tray_icon=icon_path,
        tray_text="DeskFlow",
    )


if __name__ == "__main__":
    main()
