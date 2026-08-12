# speed_scanner — 倍速/暂停状态寻址

扫描游戏倍速等级（`m_speedLevel`）与 `Time.timeScale` 地址：
Phase 1 交替 1x/2x 筛选，Phase 2 手动切换 0/1/2 筛选，剩余候选列表
手动确认。

- `ak_speed_ui.py` — tkinter 界面。
- `ak_speed_reader.py` — 读取器。
