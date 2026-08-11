#!/usr/bin/env python3
"""
一键打包 Arknights 游戏数据显示工具为 Windows EXE。

特性：
1) 打包主程序：backend/run.py → ArknightsTimeline_<版本>.exe
   （游戏时间/帧显示 + 敌人实时监控, tools/enemy_health）
2) 打包寻址工具：tools/timer/ak_timer_ui.py → AKTimerTool.exe（内嵌进主程序）
3) 默认连打测试版：同源 + 独立诊断日志窗口 → ArknightsTimeline_<版本>_Test.exe
4) 自动包含 tools/ 目录（含 enemy_health/bin/memsrv 设备侧内存服务）
5) 自动构建 memsrv（memsrv.c 比 bin/memsrv 新时用 ziglang 交叉编译）
6) 自动包含敌人名称数据库 data/tables/enemy_handbook_table*.bin
7) 默认图标：仓库根目录下的 aaa.ico（可命令行覆盖）

用法：
  python build_exe.py                # 默认连打正式版 + 测试版 (带诊断日志窗口)
  python build_exe.py --icon "<仓库根目录>\\aaa.ico" --name ArknightsTimeline
  python build_exe.py --onedir
  python build_exe.py --skip-timer   # 只打包主程序 (不内嵌寻址工具)
  python build_exe.py --skip-test    # 只打正式版, 跳过测试版

说明：测试版 = 同源代码 + 独立诊断日志窗口 + TEST_BUILD 标记,
输出 <名称>_Test.exe（默认 ArknightsTimeline_v<版本>_Test.exe），用于现场排查。
发布前只需修改 backend/app/version.py 中的 VERSION 变量；默认文件名、Windows
文件属性、程序主页面标题和测试日志顶部都会自动使用该版本号。
(如换机扫描失败)。desktop_app 检测标记或环境变量 AK_TEST_BUILD=1
即开启线程安全日志落盘、环境诊断和一键日志打包；测试版仍为 windowed，
不会再弹出 CMD 控制台。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.version import VERSION, VERSION_LABEL, windows_version_tuple


def _ensure_memsrv(tools_dir: Path) -> None:
    """memsrv.c 更新或 bin/memsrv 缺失时, 用 ziglang 交叉编译 aarch64 静态二进制。
    构建失败不阻断打包 (TCP 通道会自动回退 sh+dd 模式, 只是慢)。"""
    src = tools_dir / "enemy_health" / "memsrv.c"
    out = tools_dir / "enemy_health" / "bin" / "memsrv"
    if not src.is_file():
        print("[WARN] 未找到 memsrv.c, 跳过 memsrv 构建")
        return
    if out.is_file() and out.stat().st_mtime >= src.stat().st_mtime:
        print(f"[INFO] memsrv 已是最新: {out}")
        return
    print("[INFO] 构建 memsrv (zig cc -> aarch64-linux-musl 静态)...")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "ziglang", "cc", "-target", "aarch64-linux-musl",
           "-static", "-O2", "-o", str(out), str(src)]
    proc = subprocess.run(cmd)
    if proc.returncode != 0 or not out.is_file():
        print("[WARN] memsrv 构建失败 (pip install ziglang 可修复); "
              "打包继续, 运行时将回退 sh+dd 慢速模式")
    else:
        print(f"[OK] memsrv 构建完成: {out} ({out.stat().st_size} bytes)")


def _add_data_arg(src: Path, dst: str) -> str:
    # PyInstaller 的 --add-data 在 Windows 使用 ';' 分隔，在 Linux/macOS 使用 ':'
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dst}"


def _frontend_version(repo_root: Path) -> str:
    """前端版本的唯一配置入口是 frontend/package.json 的 version 字段
    (页面标题与页头展示的版本号也由它注入)。"""
    try:
        return json.loads((repo_root / "frontend" / "package.json")
                          .read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, ValueError):
        return "未知"


def _ensure_frontend_static(repo_root: Path) -> None:
    """打包前构建前端 (frontend/ -> backend/app/static, 内嵌为排轴工具页面)。
    未装 node/npm 或构建失败不阻断打包, 沿用仓库里已提交的旧构建产物。"""
    frontend_dir = repo_root / "frontend"
    static_dir = repo_root / "backend" / "app" / "static"
    if not (frontend_dir / "package.json").is_file():
        print("[WARN] 未找到 frontend/package.json, 跳过前端构建, 沿用现有 static")
        return
    print(f"[INFO] 前端版本: v{_frontend_version(repo_root)} (frontend/package.json)")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        print("[WARN] 未找到 npm, 跳过前端构建, 沿用现有 static "
              "(装 Node.js 后可在 frontend/ 手动 npm run build)")
        return
    if not (frontend_dir / "node_modules").is_dir():
        print("[INFO] 安装前端依赖 (npm install)...")
        if subprocess.run([npm, "install"], cwd=frontend_dir).returncode != 0:
            print("[WARN] npm install 失败, 沿用现有 static")
            return
    print("[INFO] 构建前端 (npm run build -> backend/app/static)...")
    proc = subprocess.run([npm, "run", "build"], cwd=frontend_dir)
    if proc.returncode != 0 or not (static_dir / "index.html").is_file():
        print("[WARN] 前端构建失败, 打包继续并沿用现有 static")
    else:
        print(f"[OK] 前端构建完成: {static_dir}")


def _snapshot_frontend_static(backend_dir: Path) -> Path:
    """把 backend/app/static 复制为打包快照 (build/_static_snapshot)。
    PyInstaller Analysis 扫描与 PKG 写盘之间若 static 被 vite build 改写
    (assets 文件名带 hash, 旧文件被清空), 会以 FileNotFoundError 中断;
    打包统一引用快照目录后正式版/测试版看到的文件集冻结一致。"""
    src = backend_dir / "app" / "static"
    snapshot = backend_dir / "build" / "_static_snapshot"
    if not (src / "index.html").is_file():
        return src  # 没有可打包的前端, 原样返回 (后续 is_dir 判断会跳过)
    shutil.rmtree(snapshot, ignore_errors=True)
    try:
        shutil.copytree(src, snapshot)
        print(f"[INFO] 前端 static 快照: {snapshot}")
        return snapshot
    except OSError as exc:
        print(f"[WARN] static 快照失败 ({exc}), 改为直接引用源目录")
        return src


def _write_windows_version_file(backend_dir: Path, executable_name: str) -> Path:
    """生成 PyInstaller 使用的 Windows FileVersion/ProductVersion 资源。"""
    numeric = windows_version_tuple()
    numeric_text = ".".join(str(part) for part in numeric)
    output = backend_dir / "build" / "version_info" / f"{executable_name}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    strings = {
        "CompanyName": "Tim23333",
        "FileDescription": f"ArknightsTimeline {VERSION_LABEL}",
        "FileVersion": numeric_text,
        "InternalName": executable_name,
        "OriginalFilename": f"{executable_name}.exe",
        "ProductName": "ArknightsTimeline",
        "ProductVersion": VERSION,
    }
    string_rows = ",\n".join(
        f"StringStruct({key!r}, {value!r})" for key, value in strings.items())
    output.write_text(
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers={numeric!r}, prodvers={numeric!r},\n"
        "    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),\n"
        "  kids=[\n"
        "    StringFileInfo([StringTable('040904B0', [\n"
        f"      {string_rows}\n"
        "    ])]),\n"
        "    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n",
        encoding="utf-8",
    )
    return output


def _build_main_app(backend_dir: Path, repo_root: Path, icon_path: Path, args,
                    static_dir: Path | None = None) -> int:
    """打包带版本号的主程序（内嵌寻址工具）。
    static_dir 传快照目录 (build/_static_snapshot)，避免打包中途前端重新构建
    改写 static/assets 导致 Analysis 扫到的文件在 PKG 阶段消失。"""
    entry = backend_dir / "run.py"
    tools_dir = repo_root / "tools"
    data_dir = backend_dir / "data"
    if static_dir is None:
        static_dir = backend_dir / "app" / "static"
    tables_dir = repo_root / "data" / "tables"
    timer_exe = backend_dir / "dist" / "AKTimerTool.exe"

    if not entry.is_file():
        print(f"[ERROR] 未找到入口脚本: {entry}")
        return 1

    embed_timer = timer_exe.is_file()
    if not embed_timer:
        print("[WARN] 未找到寻址工具, 主程序将不包含内嵌 AKTimerTool.exe")

    version_file = _write_windows_version_file(backend_dir, args.name)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        args.name,
        "--icon",
        str(icon_path),
        "--version-file",
        str(version_file),
        "--paths",
        str(repo_root),
        "--distpath",
        str(backend_dir / "dist"),
        "--workpath",
        str(backend_dir / "build" / "main"),
        "--specpath",
        str(backend_dir),
    ]

    if args.onedir:
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    if args.console:
        cmd.append("--console")
    else:
        cmd.append("--windowed")

    # 打包附加数据
    if icon_path.is_file():
        cmd.extend(["--add-data", _add_data_arg(icon_path, ".")])
    if getattr(args, "test", False):
        # 测试版标记文件: desktop_app 检测后开启独立诊断日志窗口与落盘
        marker = backend_dir / "build" / "TEST_BUILD"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("test build\n", encoding="utf-8")
        cmd.extend(["--add-data", _add_data_arg(marker, ".")])
    cmd.extend(["--add-data", _add_data_arg(tools_dir, "tools")])
    if data_dir.is_dir():
        cmd.extend(["--add-data", _add_data_arg(data_dir, "backend/data")])
    if static_dir.is_dir():
        cmd.extend(["--add-data", _add_data_arg(static_dir, "backend/app/static")])
    # 敌人名称数据库 (tools/enemy_health 运行时按 data/tables 相对路径查找)
    if tables_dir.is_dir():
        for f in tables_dir.glob("enemy_handbook_table*.bin"):
            cmd.extend(["--add-data", _add_data_arg(f, "data/tables")])
        for f in tables_dir.glob("enemy_names*.json"):
            cmd.extend(["--add-data", _add_data_arg(f, "data/tables")])
        # 动作生效帧数据 (ark_parser/extract_effect_frames.py 产物)
        for f in tables_dir.glob("effect_frames.json"):
            cmd.extend(["--add-data", _add_data_arg(f, "data/tables")])
        # 干员名数据库 (tools/deploy_tracker/char_names 按 data/tables 相对路径重建)
        for f in tables_dir.glob("character_table*.bin"):
            cmd.extend(["--add-data", _add_data_arg(f, "data/tables")])
    # 干员名缓存 (deploy_tracker 优先读缓存, ark_parser 相对路径)
    char_names_json = repo_root / "ark_parser" / "char_names.json"
    if char_names_json.is_file():
        cmd.extend(["--add-data", _add_data_arg(char_names_json, "ark_parser")])

    # 内嵌寻址工具
    if embed_timer:
        cmd.extend(["--add-data", _add_data_arg(timer_exe, "tools")])

    # 常用隐藏导入（避免运行时漏模块）
    cmd.extend(["--hidden-import", "tools.timer.ak_memory_reader"])
    cmd.extend(["--hidden-import", "tools.deploy_tracker.ak_deploy_reader"])
    cmd.extend(["--hidden-import", "tools.enemy_health.enemy_reader"])
    cmd.extend(["--hidden-import", "tools.enemy_health.memcore"])
    cmd.extend(["--hidden-import", "tools.enemy_health.enemy_db"])
    cmd.extend(["--hidden-import", "tools.enemy_health.game_structs"])
    cmd.extend(["--hidden-import", "tools.enemy_health.stage_export"])
    cmd.extend(["--hidden-import", "numpy"])
    cmd.extend(["--hidden-import", "pymem"])
    cmd.extend(["--hidden-import", "PySide6"])
    cmd.extend(["--hidden-import", "websockets"])   # WS 推送服务 (桌面_app 内延迟导入)

    cmd.append(str(entry))

    print("[INFO] 开始打包主程序...")
    print("[INFO] 命令:\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

    proc = subprocess.run(cmd, cwd=str(backend_dir))
    if proc.returncode != 0:
        print(f"[ERROR] 主程序打包失败，退出码={proc.returncode}")
        return proc.returncode

    out = backend_dir / "dist" / (f"{args.name}.exe" if not args.onedir else args.name)
    print(f"[OK] 主程序打包完成: {out}")
    return 0


def _build_timer_tool(backend_dir: Path, repo_root: Path, icon_path: Path, args) -> int:
    """打包寻址工具 AKTimerTool.exe"""
    timer_dir = repo_root / "tools" / "timer"
    entry = timer_dir / "ak_timer_ui.py"

    if not entry.is_file():
        print(f"[ERROR] 未找到寻址工具脚本: {entry}")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "AKTimerTool",
        "--icon",
        str(icon_path),
        "--paths",
        str(timer_dir),  # 添加 timer 目录到路径，以便找到 ak_memory_reader
        "--distpath",
        str(backend_dir / "dist"),
        "--workpath",
        str(backend_dir / "build" / "timer"),
        "--specpath",
        str(backend_dir),
        "--onefile",
        "--windowed",
    ]

    # 打包附加数据
    if icon_path.is_file():
        cmd.extend(["--add-data", _add_data_arg(icon_path, ".")])

    # 隐藏导入
    cmd.extend(["--hidden-import", "ak_memory_reader"])
    cmd.extend(["--hidden-import", "process_scan"])
    cmd.extend(["--hidden-import", "pymem"])
    cmd.extend(["--hidden-import", "numpy"])
    cmd.extend(["--hidden-import", "psutil"])

    cmd.append(str(entry))

    print("[INFO] 开始打包寻址工具...")
    print("[INFO] 命令:\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

    proc = subprocess.run(cmd, cwd=str(backend_dir))
    if proc.returncode != 0:
        print(f"[ERROR] 寻址工具打包失败，退出码={proc.returncode}")
        return proc.returncode

    out = backend_dir / "dist" / "AKTimerTool.exe"
    print(f"[OK] 寻址工具打包完成: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build backend desktop EXE with PyInstaller.")
    parser.add_argument(
        "--name",
        help=f"输出程序名（默认 ArknightsTimeline_{VERSION_LABEL}）")
    parser.add_argument(
        "--icon",
        default=str(Path(__file__).resolve().parent.parent / "aaa.ico"),
        help="ico 图标路径（默认 <仓库根>/aaa.ico）",
    )
    parser.add_argument("--onedir", action="store_true", help="使用 onedir 模式（默认 onefile）")
    parser.add_argument("--no-clean", action="store_true", help="不清理 build/dist 临时目录")
    parser.add_argument("--console", action="store_true", help="显示控制台窗口（默认无控制台）")
    parser.add_argument("--skip-timer", action="store_true", help="跳过寻址工具打包（主程序将不含内嵌寻址工具）")
    parser.add_argument("--skip-frontend", action="store_true",
                        help="跳过前端构建（沿用 backend/app/static 现有产物）")
    parser.add_argument("--skip-test", action="store_true", help="跳过测试版打包（默认与正式版一起产出）")
    parser.add_argument("--test", action="store_true",
                        help="(已废弃, 默认即会同时打包测试版) 仅保留兼容, 效果等同默认行为")
    args = parser.parse_args()
    if not args.name:
        args.name = f"ArknightsTimeline_{VERSION_LABEL}"

    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parent
    workspace_root = repo_root.parent

    print(f"[INFO] 当前应用版本: {VERSION_LABEL}（修改 backend/app/version.py）")

    icon_path = Path(args.icon).expanduser().resolve()
    if not icon_path.is_file():
        print(f"[ERROR] 未找到 ico 图标: {icon_path}")
        return 1

    tools_dir = repo_root / "tools"
    if not tools_dir.is_dir():
        print(f"[ERROR] 未找到 tools 目录: {tools_dir}")
        return 1

    # 可选清理旧目录 (失败多因 exe 正在运行/被占用, 直接报错而不是静默带病打包)
    if not args.no_clean:
        for d in (backend_dir / "build", backend_dir / "dist"):
            if not d.exists():
                continue
            try:
                shutil.rmtree(d)
            except OSError as exc:
                print(f"[ERROR] 无法清理 {d}: {exc}")
                print("        请关闭正在运行的已打包 exe 及占用该目录的程序后重试")
                return 1

    # 步骤 0: 构建 memsrv 设备侧内存服务 (源码更新时)
    print("\n" + "=" * 60)
    print("[步骤 0] 检查 memsrv 设备侧内存服务...")
    print("=" * 60)
    _ensure_memsrv(tools_dir)

    # 步骤 0.5: 构建前端 (排轴工具页面, 打包进 backend/app/static)
    if args.skip_frontend:
        print("\n[INFO] --skip-frontend: 跳过前端构建, 沿用现有 static")
    else:
        print("\n" + "=" * 60)
        print("[步骤 0.5] 构建前端（排轴工具页面）...")
        print("=" * 60)
        _ensure_frontend_static(repo_root)
    static_snapshot = _snapshot_frontend_static(backend_dir)

    # 步骤 1: 先打包寻址工具为临时 exe
    timer_exe = backend_dir / "dist" / "AKTimerTool.exe"
    if args.skip_timer:
        print("\n[INFO] --skip-timer: 跳过寻址工具打包")
        # 主程序内嵌寻址工具; 跳过时拿旧的 (若有) 顶用, 没有则仅警告
        if not timer_exe.is_file():
            print("[WARN] dist/AKTimerTool.exe 不存在, 主程序将无法内嵌寻址工具")
    else:
        print("\n" + "=" * 60)
        print("[步骤 1/3] 打包寻址工具...")
        print("=" * 60)
        ret = _build_timer_tool(backend_dir, repo_root, icon_path, args)
        if ret != 0:
            return ret

    # 步骤 2: 打包主程序，将寻址工具内嵌进去
    print("\n" + "=" * 60)
    print("[步骤 2/3] 打包主程序（内嵌寻址工具）...")
    print("=" * 60)
    ret = _build_main_app(backend_dir, repo_root, icon_path, args, static_snapshot)
    if ret != 0:
        return ret

    # 步骤 3: 测试版 (独立诊断日志窗口), 名称加 _Test 后缀, 内嵌标记
    if not args.skip_test:
        print("\n" + "=" * 60)
        print("[步骤 3/3] 打包测试版（独立诊断日志窗口）...")
        print("=" * 60)
        test_args = argparse.Namespace(**vars(args))
        test_args.test = True        # _build_main_app 据此内嵌 TEST_BUILD 标记
        test_args.console = False    # 测试版使用 GUI 日志窗口，不弹 CMD
        test_args.name = args.name if args.name.endswith("_Test") else f"{args.name}_Test"
        ret = _build_main_app(backend_dir, repo_root, icon_path, test_args, static_snapshot)
        if ret != 0:
            return ret

    # 清理临时的 AKTimerTool.exe（已内嵌到主程序中）
    if timer_exe.exists():
        timer_exe.unlink()
        print(f"[INFO] 已清理临时文件: {timer_exe.name}")

    print("\n" + "=" * 60)
    print("[OK] 打包完成！")
    print(f"[INFO] 后端版本: {VERSION_LABEL} | 前端版本: v{_frontend_version(repo_root)}")
    print(f"[INFO] 输出目录: {backend_dir / 'dist'}")
    print(f"[INFO] 文件列表:")
    dist_dir = backend_dir / "dist"
    if dist_dir.exists():
        for f in dist_dir.iterdir():
            if f.suffix == ".exe":
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  - {f.name} ({size_mb:.1f} MB)")
    print("=" * 60)
    print('[TIP] 寻址工具已内嵌到主程序中，点击"打开寻址工具"即可使用。')
    print('[TIP] 敌人监控需要 MuMu 模拟器已启动并 adb root（MuMu 默认支持）。')
    print('[TIP] 若首次运行被拦截，请在 Windows 安全提示中选择"仍要运行"。')
    print(f"[TIP] 当前工作区根目录: {workspace_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

