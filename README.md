# Arknights 明日方舟游戏数据显示工具

明日方舟游戏数据实时显示工具集：通过内存读取，实时显示**游戏时间、逻辑帧数、倍速状态、场上所有敌人的名称/血量/属性/坐标/技能CD、战斗随机数序列（已消耗+未来预测）**，并附带游戏数据解析与服务器接口逆向文档。

第一次使用请阅读：[新手使用教程](docs/新手使用教程.md)。

## 主程序功能（backend/）

`ArknightsTimeline.exe`（PySide6 桌面端，单文件分发）：

- **时间/帧数卡片**：实时读取游戏内置时间（float）与逻辑帧数（uint32），经内嵌寻址工具一次性定位地址后秒级启动
- **敌人实时监控**：进关卡后点「开始扫描」定位当前 `BattleController` 并读取关卡完整固定出怪序列（通常约 20-40 秒，场上尚无敌人也可用；结果缓存），随后准实时展示所有敌人的：
  - 名称 / 编号 / 敌人 ID
  - 血量（进度条 + 数值）、攻击 / 防御 / 法抗 / 移速 / 攻速
  - 地图坐标，以及“未出场 / 场上 / 已离场”生命周期；死亡和漏怪均归为已离场
  - 技能 CD（剩余/总冷却，如浮士德「SummonBallis 11.4/15s」）
  - 战斗状态、倍速、战斗时间
  - 固定敌人从开局起按预定出场顺序显示；条件分支/召唤等动态敌人首次出现后追加
  - “离场敌方不显示”默认勾选，取消后可回看已离场敌人的最后一帧数据
  - 轮询间隔 0.01s、渲染 60fps
- **随机数追踪**：进关卡后点「扫描随机数」一次性定位随机数引擎（首次约 15-30 秒，地址缓存后秒级），随后实时展示关键随机（战斗判定）：
  - 最近消耗序列（序号/值/原始值）+ 未来预测（个数自定义 1-500，默认 30）
  - 游标位置、累计消耗、消耗速率
- **全局操作记录**：进关卡后点「扫描操作记录」定位 BattleLogger（快速路径约 20 秒，完整堆扫描约 1-2 分钟），随后准实时展示每一次 部署/撤退/技能 操作：
  - 战斗时间、操作类型、干员名、朝向、地图格子坐标
  - 代理作战（PRTS）直接显示完整代理序列（静态）
  - 支持一键导出 JSON（与 ak_live_log 同格式）
- **内嵌寻址工具**：点击即自动提取运行，无需安装 Python
- **WebSocket 推送**：游戏数据实时推送给外部客户端
- 窗口置顶、管理员权限自动提权

## 敌人监控原理（tools/enemy_health/）

通过 adb 读取 MuMu 模拟器中游戏进程（IL2CPP, arm64）的内存：

```
MuMu 模拟器 (Android arm64)
  └── 明日方舟进程
       └── Scheduler.m_managedWaveEnemies (List<Enemy>)
            └── Enemy: m_hp / <id> / Attributes.m_cachedData
```

- **定位**：主路径在设备侧扫描当前 `BattleController` 的 Il2CppClass/对象，沿
  `BattleController → Scheduler → m_managedWaveEnemies` 取得实时列表，并从
  `BattleController → LevelData.waves` 解析开局即存在的固定 SPAWN 顺序，因此不再
  依赖场上已有敌人。旧的 `enemy_` 字符串 + HP 特征全堆扫描保留为版本漂移兜底；
  地址链缓存到 `enemy_cache.pkl`，有效时可直接复用
- **轮询**：设备侧常驻内存服务 `memsrv`（aarch64 静态二进制，`nc -L` +
  `adb forward` TCP 长连接），打开 `/proc/<pid>/mem` 一次后每次读取仅一个
  pread，稳态 ~1-2ms/帧；服务不可用时自动回退慢速 adb 读取
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
├── ark_parser/             # 游戏数据解析
│   ├── parse_characters.py # 批量提取干员数据
│   ├── parse_skill_table.py# 批量提取技能数据
│   ├── deep_parse.py       # 单干员深度解析
│   └── extract_tables.py   # 从 AB 包提取数据表
│
├── ark_api_docs/           # 服务端接口逆向文档
│
├── Ark_data/               # dump.cs 等逆向原始数据
│
├── frontend/               # 旧排轴前端（已停用）
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
- 敌人监控需要 MuMu 模拟器且 adb root 可用（MuMu 默认支持）；程序会自动探测 adb.exe（多盘符常见路径/注册表/PATH/ANDROID_HOME），探测失败时可在点击「开始扫描」后手动选择 MuMu 安装目录下的 `shell\adb.exe`，选择一次即记住

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
- `backend/dist/ArknightsTimeline.exe` — 主程序（内嵌寻址工具与 memsrv）

打包详情见 [backend/README_BUILD.md](backend/README_BUILD.md)。

## WebSocket 接口

主程序启动后会开启 WebSocket 服务，推送实时游戏数据：

```json
{
  "game_time": 12.345,
  "frame_count": 741,
  "connected": true,
  "speed_level": 2,
  "speed_name": "2倍速",
  "timescale": 2.0,
  "is_paused": false
}
```

连接地址见程序右上角「接口说明」按钮。

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
