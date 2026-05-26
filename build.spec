# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# 项目根目录
base_dir = Path(__file__).parent

a = Analysis(
    ['main.py'],
    pathex=[str(base_dir)],
    binaries=[],
    datas=[
        (str(base_dir / 'ui' / 'templates'), 'ui/templates'),
        (str(base_dir / 'ui' / 'static'), 'ui/static'),
        (str(base_dir / 'ui' / 'icons'), 'ui/icons'),
    ],
    hiddenimports=[
        'flask',
        'jinja2',
        'werkzeug',
        'pypdf',
        'docx',
        'pandas',
        'openpyxl',
        'requests',
        'ddgs',
        'watchdog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'sympy',
        'PIL', 'cv2', 'torch', 'tensorflow',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DeskFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # 不显示命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(base_dir / 'ui' / 'icons' / 'deskflow.ico') if (base_dir / 'ui' / 'icons' / 'deskflow.ico').exists() else None,
)
