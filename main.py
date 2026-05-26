"""DeskFlow — 桌面智能助手启动入口"""
import sys
import os
import json

# 保证可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify
from core.llm_gateway import LLMGateway
from core.config import load_config, save_config, update_config
from core.file_ops import FileOps
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
    config = load_config()
    if not config.get("first_run"):
        _init_orchestrator()
    # 启动 Flask
    app.run(host="127.0.0.1", port=7788, debug=False)

if __name__ == "__main__":
    main()
