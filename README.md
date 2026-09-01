# Arknights 明日方舟游戏数据显示工具

明日方舟游戏数据实时显示工具集：通过内存读取，实时显示**游戏时间、逻辑帧数、倍速状态、场上所有敌人的名称/血量/属性/坐标/技能CD、战斗随机数序列（已消耗+未来预测）**，并附带游戏数据解析与服务器接口逆向文档。

第一次使用请阅读：[新手使用教程](docs/新手使用教程.md)。
交流群：1091217913
## 主程序功能（backend/）

`ArknightsTimeline_v<版本>.exe`（PySide6 桌面端，单文件分发）：

- **时间/帧数卡片**：实时读取游戏内置时间（float）与逻辑帧数（uint32），经内嵌寻址工具一次性定位地址后秒级启动
- **敌人实时监控**：进关卡后点「开始扫描」定位当前 `BattleController` 并读取关卡完整固定出怪序列（通常约 20-40 秒，场上尚无敌人也可用；结果缓存），随后准实时展示所有敌人的：
  - 名称 / 编号 / 敌人 ID
  - 血量（进度条 + 数值）、攻击 / 防御 / 法抗 / 移速 / 攻速
  - 地图坐标，以及“未出场 / 场上 / 已离场”生命周期；死亡和漏怪均归为已离场
  - 技能 CD（剩余/总冷却，如浮士德「SummonBallis 11.4/15s」）
  - 战斗状态、倍速、战斗时间
  - 固定敌人从开局起按预定出场顺序显示；条件分支/召唤等动态敌人首次出现后追加
  - 当前调度片段内显示精确“距离出场”游戏秒数；死亡转换/技能召唤等不可计时项显示触发条件
  - “离场敌方不显示”默认勾选，取消后可回看已离场敌人的最后一帧数据
  - 敌我全部运行时字段固定 60Hz 读取；暂停边界使用逻辑帧前后校验，跨帧混合快照不会发布
  - GUI 只消费最新完整快照并按值变化增量重绘；状态栏显示实际 Hz、完整帧耗时、batch/读取数和 I/O 耗时
- **随机数追踪**：进关卡后点「扫描随机数」一次性定位两条随机数引擎（首次约 15-30 秒，地址缓存后秒级），随后同时展示战斗随机 `randomImp` 与表现随机 `randomTrivial`：
  - 两条序列各自显示最近消耗（序号/值/原始值）和未来预测（个数统一设置 1-500，默认 30）
  - 两条序列各自显示游标位置、累计消耗与消耗速率
- **全局操作记录**：进关卡后点「扫描操作记录」定位 BattleLogger（快速路径约 20 秒，完整堆扫描约 1-2 分钟），随后准实时展示每一次 部署/撤退/技能 操作：
  - 战斗时间、操作类型、干员名、朝向、地图格子坐标
  - 代理作战（PRTS）直接显示完整代理序列（静态）
  - 支持一键导出 JSON（与 ak_live_log 同格式）
- **内嵌寻址工具**：点击即自动提取运行，无需安装 Python
- **WebSocket 推送**：游戏数据实时推送给外部客户端
- 窗口置顶、管理员权限自动提权

## 战斗模拟器（Ark_emulator/）

数据驱动的明日方舟战斗模拟器：按 30Hz 逻辑 tick 复现**敌方/我方全部行为、
增益减益、环境机制（PRTS 调度、宝石、污染区等）**，支持选择关卡、自定义
编队、自定义关卡敌人，并实时对外输出完整战场快照。核心用途：AI 打图分析、
机制研究、数据验证。

- **关卡覆盖**：官方 3864 关全部可加载（主线/活动/hard/训练/肉鸽等）。
- **完整机制**：敌方 1651 技能零 no-op、干员 454 名全量可用、3-tick 索敌
  门控、元素损伤、推拉/位移、buff 模板引擎（可玩内容零未实现节点）。
- **AI 接口**：`AgentEnv` + `GreedyDefender`/`BeamAgent` 可直接打图。
- **实时输出**：`snapshot()` JSON 快照 + LiveServer（HTTP+SSE）。

快速开始与用法见 [Ark_emulator/README.md](Ark_emulator/README.md)。

## 敌人监控原理（tools/enemy_health/）

通过 adb 读取 MuMu 模拟器中游戏进程（IL2CPP, arm64）的内存：

```
MuMu 模拟器 (Android arm64)
  └── 明日方舟进程
       ├── Scheduler.m_managedWaveEnemies (固定波次敌人)
       └── UnitManager.enemies (全部实时敌人，含装置/技能召唤)
            └── Enemy: m_hp / <id> / Attributes.m_cachedData
```

