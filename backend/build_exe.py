#!/usr/bin/env python3
"""
一键打包 Arknights 后端桌面程序为 Windows EXE。

特性：
1) 打包主程序：backend/run.py → ArknightsTimeline.exe
2) 打包寻址工具：tools/timer/ak_timer_ui.py → AKTimerTool.exe
3) 自动包含 tools/ 目录（含内存寻址工具）
4) 自动包含 backend/data 与 backend/app/static
5) 默认图标：仓库根目录下的 aaa.ico（可命令行覆盖）

用法：
  python build_exe.py
  python build_exe.py --icon "<仓库根目录>\\aaa.ico" --name ArknightsTimeline
  python build_exe.py --onedir
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _add_data_arg(src: Path, dst: str) -> str:
    # PyInstaller 的 --add-data 在 Windows 使用 ';' 分隔，在 Linux/macOS 使用 ':'
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dst}"


def _build_main_app(backend_dir: Path, repo_root: Path, icon_path: Path, args) -> int:
    """打包主程序 ArknightsTimeline.exe（内嵌寻址工具）"""
    entry = backend_dir / "run.py"
    tools_dir = repo_root / "tools"
    data_dir = backend_dir / "data"
    static_dir = backend_dir / "app" / "static"
    timer_exe = backend_dir / "dist" / "AKTimerTool.exe"
    speed_exe = backend_dir / "dist" / "AKSpeedTool.exe"

    if not entry.is_file():
        print(f"[ERROR] 未找到入口脚本: {entry}")
        return 1

    if not timer_exe.is_file():
        print(f"[ERROR] 未找到寻址工具: {timer_exe}")
        print("[ERROR] 请先打包寻址工具")
        return 1

    if not speed_exe.is_file():
        print(f"[ERROR] 未找到倍速寻址工具: {speed_exe}")
        print("[ERROR] 请先打包倍速寻址工具")
        return 1

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
    cmd.extend(["--add-data", _add_data_arg(tools_dir, "tools")])
    if data_dir.is_dir():
        cmd.extend(["--add-data", _add_data_arg(data_dir, "backend/data")])
    if static_dir.is_dir():
        cmd.extend(["--add-data", _add_data_arg(static_dir, "backend/app/static")])

    # 内嵌寻址工具
    cmd.extend(["--add-data", _add_data_arg(timer_exe, "tools")])
    cmd.extend(["--add-data", _add_data_arg(speed_exe, "tools")])

    # 常用隐藏导入（避免运行时漏模块）
    cmd.extend(["--hidden-import", "tools.timer.ak_memory_reader"])
    cmd.extend(["--hidden-import", "tools.deploy_tracker.ak_deploy_reader"])
    cmd.extend(["--hidden-import", "tools.speed_scanner.ak_speed_reader"])
    cmd.extend(["--hidden-import", "pymem"])
    cmd.extend(["--hidden-import", "PySide6"])

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
    cmd.extend(["--hidden-import", "pymem"])
    cmd.extend(["--hidden-import", "numpy"])

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


def _build_speed_tool(backend_dir: Path, repo_root: Path, icon_path: Path, args) -> int:
    """打包倍速寻址工具 AKSpeedTool.exe"""
    speed_dir = repo_root / "tools" / "speed_scanner"
    entry = speed_dir / "ak_speed_ui.py"

    if not entry.is_file():
        print(f"[ERROR] 未找到倍速寻址工具脚本: {entry}")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "AKSpeedTool",
        "--icon",
        str(icon_path),
        "--paths",
        str(speed_dir),
        "--distpath",
        str(backend_dir / "dist"),
        "--workpath",
        str(backend_dir / "build" / "speed"),
        "--specpath",
        str(backend_dir),
        "--onefile",
        "--windowed",
    ]

    if icon_path.is_file():
        cmd.extend(["--add-data", _add_data_arg(icon_path, ".")])

    cmd.extend(["--hidden-import", "ak_speed_reader"])
    cmd.extend(["--hidden-import", "pymem"])
    cmd.extend(["--hidden-import", "numpy"])

    cmd.append(str(entry))

    print("[INFO] 开始打包倍速寻址工具...")
    print("[INFO] 命令:\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

    proc = subprocess.run(cmd, cwd=str(backend_dir))
    if proc.returncode != 0:
        print(f"[ERROR] 倍速寻址工具打包失败，退出码={proc.returncode}")
        return proc.returncode

    out = backend_dir / "dist" / "AKSpeedTool.exe"
    print(f"[OK] 倍速寻址工具打包完成: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build backend desktop EXE with PyInstaller.")
    parser.add_argument("--name", default="ArknightsTimeline", help="输出程序名（默认 ArknightsTimeline）")
    parser.add_argument(
        "--icon",
        default=str(Path(__file__).resolve().parent.parent / "aaa.ico"),
        help="ico 图标路径（默认 <仓库根>/aaa.ico）",
    )
    parser.add_argument("--onedir", action="store_true", help="使用 onedir 模式（默认 onefile）")
    parser.add_argument("--no-clean", action="store_true", help="不清理 build/dist 临时目录")
    parser.add_argument("--console", action="store_true", help="显示控制台窗口（默认无控制台）")
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parent
    workspace_root = repo_root.parent

    icon_path = Path(args.icon).expanduser().resolve()
    if not icon_path.is_file():
        print(f"[ERROR] 未找到 ico 图标: {icon_path}")
        return 1

    tools_dir = repo_root / "tools"
    if not tools_dir.is_dir():
        print(f"[ERROR] 未找到 tools 目录: {tools_dir}")
        return 1

    # 可选清理旧目录
    if not args.no_clean:
        for d in (backend_dir / "build", backend_dir / "dist"):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)

    # 步骤 1: 先打包寻址工具为临时 exe
    print("\n" + "=" * 60)
    print("[步骤 1/3] 打包寻址工具...")
    print("=" * 60)
    ret = _build_timer_tool(backend_dir, repo_root, icon_path, args)
    if ret != 0:
        return ret

    # 步骤 2: 打包倍速寻址工具
    print("\n" + "=" * 60)
    print("[步骤 2/3] 打包倍速寻址工具...")
    print("=" * 60)
    ret = _build_speed_tool(backend_dir, repo_root, icon_path, args)
    if ret != 0:
        return ret

    # 步骤 3: 打包主程序，将寻址工具内嵌进去
    print("\n" + "=" * 60)
    print("[步骤 3/3] 打包主程序（内嵌寻址工具）...")
    print("=" * 60)
    ret = _build_main_app(backend_dir, repo_root, icon_path, args)
    if ret != 0:
        return ret

    # 清理临时 exe（已内嵌到主程序中）
    for name in ("AKTimerTool.exe", "AKSpeedTool.exe"):
        tmp = backend_dir / "dist" / name
        if tmp.exists():
            tmp.unlink()
            print(f"[INFO] 已清理临时文件: {name}")

    print("\n" + "=" * 60)
    print("[OK] 打包完成！")
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
    print('[TIP] 若首次运行被拦截，请在 Windows 安全提示中选择"仍要运行"。')
    print(f"[TIP] 当前工作区根目录: {workspace_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

