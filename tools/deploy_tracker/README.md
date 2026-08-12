# deploy_tracker — 干员操作记录追踪

读取模拟器内存中的 `BattleLogger`，实时显示**部署/技能/撤退**操作（时间、
干员名、朝向、格子坐标），代理作战（PRTS）直接显示完整代理序列。

- `ak_live_log.py` — 控制台实时监控，自动增量导出 JSON
  （`python -m tools.deploy_tracker.ak_live_log [--out xxx.json]`）。
- `web_server.py` — 浏览器时间轴（`--port 8793`）。
- `ak_deploy_ui.py` — tkinter 桌面版（全自动定位 + 表格 + 导出）。
- `ak_deploy_reader.py` / `char_names.py` — 读取器与干员中文名映射。

数据来源：`BattleLogger.m_logs`（+0x20）与 `ReplayController.m_journal`；
TCP 通道端口 **27273**（与敌人 27271 / RNG 27272 隔离）。
