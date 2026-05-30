# -*- mode: python ; coding: utf-8 -*-
"""DeskFlow PyInstaller 构建配置 — 桌面窗口版"""

import os
from os.path import join

# PyInstaller spec 中不能用 __file__，用 os.getcwd() 代替
BASE = os.getcwd()

# ── 资源数据：UI 模板 / 静态文件 / 图标 ──
ui_datas = [
    (join(BASE, 'ui', 'templates'), 'ui/templates'),
    (join(BASE, 'ui', 'static'), 'ui/static'),
    (join(BASE, 'ui', 'icons'), 'ui/icons'),
]

block_cipher = None

# ── 分析入口 ──
a = Analysis(
    ['run.py'],
    pathex=[BASE],
    binaries=[],
    datas=ui_datas,
    hiddenimports=[
        # Flask 生态
        'flask', 'jinja2', 'werkzeug', 'markupsafe', 'click',
        'itsdangerous', 'blinker',

        # 项目内部 — 核心
        'core.config', 'core.llm_gateway', 'core.file_ops',
        'core.shortcuts', 'core.logger', 'core.file_monitor',
        'core.task_scheduler', 'core.provider_tester',
        # 项目内部 — Agent
        'agents.base_agent', 'agents.file_manager',
        'agents.document', 'agents.excel', 'agents.web_search',
        'agents.memory', 'agents.window_ops',
        # 项目内部 — 编排
        'orchestrator.engine', 'orchestrator.intent_router',
        'orchestrator.workflows', 'orchestrator.scheduler',
        # 项目内部 — 自动学习
        'autolearn.models', 'autolearn.collector',
        'autolearn.analyzer', 'autolearn.hooks',
        # 项目内部 — 记忆
        'memory.store', 'memory.profile', 'memory.learner',

        # 第三方依赖（显式列出，PyInstaller 扫描不到动态 import 的）
        'apscheduler.triggers.cron',
        'apscheduler.triggers.interval',
        'apscheduler.schedulers.background',
        'pandas',
        'openpyxl',
        'python_docx',
        'pypdf',
        'requests',
        'ddgs',
        'watchdog.observers',
        'watchdog.events',
        'pyperclip',
        'pywinauto',
        'win32gui',
        'webview',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    excludes=[
        'matplotlib', 'scipy', 'sympy', 'notebook', 'jupyter',
        'ipython', 'tkinter', 'turtle', 'test', 'unittest',
        'setuptools._distutils',
    ],
)

# ── 确保大包完整收集 ──
from PyInstaller.utils.hooks import collect_all

for _pkg in ['flask', 'jinja2', 'werkzeug', 'markupsafe',
             'pandas', 'openpyxl', 'apscheduler',
             'watchdog', 'pywinauto']:
    _d, _b, _hi = collect_all(_pkg)
    a.datas += _d
    a.binaries += _b
    a.hiddenimports += list(set(_hi) - set(a.hiddenimports))

# ── 打包：One-Dir 模式（exe + 依赖文件放在同一目录） ──
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='DeskFlow',
    debug=False,
    console=False,
    disable_windowed_traceback=False,
    upx=False,
    icon=join(BASE, 'ui', 'icons', 'deskflow.ico'),
    strip=False,
    uac_admin=False,
    codepage='utf-8',
)

# COLLECT 把 dll/pyd/zip/资源全部放在 exe 同目录，启动即用不解压
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DeskFlow',
)
