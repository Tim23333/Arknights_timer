# timer — 游戏时间 & 逻辑帧寻址

内存扫描定位游戏时间（float32）与逻辑帧数（uint32）地址，供主程序秒级
启动。多步扫描向导逐步缩小候选，支持 MuMu/雷电/夜神/BlueStacks 等。

- `ak_timer_ui.py` — tkinter 扫描界面。
- `ak_memory_reader.py` / `process_scan.py` — 内存读取与候选扫描。
- `test_timer_processes.py` — 定位自测。

扫描原理：1 费 = 1 秒，按费用变化范围逐轮筛选候选地址。
