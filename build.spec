# -*- mode: python ; coding: utf-8 -*-
"""DeskFlow PyInstaller 构建配置 — One-Dir 桌面版"""
import os
from os.path import join

BASE = os.getcwd()
block_cipher = None

# ── 资源数据：递归收集 UI 目录 ──
datas = []
for root, dirs, files in os.walk(join(BASE, 'ui')):
    dest = os.path.relpath(root, BASE)
    for f in files:
        datas.append((join(root, f), dest))

a = Analysis(
    ['run.py'],
    pathex=[BASE],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'flask', 'jinja2', 'werkzeug', 'markupsafe', 'click',
        'itsdangerous', 'blinker',
        'core.config', 'core.llm_gateway', 'core.file_ops',
        'core.shortcuts', 'core.logger', 'core.file_monitor',
        'core.task_scheduler', 'core.provider_tester',
        'agents.base_agent', 'agents.file_manager',
        'agents.document', 'agents.excel', 'agents.web_search',
        'agents.memory', 'agents.window_ops',
        'orchestrator.engine', 'orchestrator.intent_router',
        'orchestrator.workflows', 'orchestrator.scheduler',
        'autolearn.models', 'autolearn.collector',
        'autolearn.analyzer', 'autolearn.hooks',
        'memory.store', 'memory.profile', 'memory.learner',
        'apscheduler', 'pandas', 'openpyxl',
        'python_docx', 'pypdf', 'requests', 'ddgs',
        'watchdog', 'watchdog.observers', 'watchdog.events',
        'pyperclip', 'pywinauto', 'win32gui', 'webview',
        'apscheduler.triggers.cron',
        'apscheduler.triggers.interval',
        'apscheduler.schedulers.background',
        'sqlite3',
        # pywebview internal backends
        'webview.platforms',
    ],
    hookspath=[],
    hooksconfig={},
    excludes=[
        'matplotlib', 'scipy', 'sympy', 'notebook', 'jupyter',
        'ipython', 'tkinter', 'turtle', 'test', 'unittest',
        'setuptools._distutils',
    ],
)

# ── 强制全量收集大包（含所有子模块 + 数据文件 + DLL） ──
from PyInstaller.utils.hooks import collect_all, collect_submodules

print("=" * 60)
for _pkg in ['flask', 'jinja2', 'werkzeug', 'markupsafe',
             'pandas', 'openpyxl', 'apscheduler',
             'watchdog', 'pywinauto', 'webview',
             'requests', 'pypdf', 'python_docx']:
    try:
        _d, _b, _hi = collect_all(_pkg)
        a.datas += _d
        a.binaries += _b
        a.hiddenimports += [m for m in _hi if m not in a.hiddenimports]
        print(f"  ✅ collect_all({_pkg}): +{len(_hi)} modules, +{len(_d)} datas")
    except Exception as e:
        print(f"  ⚠ collect_all({_pkg}): {e}")

# 额外收集 flask 子模块（确保万无一失）
try:
    extra = collect_submodules('flask')
    a.hiddenimports += [m for m in extra if m not in a.hiddenimports]
    print(f"  ✅ collect_submodules('flask'): +{len(extra)} modules")
except Exception as e:
    print(f"  ⚠ collect_submodules('flask'): {e}")
print("=" * 60)

# ── 打包 One-Dir ──
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
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
