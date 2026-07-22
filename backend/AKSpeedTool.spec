# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['G:\\Arknights\\tools\\speed_scanner\\ak_speed_ui.py'],
    pathex=['G:\\Arknights\\tools\\speed_scanner'],
    binaries=[],
    datas=[('G:\\Arknights\\aaa.ico', '.')],
    hiddenimports=['ak_speed_reader', 'pymem', 'numpy'],
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
    name='AKSpeedTool',
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
    icon=['G:\\Arknights\\aaa.ico'],
)
