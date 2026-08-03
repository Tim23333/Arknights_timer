# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['G:\\Arknights\\backend\\run.py'],
    pathex=['G:\\Arknights'],
    binaries=[],
    datas=[('G:\\Arknights\\aaa.ico', '.'), ('G:\\Arknights\\backend\\build\\TEST_BUILD', '.'), ('G:\\Arknights\\tools', 'tools'), ('G:\\Arknights\\backend\\app\\static', 'backend/app/static'), ('G:\\Arknights\\data\\tables\\enemy_handbook_table493349.bin', 'data/tables'), ('G:\\Arknights\\data\\tables\\enemy_names.json', 'data/tables'), ('G:\\Arknights\\data\\tables\\character_table9fc534.bin', 'data/tables'), ('G:\\Arknights\\ark_parser\\char_names.json', 'ark_parser'), ('G:\\Arknights\\backend\\dist\\AKTimerTool.exe', 'tools')],
    hiddenimports=['tools.timer.ak_memory_reader', 'tools.deploy_tracker.ak_deploy_reader', 'tools.enemy_health.enemy_reader', 'tools.enemy_health.memcore', 'tools.enemy_health.enemy_db', 'tools.enemy_health.game_structs', 'numpy', 'pymem', 'PySide6', 'websockets'],
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
    name='ArknightsTimeline_Test',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['G:\\Arknights\\aaa.ico'],
)