- **定位**：主路径在设备侧扫描当前 `BattleController` 的 Il2CppClass/对象，沿
  `BattleController → UnitManager → enemies` 取得完整实时列表（Scheduler 列表作兜底），并从
  `BattleController → LevelData.waves` 解析开局即存在的固定 SPAWN 顺序，因此不再
  依赖场上已有敌人。旧的 `enemy_` 字符串 + HP 特征全堆扫描保留为版本漂移兜底；
  地址链缓存到 `enemy_cache.pkl`，有效时可直接复用
- **轮询**：设备侧常驻内存服务 `memsrv v4`（aarch64 静态二进制，`nc -L` +
  `adb forward` TCP 长连接），打开 `/proc/<pid>/mem` 一次后按 batch 批量 pread。
  敌我容器、实体、属性、状态、技能、Buff、伤害统计和战斗时钟全部逐采样帧读取；
  稳定指针链会合并为同一批，指针改变则当帧补读。v4 是唯一内存读取协议；
  二进制缺失、握手不符或通道异常会直接报错，不再切换到旧协议或慢速 ADB
- **单一展示层**：`tools/enemy_health` 只负责定位、读取与数据模型；敌人表格、
  列设置和详情窗口统一由 `backend` 主程序维护

## 内存寻址使用说明（时间/帧数）

### 基本原理

扫描工具通过内存中的**游戏时间**（float）来定位地址。明日方舟中 **1 费 = 1 秒**，因此费用变化可以精确对应游戏时间。

### 扫描步骤

1. 进入**普通作战0-1**（非演习作战，演习作战有概率无法扫描到准确地址）
2. 等费用涨到 **11 费半左右**暂停游戏，在寻址工具中输入：
   - Min Value: `1`
   - Max Value: `2`
   - 点击扫描
3. 继续游戏，等费用涨到 **12 费半左右**暂停，输入：
   - Min Value: `2`
   - Max Value: `3`
   - 点击扫描（筛选上一轮的候选）
4. 以此类推，每过 1 费暂停一次，范围向后推移 1 秒
5. 重复直到候选地址只剩 **1 个**，即为游戏时间的内存地址

### 扫描示例

| 费用 | Min | Max | 说明 |
|------|-----|-----|------|
| 11.5 | 1 | 2 | 第一轮，全内存扫描 |
| 12.5 | 2 | 3 | 第二轮，筛选候选 |
| 13.5 | 3 | 4 | 第三轮 |
| 14.5 | 4 | 5 | 第四轮 |
| ... | ... | ... | 直到只剩 1 个地址 |

### 倍速/暂停扫描(已废弃)

找到游戏时间地址后，可使用倍速扫描工具（`tools/speed_scanner/`）：

1. **Phase 1**：保持 1 倍速，交替点击「扫描 1 倍速」和「扫描 2 倍速」直到剩 1 个
2. **Phase 2**：点击「扫描 0/1/2」按钮，根据当前游戏状态选择：
   - 游戏暂停 → 点「扫描 0」
   - 1 倍速运行 → 点「扫描 1」
   - 2 倍速运行 → 点「扫描 2」
3. 剩余 ≤10 个时会弹出候选列表，可切换游戏状态观察值变化后手动选择

## 项目结构

```
├── Ark_emulator/           # 明日方舟战斗模拟器（见 Ark_emulator/README.md）
├── backend/                # 游戏数据显示工具主程序（PySide6 桌面端）
│   ├── desktop_app.py      # 主窗口 + WebSocket 服务 + 敌人监控界面
│   ├── run.py              # 启动入口
│   ├── build_exe.py        # 一键打包脚本（自动重编 memsrv）
│   └── app/                # Web 服务（FastAPI）
│
├── tools/                  # 内存读取工具
│   ├── timer/              # 游戏时间 & 逻辑帧寻址
│   ├── enemy_health/       # 敌方血量/属性实时监控 (adb + memsrv)
│   ├── ak_live_rng/        # 实时随机数追踪 (关键/表现双引擎 + 预测)
│   ├── speed_scanner/      # 倍速 & 暂停状态寻址
│   └── deploy_tracker/     # 干员部署追踪
│
├── ark_parser/             # 游戏数据解析管线（我方/敌方/生效帧）
│   ├── character/          # 我方数据（extract_character_data.py）
│   ├── enemy/              # 敌方数据（extract_enemy_data.py / build_sim_bundle.py）
│   └── extract_effect_frames.py  # 敌我动作生效帧
│
├── ark_api_docs/           # 服务端接口逆向文档
│
├── Ark_data/               # dump.cs 等逆向原始数据
│
├── data/                   # 游戏资源解包产物（base+hot）
├── docs/                   # 新手教程 / 排轴数据格式
├── damage_calculator/      # 网页版数值计算器
├── frontend/               # 排轴工具前端（Vue3 + Vite）
├── rougelike/              # 肉鸽数据提取脚本
├── promo_assets/           # 宣传素材
├── promo_video_work/       # 宣传视频工作区
├── unpack_work/            # 解包工作目录（体积大不入库）
│
└── AssetStudio-ArknightsStudio/  # AB 包解包工具
```

