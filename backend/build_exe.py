#!/usr/bin/env python3
"""
一键打包 Arknights 后端桌面程序为 Windows EXE。

特性：
1) 打包入口：backend/run.py
2) 自动包含 tools/ 目录（含内存寻址工具）
3) 自动包含 backend/data 与 backend/app/static
4) 默认图标：仓库根目录下的 aaa.ico（可命令行覆盖）

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
    entry = backend_dir / "run.py"

    icon_path = Path(args.icon).expanduser().resolve()
    if not entry.is_file():
        print(f"[ERROR] 未找到入口脚本: {entry}")
        return 1
    if not icon_path.is_file():
        print(f"[ERROR] 未找到 ico 图标: {icon_path}")
        return 1

    tools_dir = repo_root / "tools"
    data_dir = backend_dir / "data"
    static_dir = backend_dir / "app" / "static"

    if not tools_dir.is_dir():
        print(f"[ERROR] 未找到 tools 目录: {tools_dir}")
        return 1

    # 可选清理旧目录
    if not args.no_clean:
        for d in (backend_dir / "build", backend_dir / "dist"):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)

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
        str(backend_dir / "build"),
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

    # 常用隐藏导入（避免运行时漏模块）
    cmd.extend(["--hidden-import", "tools.timer.ak_memory_reader"])
    cmd.extend(["--hidden-import", "tools.deploy_tracker.ak_deploy_reader"])
    cmd.extend(["--hidden-import", "pymem"])
    cmd.extend(["--hidden-import", "PySide6"])

    cmd.append(str(entry))

    print("[INFO] 开始打包...")
    print("[INFO] 工作目录:", backend_dir)
    print("[INFO] 命令:\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

    proc = subprocess.run(cmd, cwd=str(backend_dir))
    if proc.returncode != 0:
        print(f"[ERROR] 打包失败，退出码={proc.returncode}")
        return proc.returncode

    out = backend_dir / "dist" / (f"{args.name}.exe" if not args.onedir else args.name)
    print(f"[OK] 打包完成: {out}")
    print(f"[TIP] 若首次运行被拦截，请在 Windows 安全提示中选择“仍要运行”。")
    print(f"[TIP] 当前工作区根目录: {workspace_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

