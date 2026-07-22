"""
启动明日方舟游戏数据显示工具（独立桌面程序，无 Web 服务）。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from desktop_app import main

if __name__ == "__main__":
    main()