## 功能概览

### 内存寻址工具（tools/timer/）

通过内存扫描定位游戏中的 `game_time`（float32）和 `frame_count`（uint32）地址。

- 多步扫描向导，逐步缩小候选地址
- 自动推送到主程序
- 支持 MuMu、雷电、夜神、BlueStacks 等模拟器

### 倍速/暂停扫描工具（tools/speed_scanner/）

扫描游戏中的倍速等级和暂停状态。

- Phase 1：扫描 `m_speedLevel`（int32），交替 1x/2x 筛选
- Phase 2：扫描 `Time.timeScale`（float），手动切换 0/1/2 筛选
- 剩余 ≤10 个候选时弹出实时值列表，支持手动选择

### 游戏数据解析（ark_parser/）

从游戏 AB 包中提取并解析数据表。

- 干员数据：属性、天赋、技能、潜能
- 技能数据：描述、blackboard 参数
- 支持 FlatBuffers 自定义格式解析

### API 接口文档（ark_api_docs/）

基于 `dump.cs` 逆向分析的游戏服务器接口文档，覆盖认证、战斗、抽卡、基建、商店等全部系统。

## 快速开始

### 环境要求

- Python 3.8+
- Windows 10/11
- 管理员权限（读取游戏内存）
- 敌人监控需要 MuMu 模拟器且 adb root 可用；程序会自动探测 adb.exe（多盘符常见路径/注册表/PATH/ANDROID_HOME）。也可随时点击主页面顶部「选择 ADB」：除 adb.exe 外，还会列出设备地址（如 `127.0.0.1:16384`），应选择与 MAA“连接地址”相同的目标；敌人、随机数和操作记录扫描统一使用这组配置。MAA 能截图只代表普通 ADB 可用，读取 `/proc/<pid>/mem` 仍必须在 MuMu 设置中开启 Root 并重启模拟器

### 安装依赖

```bash
pip install -r backend/requirements.txt
pip install pymem PySide6 websockets numpy
```

### 启动主程序

```bash
cd backend
python run.py
```

### 运行敌人扫描诊断（命令行）

```bash
python -m tools.enemy_health --once
```

### 启动内存寻址工具

```bash
cd tools/timer
python ak_timer_ui.py
```

### 解析游戏数据

```bash
cd ark_parser

# 批量提取干员数据
python parse_characters.py

# 批量提取技能数据
python parse_skill_table.py

# 深度解析单个干员
python deep_parse.py char_1045_svash2
```

## 打包为 exe

```bash
cd backend
python build_exe.py
```

输出：
- `backend/dist/ArknightsTimeline_v<版本>.exe` — 主程序（内嵌寻址工具与 memsrv）

打包详情见 [backend/README_BUILD.md](backend/README_BUILD.md)。

## 游戏更新后如何同步更新模拟器

明日方舟数据分两层：**基础包**（大版本，随安装/重装更新）与**热更包**
（每次热更新下载，覆盖同名表）。模拟器同步 = 重新解包 base+hot → 重建解析
JSON → 刷新模拟器数据文件 → 全量验证。步骤：

### 1. 解包数据表（exportRaw，base 与 hot 各跑一遍）

```bash
CLI="AssetStudio-ArknightsStudio/AssetStudioCLI/bin/Release/net8.0/ArknightsStudioCLI.exe"
"$CLI" "<游戏>\Arknights_Data\StreamingAssets\AB\Windows\anon" \
       -t textAsset -m exportRaw -g none -o data/anon/base_<日期>
"$CLI" "<游戏>\Arknights_Data\PersistentData\Bundles\anon" \
       -t textAsset -m exportRaw -g none -o data/anon/zz_hot_<日期>
```

> `data/anon/` 目录按名排序、**后扫到的覆盖先扫到的**，因此 base 目录名以
> `base_` 开头、hot 以 `zz_hot_` 开头，保证热更表生效。

