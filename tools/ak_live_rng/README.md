# ak_live_rng — 实时随机数追踪

经静态指针链定位战斗随机引擎，实时还原每次随机数调用并预测后续序列
（关键随机 `randomImp` 与表现随机 `randomTrivial` 双引擎）。

- `ak_live_rng.py` — 控制台版（adb 后端，免管理员）。
- `ak_rng_ui.py` — tkinter 图形界面（序列条图/当前值/游标）。
- `rng_service.py` — 可复用服务层（`RngService`，可注入自定义 reader）。
- `memscan.py` / `tracker.py` / `rng_engines.py` — 定位/轮询/引擎复刻。
- `test_ak_live_rng.py` — 离线自测（53 项，无需模拟器）。

来源边界：本地 dump 声明 `IBattleRandom`、`BattleRandomWrapper.m_random`、
`LegacyRandom` 双游标与数组；方法正文未恢复。历史项目说明报告过 Knuth
游标间距31，而 `.NET` 兼容初始化为21；本工具从捕获的完整状态推进，
不能把兼容构造函数当作已证明的游戏种子初始化。每个部署的实际类/版本、
imp/trivial调用来源、原始状态与独立输出仍需核实；UI摘要不是完整状态快照。
TCP 通道端口 **27272**；本次修复与离线测试没有访问设备。
