# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui/templates', 'ui/templates'),
        ('ui/static', 'ui/static'),
        ('ui/icons', 'ui/icons'),
    ],
    hiddenimports=[
        'flask', 'jinja2', 'werkzeug',
        'pypdf', 'docx', 'pandas', 'openpyxl',
        'requests', 'ddgs', 'watchdog',
    ],
    hookspath=[],
    hooksconfig={},
)

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
    upx=True,
    icon=None,
)
