# tools — 内存读取与打轴工具

通过模拟器内存读取明日方舟实时数据（无需改游戏）。

| 子目录 | 功能 |
|---|---|
| `timer/` | 游戏时间（float）与逻辑帧数（uint32）内存寻址 |
| `speed_scanner/` | 倍速等级 / 暂停状态寻址 |
| `enemy_health/` | 敌方实时监控（adb + 设备侧 memsrv，60Hz 快照） |
| `ak_live_rng/` | 战斗/表现双随机数引擎实时追踪与预测 |
| `deploy_tracker/` | 部署/技能/撤退操作记录（BattleLogger），支持导出 JSON |
| `character_status/` | 干员实时状态读取 |

共同依赖 MuMu 模拟器 + adb root（读 `/proc/<pid>/mem`）。入口脚本与用法见
各子目录 README 或根目录 README.md。
