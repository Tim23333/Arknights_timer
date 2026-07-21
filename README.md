# Arknights 明日方舟打轴工具

明日方舟游戏数据解析、内存读取、排轴打轴一体化工具集。

## 内存寻址使用说明

### 基本原理

扫描工具通过内存中的**游戏时间**（float）来定位地址。明日方舟中 **1 费 = 1 秒**，因此费用变化可以精确对应游戏时间。

### 扫描步骤

1. 进入**普通作战**（非演习作战，演习作战有概率无法扫描到准确地址）
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

### 倍速/暂停扫描

找到游戏时间地址后，可使用倍速扫描工具（`tools/speed_scanner/`）：

1. **Phase 1**：保持 1 倍速，交替点击「扫描 1 倍速」和「扫描 2 倍速」直到剩 1 个
2. **Phase 2**：点击「扫描 0/1/2」按钮，根据当前游戏状态选择：
   - 游戏暂停 → 点「扫描 0」
   - 1 倍速运行 → 点「扫描 1」
   - 2 倍速运行 → 点「扫描 2」
3. 剩余 ≤10 个时会弹出候选列表，可切换游戏状态观察值变化后手动选择

## 项目结构

```
├── backend/                # 打轴工具主程序（PySide6 桌面端）
│   ├── desktop_app.py      # 主窗口 + WebSocket 服务
│   ├── run.py              # 启动入口
│   ├── build_exe.py        # 一键打包脚本
│   └── app/                # Web 服务（FastAPI）
│
├── frontend/               # 前端（Vite + Vue）
│   ├── src/                # 源码
│   └── standalone/         # 独立 HTML 版本（v0.1 ~ v0.25）
│
├── tools/                  # 内存读取工具
│   ├── timer/              # 游戏时间 & 逻辑帧寻址
│   ├── speed_scanner/      # 倍速 & 暂停状态寻址
│   ├── deploy_tracker/     # 干员部署追踪
│   └── enemy_health/       # 敌方血量读取
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
└── AssetStudio-ArknightsStudio/  # AB 包解包工具
```

## 功能概览

### 打轴工具（backend/）

桌面端排轴工具，用于明日方舟关卡攻略视频的时间轴规划。

- 实时读取游戏内存中的时间、帧数、倍速、暂停状态
- 加载排轴 JSON，按帧对齐显示当前执行步骤
- WebSocket 推送游戏数据，支持外部客户端接入
- 支持从其他打轴工具导入 JSON

### 内存寻址工具（tools/timer/）

通过内存扫描定位游戏中的 `game_time`（float32）和 `frame_count`（uint32）地址。

- 多步扫描向导，逐步缩小候选地址
- 自动推送到打轴工具主程序
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

### 安装依赖

```bash
pip install pymem PySide6 websockets numpy
```

### 启动打轴工具

```bash
cd backend
python run.py
```

### 启动内存寻址工具

```bash
cd tools/timer
python ak_timer_ui.py
```

### 启动倍速/暂停扫描工具

```bash
cd tools/speed_scanner
python ak_speed_ui.py
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
- `backend/dist/ArknightsTimeline.exe` — 主程序（内嵌寻址工具）

打包详情见 [backend/README_BUILD.md](backend/README_BUILD.md)。

## WebSocket 接口

打轴工具启动后会开启 WebSocket 服务，推送实时游戏数据：

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
| 前端 | Vite + Vue 3 |
| Web 服务 | FastAPI |
| 内存读取 | pymem |
| 数据解析 | FlatBuffers (自定义变体) |
| 打包 | PyInstaller |

## 许可证

[MIT License](LICENSE)
