# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Arknights\\Arknights_timer\\backend\\run.py'],
    pathex=['D:\\Arknights\\Arknights_timer'],
    binaries=[],
    datas=[('D:\\Arknights\\Arknights_timer\\aaa.ico', '.'), ('D:\\Arknights\\Arknights_timer\\tools', 'tools'), ('D:\\Arknights\\Arknights_timer\\backend\\data', 'backend/data'), ('D:\\Arknights\\Arknights_timer\\backend\\app\\static', 'backend/app/static')],
    hiddenimports=['tools.timer.ak_memory_reader', 'pymem', 'PySide6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ArknightsTimeline',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\\Arknights\\Arknights_timer\\aaa.ico'],
)
