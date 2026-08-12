# ark_emulator — 模拟器核心包

数据驱动的明日方舟战斗模拟核心。全部机制按 30Hz 逻辑 tick 驱动，数据来自
`ark_parser/enemy/data`（关卡/敌人/技能）与 `ark_parser/character/data`
（干员/技能）。

## 模块分工

| 模块 | 职责 |
|---|---|
| `consts.py` | 全局常量/枚举：30Hz、索敌门控（3-tick）、异常标志、伤害类型 |
| `attributes.py` | 属性 + 四层 modifier（add/mul/final_add/final_mul） |
| `loader.py` | `DataStore`：关卡 bundle/敌人库/技能目录/关卡资产（进程级共享缓存） |
| `map.py` | 地图/瓦片/流场寻路（SPFA） |
| `waves.py` | 波次时间轴（chained 模型：后波 = 前波末事件 + postDelay + preDelay） |
| `battle.py` | `BattleController`：tick 主循环、波次/敌人/干员/阻挡/buff/费用/结算 |
| `api.py` | `Simulator` 门面：deploy/withdraw/activate_skill/pause/step/snapshot |
| `entities.py` | Unit / Enemy / Operator / Token 实体 |
| `ai.py` | 敌方 AI：移动/普攻/受控状态（眩晕/冻结/沉睡…） |
| `skills.py` | 敌方技能系统（1651 技能，含形态机/连段/召唤） |
| `operator_skills.py` | 干员技能/SP 充能/金币（诗怀雅）/弹药（能天使）等 |
| `targeting.py` | 索敌/仇恨/元素条辅助/3-tick 搜索门控 |
| `buffs.py` | Buff 系统/异常/元素条（满值扣减式） |
| `buff_templates.py` | buff 模板引擎（1341 种节点，可玩内容零未实现） |
| `damage.py` | 伤害公式（物理/法术/真实/元素，5% 保底） |
| `projectiles.py` | 弹道（速度/飞行时间/命中回调） |
| `action_nodes.py` | xLua 动作节点执行器（敌方能力图） |
| `prts.py` | 主线 15 章 PRTS 脚本调度（优先级队列 + 子动作管线） |
| `act31.py` | Act31Side 污染区（13-04 hard 狄恩杰） |
| `act35.py` | Act35Side 宝石机制（15-18） |
| `live_server.py` | HTTP + SSE 实时快照推送、`/action` 操作接口 |
| `web_ui.py` | 浏览器编辑器页面 |
| `agent_env.py` / `agents.py` | AI 环境与脚本化 agent |

## 关键常量

- `TIME_ROUGH_LOGIC_RATE = 30`：1 秒 = 30 逻辑 tick。
- `SEARCH_TARGET_TICK = 3`：目标选择器每 3 tick（0.1s）最多重搜一次。
- 伤害枚举：PHYSICAL=0 / MAGICAL=1 / TRUE=2 / ELEMENT=3。

## 数据文件（本目录）

`data_*.json` 为解包产物（buff 模板、prefab 目录、关卡资产索引、弹道速度、
Spine 事件、env 系统配置等），由 `extract_tables.py` 与 ark_parser 管线生成。
