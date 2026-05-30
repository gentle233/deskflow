"""DeskFlow 桌面窗口启动器 — 用 PyWebView 显示原生窗口"""
import sys
import os
import threading
import time
import signal

# 保证可导入项目模块
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# 全局引用，防止 GC
_flask_thread = None
_window = None


def _wait_for_flask(host="127.0.0.1", port=7788, timeout=10):
    """等待 Flask 服务器就绪"""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f"http://{host}:{port}/", timeout=2)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def _start_flask():
    """在后台线程中启动 Flask"""
    from main import app, init_deskflow
    init_deskflow()
    app.run(host="127.0.0.1", port=7788, debug=False, use_reloader=False)


def _on_closed():
    """窗口关闭时退出"""
    import os
    # Windows 上用 taskkill 确保 Flask 线程退出
    if sys.platform == "win32":
        os._exit(0)
    else:
        os._exit(0)


def main():
    global _flask_thread, _window

    # 启动 Flask
    _flask_thread = threading.Thread(target=_start_flask, daemon=True)
    _flask_thread.start()

    # 等待 Flask 就绪
    if not _wait_for_flask():
        print("❌ Flask 启动超时")
        sys.exit(1)

    # 导入 PyWebView（这里 import 确保 pyinstaller 能发现）
    import webview

    # 图标路径
    icon_path = os.path.join(BASE, "ui", "icons", "deskflow.ico")

    # 判断是否首次运行
    from core.config import load_config
    config = load_config()
    start_url = "http://127.0.0.1:7788/settings" if not config.get("first_run") else "http://127.0.0.1:7788/"

    # 创建窗口
    _window = webview.create_window(
        "DeskFlow - 桌面智能助手",
        start_url,
        width=1100,
        height=750,
        resizable=True,
        icon=icon_path,
        easy_drag=True,
    )

    # 启动（tray 托盘模式：关窗口时最小化到托盘）
    webview.start(
        tray=True,
        tray_icon=icon_path,
        tray_text="DeskFlow",
    )


if __name__ == "__main__":
    main()
