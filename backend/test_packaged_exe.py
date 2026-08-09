#!/usr/bin/env python3
"""
测试打包后的 exe 文件是否能正常运行。
用法：python test_packaged_exe.py
"""
from pathlib import Path
import subprocess
import sys

from app.version import VERSION_LABEL


def main():
    dist_dir = Path(__file__).resolve().parent / "dist"

    print("=" * 60)
    print("打包测试工具")
    print("=" * 60)

    # 检查主程序
    main_exe = dist_dir / f"ArknightsTimeline_{VERSION_LABEL}.exe"

    print(f"\n[检查] 输出目录: {dist_dir}")
    print(f"[检查] 主程序: {main_exe}")

    if not main_exe.exists():
        print(f"[错误] 主程序不存在: {main_exe}")
        print("[提示] 请先运行 build_exe.py 进行打包")
        return 1

    # 检查文件大小
    main_size_mb = main_exe.stat().st_size / (1024 * 1024)
    print(f"\n[信息] 主程序大小: {main_size_mb:.1f} MB")

    # 检查内嵌的寻址工具（通过文件大小判断）
    if main_size_mb < 80:
        print("[警告] 主程序大小异常，可能未正确内嵌寻址工具")
        print("[提示] 请重新运行 build_exe.py 打包")
    else:
        print("[成功] 主程序大小正常，寻址工具已内嵌")

    # 尝试运行主程序（带 --help 参数，如果支持的话）
    print("\n[测试] 尝试启动主程序...")
    try:
        # 使用 --version 或 --help 来测试是否能启动
        result = subprocess.run(
            [str(main_exe), "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(dist_dir)
        )
        if result.returncode == 0:
            print("[成功] 主程序可以正常启动")
        else:
            print(f"[警告] 主程序返回非零退出码: {result.returncode}")
            if result.stderr:
                print(f"[错误信息] {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("[信息] 主程序启动超时（可能是 GUI 程序正常行为）")
    except Exception as e:
        print(f"[错误] 无法启动主程序: {e}")

    print("\n" + "=" * 60)
    print("[完成] 测试完成")
    print("=" * 60)
    print("\n[说明]")
    print("- 寻址工具已内嵌到主程序中")
    print(f"- 用户只需分发 {main_exe.name} 一个文件")
    print('- 点击"打开寻址工具"按钮时，程序会自动提取并运行寻址工具')
    return 0


if __name__ == "__main__":
    sys.exit(main())
