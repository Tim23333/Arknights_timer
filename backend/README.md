# backend — 桌面主程序（PySide6）

游戏数据显示工具：时间/帧数、敌人实时监控、随机数追踪、操作记录，以及
内嵌寻址/排轴工具。入口 `run.py`，打包见 `README_BUILD.md`。

```bash
cd backend
python run.py            # 开发运行
python build_exe.py      # 一键打包（输出 dist/ArknightsTimeline_v<版本>.exe）
```

版本唯一入口：`app/version.py` 的 `VERSION`。
