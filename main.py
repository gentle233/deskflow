"""DeskFlow — 桌面智能助手启动入口"""
import sys
import os
import json

# 保证可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, Response
from core.llm_gateway import LLMGateway
from core.config import load_config, save_config, update_config
from core.file_ops import FileOps
from core.shortcuts import load_shortcuts, add_shortcut, delete_shortcut
from autolearn.models import init_db as init_autolearn_db, get_active_patterns, dismiss_pattern, count_events_last_24h, get_db_size_mb
from autolearn.collector import start_collectors
from autolearn.analyzer import run_analysis, purge_old_data
from orchestrator.engine import Orchestrator
from agents.file_manager import FileManagerAgent
from agents.document import DocumentAgent
from agents.excel import ExcelAgent
from agents.web_search import WebSearchAgent
from agents.memory import MemoryAgent
from memory.store import init_db

# 应用根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
    template_folder=os.path.join(BASE_DIR, "ui", "templates"),
    static_folder=os.path.join(BASE_DIR, "ui", "static"),
    static_url_path="/static"
)

# 全局实例
orchestrator: Orchestrator = None

@app.route("/")
def index():
    """主页面"""
    config = load_config()
    if config.get("first_run"):
        return render_template("setup.html")
    return render_template("chat.html")

@app.route("/api/setup", methods=["POST"])
def setup():
    """首次配置"""
    data = request.json
    update_config("provider", data.get("provider", "deepseek"))
    update_config("api_key", data.get("api_key", ""))
    update_config("first_run", False)
    _init_orchestrator()
    return jsonify({"status": "ok"})

