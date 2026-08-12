# Ark_emulator — 明日方舟战斗模拟器

数据驱动的明日方舟战斗模拟器：**加载真实关卡数据、按 30Hz 逻辑 tick 模拟
敌方/我方全部行为（移动、攻击、技能、阻挡、位移、增益减益、元素损伤、
环境机制），支持自定义编队与自定义敌人，并实时对外输出完整战场快照**。
核心用途：AI 打图分析、机制研究、数据验证。

## 功能

- **选择关卡**：加载官方关卡数据（主线/活动/hard/训练等，共 3864 关），
  波次、路线、runes、全局 buff、预部署全部还原。
- **自定义编队**：`squad=[{"charId","phase","level","potential"}]` 注入任意
  干员（454 名全部可部署并激活技能）。
- **自定义关卡敌人**：`custom_enemies=[{"key","count","startTime",
  "attributes"}]` 覆盖敌人属性/数量/出场时间。
- **实时快照**：`snapshot()` 输出全战场 JSON（干员/敌人/弹道/波次/buff/
  异常/技能/PRTS/宝石/污染区/沙盒/肉鸽状态等）；LiveServer 提供 HTTP+SSE
  实时推送，`POST /action` 支持部署/技能/撤退。
- **暂停/单步/继续**：`pause() / step(n) / resume()`。
- **AI 接口**：`AgentEnv` + `GreedyDefender`/`BeamAgent`，可直接打图。

## 核心设计

- 固定 **30Hz 粗逻辑**（`consts.TIME_ROUGH_LOGIC_RATE=30`），每 tick 依次
  处理：波次 → 敌方 AI（技能/移动/攻击）→ 干员 → 阻挡 → buff → 弹道 →
  地形 → 费用 → 结算。
- 索敌：阻挡优先 → 特殊优先级 → 仇恨值 → 最早出现；目标选择器按
  `SelectorTrigger.SEARCH_TARGET_TICK=3`（0.1s）门控重搜。
- 伤害：物理/法术/真实/元素四类，攻防公式、法抗、闪避、5% 保底全部还原。
- 事件总线 `EventBus`：所有行为发事件（攻击/伤害/技能/刷怪/漏怪…），
  AI 与外部客户端可订阅。

## 目录结构

```
Ark_emulator/
├── ark_emulator/          # 模拟器核心包
│   ├── consts.py          # 常量/枚举（30Hz、索敌门控、异常标志）
│   ├── attributes.py      # 属性 + 四层 modifier
│   ├── battle.py          # BattleController（tick 主循环/波次/结算）
│   ├── api.py             # Simulator 门面（deploy/withdraw/activate_skill）
│   ├── entities.py        # Unit / Enemy / Operator / Token
│   ├── map.py             # 地图/流场寻路
│   ├── waves.py           # 波次时间轴（chained 模型）
│   ├── ai.py              # 敌方 AI（移动/普攻/受控状态）
│   ├── skills.py          # 敌方技能（1651 个，零 no-op）
│   ├── operator_skills.py # 干员技能/SP/金币等
│   ├── targeting.py       # 索敌/仇恨/3-tick 门控
│   ├── buffs.py           # Buff/异常/元素条
│   ├── buff_templates.py  # buff 模板引擎（1341 种节点，可玩内容零未实现）
│   ├── damage.py          # 伤害公式
│   ├── projectiles.py     # 弹道
│   ├── prts.py            # 主线 15 章 PRTS 脚本调度
│   ├── act31.py           # Act31Side 污染区（13-04 hard）
│   ├── act35.py           # Act35Side 宝石机制（15-18）
│   ├── action_nodes.py    # xLua 动作节点执行器
│   ├── loader.py          # DataStore（bundle/敌人/技能/关卡，进程级缓存）
│   ├── live_server.py     # HTTP + SSE 实时服务
│   ├── web_ui.py          # 编辑器页面
│   ├── agent_env.py       # AI 环境（step/reward/done）
│   └── agents.py          # 脚本化 agent
├── tests/                 # 735 项回归测试（pytest，约 8 分钟）
├── docs/                  # MECHANICS / DELIVERABLES_AUDIT / TEST_SCOPING
├── examples/              # 示例（demo / agent / run_sim / bot）
├── tools/                 # scan_unhandled.py（全关卡未实现节点扫描）
├── custom_levels/         # 自定义关卡样例
└── data_raw/              # 解包原始数据（enm_pfb 等，体积大不入库）
```

## 快速开始

```bash
# 启动实时网页战斗控制台（默认自动打开浏览器）
python run_web.py

# 运行一个关卡（自动部署示例编队）
python examples/demo_main_01-01.py

# AI 打图（GreedyDefender）
python examples/agent_play.py --level level_main_01-01

# 启动 LiveServer（浏览器打开 http://127.0.0.1:端口/）
python examples/run_sim.py --level level_main_15-18 --port 8787
```

网页控制台支持关卡和干员搜索、实时加入底部编队、拖拽或点击地图部署、卡片
实时 HP/SP/冷却/费用/阻挡状态、地图实时单位/弹道显示、部署朝向、技能与撤退、
暂停/逐帧/推进一秒、0.5～4 倍速、胜负终局提示及结构化战斗事件流。可用
`python run_web.py --level level_main_15-18 --port 8787` 指定初始关卡和端口。

网页与模拟器公共 API 均使用左上角为 `(row=0, col=0)` 的坐标；官方关卡导出的
底部原点路线与 `cells` 地图索引会在加载时统一转换，前端无需再次翻转。

Python API：

```python
from ark_emulator import Simulator

sim = Simulator(level_id="level_main_01-01", squad=[
    {"charId": "char_502_nblade", "phase": 2, "level": 50}])
sim.battle.battle_cost_add(100)
sim.run_ticks(30)
sim.deploy("char_502_nblade", 3, 4)
sim.run_ticks(600)
print(sim.battle.finished, sim.battle.result)   # 结算
snap = sim.battle.snapshot()                     # 全战场 JSON 快照
```

## 测试与验证

```bash
cd Ark_emulator
python -m pytest tests                 # 735 项全量回归（约 8 分钟）
python tools/scan_unhandled.py --stride 1   # 全 bundle 3864 关未实现节点扫描
```

验证基线（2026-08-11）：
- 全 bundle **3864 关零未实现 buff 节点**（`scan_unhandled.py` 实测）。
- 敌方 **1651 个技能零 no-op**；干员 **454 名全量部署+技能激活通过**。
- 主线 0-16 章 + 覆潮之下等全部可玩内容正常加载运行。

## 范围说明（按用户确认）

- 肉鸽 / 保全派驻 / 卫戍协议 / 生息演算的**关卡不要求实现**；**肉鸽对应
  buff 已全部计入**（数据中 22 类 Roguelike 节点全覆盖）。
- 其余活动专属节点（约 700 种）仅在对应活动数据存在时按需实现。

## 依赖

- Python 3.8+（开发环境 Python 3.12）
- 运行时仅标准库；测试用 `pytest`

## 游戏更新后如何同步

见项目根目录 [README.md](../README.md)「游戏更新后如何同步更新模拟器」。
