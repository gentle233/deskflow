"""DeskFlow 窗口操作 Agent — pywinauto 桌面自动化（仅 Windows）"""
import sys
import os
from agents.base_agent import BaseAgent, Task, Result
from core.logger import logger

try:
    import pywinauto
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False


def _win_check() -> str | None:
    """检查是否可用，返回 None 表示可用，否则返回错误信息"""
    if sys.platform != "win32":
        return "当前系统不是 Windows，窗口操作不可用"
    if not HAS_PYWINAUTO:
        return "pywinauto 未安装，请运行: pip install pywinauto uiautomation"
    return None


class WindowOpsAgent(BaseAgent):
    name = "window_ops"
    description = "Windows 窗口操作：列出/激活/关闭窗口、输入文字、点击按钮"

    def can_handle(self, task: Task) -> bool:
        return task.type in (
            "window_list", "window_activate", "window_close",
            "window_type", "window_click", "window_screenshot",
            "window_minimize",
        )

    def execute(self, task: Task) -> Result:
        err = _win_check()
        if err:
            return Result(task.id, False, error=err)

        try:
            if task.type == "window_list":
                return self._list_windows(task)
            elif task.type == "window_activate":
                return self._activate_window(task)
            elif task.type == "window_close":
                return self._close_window(task)
            elif task.type == "window_type":
                return self._type_text(task)
            elif task.type == "window_click":
                return self._click_button(task)
            elif task.type == "window_screenshot":
                return self._screenshot(task)
            elif task.type == "window_minimize":
                return self._minimize_windows(task)
            return Result(task.id, False, error=f"不支持的任务类型: {task.type}")
        except Exception as e:
            logger.error("窗口操作失败 [%s]: %s", task.type, e)
            return Result(task.id, False, error=f"窗口操作失败: {e}")

    def _get_app(self, title: str):
        """根据标题查找窗口，返回 Application 对象"""
        from pywinauto import Application
        # 先尝试精确匹配
        try:
            app = Application(backend="uia").connect(title=title)
            return app
        except Exception:
            pass
        # 模糊匹配
        try:
            app = Application(backend="uia").connect(title_re=f".*{title}.*")
            return app
        except Exception:
            raise RuntimeError(f"未找到窗口: {title}")

    def _list_windows(self, task: Task) -> Result:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        items = []
        for w in windows:
            try:
                t = w.window_text()
                if t.strip():
                    items.append(t)
            except Exception:
                pass
        summary = f"找到 {len(items)} 个可见窗口"
        return Result(task.id, True, summary=summary, data=items[:30])

    def _activate_window(self, task: Task) -> Result:
        title = task.params.get("title", "")
        if not title:
            return Result(task.id, False, error="请指定窗口标题")
        app = self._get_app(title)
        win = app.top_window()
        win.set_focus()
        return Result(task.id, True, summary=f"已激活窗口: {title}")

    def _close_window(self, task: Task) -> Result:
        title = task.params.get("title", "")
        if not title:
            return Result(task.id, False, error="请指定窗口标题")
        app = self._get_app(title)
        win = app.top_window()
        win.close()
        return Result(task.id, True, summary=f"已关闭窗口: {title}")

    def _type_text(self, task: Task) -> Result:
        title = task.params.get("title", "")
        text = task.params.get("text", "")
        if not text:
            return Result(task.id, False, error="请输入要输入的文字")
        if title:
            app = self._get_app(title)
            win = app.top_window()
            win.set_focus()
        from pywinauto.keyboard import send_keys
        send_keys(text)
        return Result(task.id, True, summary=f"已输入 {len(text)} 个字符")

    def _click_button(self, task: Task) -> Result:
        title = task.params.get("title", "")
        button = task.params.get("button", "")
        if not button:
            return Result(task.id, False, error="请指定按钮文字")
        app = self._get_app(title) if title else None
        if app:
            win = app.top_window()
            btn = win.child_window(title=button, control_type="Button")
            btn.click()
        else:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            btn = desktop.window(title=button, control_type="Button")
            btn.click()
        return Result(task.id, True, summary=f"已点击按钮: {button}")

    def _screenshot(self, task: Task) -> Result:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        img = desktop.wrapper_object().capture_as_image()
        path = os.path.expanduser(f"~/.deskflow/screenshots")
        os.makedirs(path, exist_ok=True)
        filepath = os.path.join(path, f"screenshot_{task.id}.png")
        img.save(filepath)
        return Result(task.id, True, summary=f"截图已保存: {filepath}", data=filepath)

    def _minimize_windows(self, task: Task) -> Result:
        title = task.params.get("title", "")
        if title:
            app = self._get_app(title)
            win = app.top_window()
            win.minimize()
            return Result(task.id, True, summary=f"已最小化: {title}")
        # 最小化所有窗口
        import pywinauto
        pywinauto.keyboard.send_keys('{VK_LWIN down}m{VK_LWIN up}')
        return Result(task.id, True, summary="已最小化所有窗口")