### 2. 提取数据表

```bash
python extract_tables.py        # -> data/tables/*.bin（26 张表）
```

### 3. 重建解析 JSON

```bash
cd ark_parser/character
python extract_character_data.py   # characters/skills/devices/battle_equip/uniequip

cd ../enemy
python extract_enemy_data.py       # enemy_database/stage_enemy_usage/levels 等
python build_sim_bundle.py         # stage_sim_bundle.json（模拟器关卡 bundle）
```

### 4. 刷新模拟器数据文件（新增机制/新 prefab 时按需）

对应生成脚本（均为解包中间产物的后处理）：

| 模拟器数据文件 | 生成来源 |
|---|---|
| `Ark_emulator/ark_emulator/data_buff_templates.json` | `unpack_work/buff_table_scan/parse_buff_templates.py` |
| `Ark_emulator/ark_emulator/data_enemy_prefab_catalog_current.json` | `ark_parser/enemy/extract_prefab_skills.py`（enm_pfb 导出） |
| `Ark_emulator/ark_emulator/data_level_assets_index.json` | 关卡资产解包（`unpack_work/level_assets*`） |
| `Ark_emulator/ark_emulator/data_env_systems.json` | `[uc]envsystems` AB 的 UnityPy typetree 导出 |
| `Ark_emulator/ark_emulator/data_projectile_speeds.json` 等 | 弹道/Spine 事件提取脚本 |

### 5. 全量验证

```bash
cd Ark_emulator
python tools/scan_unhandled.py --ticks 600 --workers 4   # 全 3864 关未实现节点扫描
python -m pytest tests                                   # 全量回归
```

期望：`scan_unhandled` 报告 **0 未实现节点**、回归全绿。若新版本新增机制
导致未实现节点 > 0，在 `ark_emulator/buff_templates.py`（或
`action_nodes.py`）补齐对应 handler 后复扫。

### 6. 内存工具偏移更新（可选，结构变化时）

```bash
python -m tools.enemy_health.update_from_unpack --assets <热更解包目录>
```

重建 `generated_offsets.json` 与敌人名称库 `enemy_names.json`；桌面程序的
内存地址链若漂移，按 `tools/enemy_health` 的定位流程重新扫描。

### 常见问题

- **表没变化但关卡打不开**：检查 `data/anon` 目录名排序（hot 必须
  `zz_hot_*` 在 base 之后），并重跑 `extract_tables.py`。
- **新活动关卡缺失**：活动数据未下载时客户端无对应表，需先进游戏下载该
  活动资源再解包（参考覆潮之下 OD-8 的处理）。
- **模拟器未实现节点增多**：多为新活动专属 buff 节点，按需在
  `buff_templates.py` 补 handler；肉鸽 buff 已全量计入。

## WebSocket 接口

主程序默认在本机 `127.0.0.1:8765` 提供版本化 WebSocket 服务。可在「更多自定义选项」单独关闭；关闭后不保留监听端口或后台服务线程。

- 游戏数据：`ws://127.0.0.1:8765/v1/game`
- 运维状态：`ws://127.0.0.1:8765/v1/ops`

游戏端点连接后按需订阅主题和频率，而不是接收无差别推送：

```json
{
  "type": "subscribe",
  "topics": {
    "battle": {"rateHz": 20},
    "enemies": {"rateHz": 10},
    "enemy_detail": {"scope": "all", "rateHz": 60}
  }
}
```

服务端消息均含 `type`、`schemaVersion`、`sessionId`、`sequence`、`emittedAt` 和 `data`。可订阅 `battle`、`stage`、`enemies`、`characters`、`enemy_detail`、`character_detail`、`deploy`、`rng` 与 `quality`。详情数据由共享采样缓存生成，所有客户端复用同一份读取结果；60Hz 是可请求的协议发送上限，实际频率会受数据读取质量约束。`scope: selected` 只采样指定业务 ID；`scope: all` 的重型全场详情内存采样上限为 5Hz，并可按订阅频率发送最新缓存。

连接地址与简要示例也可在程序右上角「接口说明」查看。

## 技术栈

| 组件 | 技术 |
|------|------|
| 桌面端 | Python + PySide6 |
| Web 服务 | FastAPI + WebSocket |
| 内存读取 | pymem（模拟器进程）/ adb + memsrv（设备侧服务, zig cc 交叉编译 aarch64） |
| 扫描加速 | numpy + 堆快照落盘复用 |
| 数据解析 | FlatBuffers (自定义变体) |
| 打包 | PyInstaller |

## 许可证

[MIT License](LICENSE)
