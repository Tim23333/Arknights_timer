# ak_live_rng — 实时随机数追踪

经静态指针链定位战斗随机引擎，实时还原每次随机数调用并预测后续序列
（关键随机 `randomImp` 与表现随机 `randomTrivial` 双引擎）。

- `ak_live_rng.py` — 控制台版（adb 后端，免管理员）。
- `ak_rng_ui.py` — tkinter 图形界面（序列条图/当前值/游标）。
- `rng_service.py` — 可复用服务层（`RngService`，可注入自定义 reader）。
- `memscan.py` / `tracker.py` / `rng_engines.py` — 定位/轮询/引擎复刻。
- `test_ak_live_rng.py` — 离线自测（53 项，无需模拟器）。

结论：战斗 RNG = mscorlib `System.Random`（Knuth 减法门），种子随代理
保存；TCP 通道端口 **27272**。