@app.route("/api/chat", methods=["POST"])
def chat():
    """聊天接口"""
    message = request.form.get("message", "")
    file = request.files.get("file")

    # 处理上传的文件
    if file:
        upload_dir = os.path.expanduser("~/.deskflow/uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)
        file.save(filepath)
        content = FileOps.read(filepath)
        message = f"{message}\n\n[文件内容: {file.filename}]\n{content[:3000]}"

    if not orchestrator:
        return jsonify({"reply": "⚠️ 请先完成初始配置"})

    try:
        reply = orchestrator.process(message)
    except Exception as e:
        reply = f"⚠️ 处理出错: {str(e)}"
    return jsonify({"reply": reply})



@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """流式聊天接口 — SSE"""
    message = request.form.get("message", "")
    file = request.files.get("file")

    if file:
        upload_dir = os.path.expanduser("~/.deskflow/uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)
        file.save(filepath)
        content = FileOps.read(filepath)
        message = f"{message}\n\n[文件内容: {file.filename}]\n{content[:3000]}"

    if not orchestrator:
        return jsonify({"reply": "请先完成初始配置"})

    def generate():
        try:
            reply = orchestrator.process(message)
            CHUNK = 3
            for i in range(0, len(reply), CHUNK):
                chunk = reply[i:i + CHUNK]
                data = json.dumps({"token": chunk})
                yield "data: " + data + "\n\n"
            data = json.dumps({"done": True})
            yield "data: " + data + "\n\n"
        except Exception as e:
            data = json.dumps({"error": str(e)})
            yield "data: " + data + "\n\n"

    return Response(generate(), mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/config", methods=["GET"])
def get_config():
    """查看当前配置（隐藏 API Key 全文）"""
    config = load_config()
    safe = dict(config)
    key = safe.get("api_key", "")
    if key:
        safe["api_key"] = key[:8] + "..." + key[-4:]
    return jsonify(safe)

@app.route("/api/provider/check", methods=["GET"])
def check_provider():
    """检查 API 连接状态"""
    config = load_config()
    if not config.get("api_key"):
        return jsonify({"status": "error", "message": "未配置 API Key"})
    try:
        llm = LLMGateway(config.get("provider"), config.get("api_key"))
        llm.chat([{"role": "user", "content": "说一个字"}])
        return jsonify({"status": "ok", "message": "连接正常"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# 在聊天页的导航栏加一个配置按钮

@app.route("/api/config/search", methods=["POST"])
def save_search_config():
    """保存搜索设置"""
    data = request.json
    if not data:
        return jsonify({"status": "error", "error": "无数据"})
    provider = data.get("search_provider", "ddgs")
    if provider not in ("ddgs", "bing"):
        return jsonify({"status": "error", "error": "不支持的搜索提供商"})
    update_config("search_provider", provider)
    if provider == "bing" and data.get("bing_api_key"):
        update_config("bing_api_key", data["bing_api_key"])
    return jsonify({"status": "ok"})

@app.route("/api/shortcuts", methods=["GET"])
def get_shortcuts():
    """获取所有快捷指令"""
    return jsonify(load_shortcuts())

@app.route("/api/shortcuts", methods=["POST"])
def create_shortcut():
    """添加快捷指令"""
    data = request.json
    if not data or not data.get("trigger") or not data.get("command"):
        return jsonify({"status": "error", "error": "trigger 和 command 不能为空"}), 400
    result = add_shortcut(data["trigger"], data["command"], data.get("desc", ""))
    return jsonify(result)

@app.route("/api/shortcuts", methods=["DELETE"])
def remove_shortcut():
    """删除快捷指令"""
    data = request.json or {}
    trigger = data.get("trigger", "")
    if not trigger:
        return jsonify({"status": "error", "error": "trigger 不能为空"}), 400
    return jsonify(delete_shortcut(trigger))

@app.route("/api/autolearn/suggestions")
def autolearn_suggestions():
    """获取学习建议"""
    patterns = get_active_patterns(limit=3, min_confidence=0.5)
    return jsonify([{
        'id': p['id'],
        'type': p['pattern_type'],
        'key': p['pattern_key'],
        'value': p['pattern_value'],
        'title': _autolearn_title(p),
        'confidence': p['confidence']
    } for p in patterns])

@app.route("/api/autolearn/dismiss/<int:pattern_id>", methods=["POST"])
def autolearn_dismiss(pattern_id):
    """忽略建议"""
    dismiss_pattern(pattern_id)
    return jsonify({"status": "ok"})

@app.route("/api/autolearn/stats")
def autolearn_stats():
    """学习统计"""
    return jsonify({
        'events_today': count_events_last_24h(),
        'active_patterns': len(get_active_patterns(limit=100, min_confidence=0)),
        'storage_mb': get_db_size_mb()
    })

def _autolearn_title(pattern: dict) -> str:
    """为学习模式生成友好标题"""
    pt = pattern['pattern_type']
    val = pattern['pattern_value'] or ''
    if pt == 'frequent_folder':
        return f'📂 快速打开: {os.path.basename(val) or val}'
    elif pt == 'weekly_report':
        return f'📝 写周报时间'
    elif pt == 'common_phrase':
        return f'💬 常用短语: "{val}"'
    elif pt == 'repeated_action':
        return f'🔄 重复操作: {val[:20]}'
    elif pt == 'user_preference':
        return f'💡 {val[:30]}'
    return f'🔔 {val[:30]}'

@app.route("/settings")
def settings():
    """配置页面"""
    return render_template("settings.html")

def _init_orchestrator():
    """初始化总控和 Agent"""
    global orchestrator
    config = load_config()
    llm = LLMGateway(config.get("provider", "deepseek"), config.get("api_key", ""))
    orchestrator = Orchestrator(llm)
    # 注册 Agent
    orchestrator.dispatcher.register(FileManagerAgent())
    orchestrator.dispatcher.register(DocumentAgent())
    orchestrator.dispatcher.register(ExcelAgent())
    orchestrator.dispatcher.register(WebSearchAgent())
    orchestrator.dispatcher.register(MemoryAgent())

def main():
    init_db()
    init_autolearn_db()
    config = load_config()
    if not config.get("first_run"):
        _init_orchestrator()
        # 启动自动学习采集器
        try:
            start_collectors()
            _start_autolearn_scheduler()
        except Exception as e:
            print(f"[autolearn] 采集器启动失败: {e}")
    # 启动 Flask
    app.run(host="127.0.0.1", port=7788, debug=False)


def _start_autolearn_scheduler():
    """启动自动学习定时任务"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        # 每小时分析一次
        scheduler.add_job(run_analysis, 'interval', hours=1, id='autolearn_analysis')
        # 每天凌晨清理一次过期数据
        scheduler.add_job(purge_old_data, 'cron', hour=3, id='autolearn_purge')
        scheduler.start()
        print("[autolearn] 定时任务已启动（每小时分析 / 每天3点清理）")
    except ImportError:
        print("[autolearn] apscheduler 未安装，跳过定时分析")
    except Exception as e:
        print(f"[autolearn] 调度器启动失败: {e}")

if __name__ == "__main__":
    main()
