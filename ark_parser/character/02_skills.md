# 02 技能表结构与 SP 规则

> 数据：`data/skills.json`（1795 条）。结构依据 dump.cs:188400（SkillDataBundle）
> 与 188379（LevelData）、188231（SpData）。

## 1. SkillDataBundle

`{skillId, iconId, hidden, levels[]}`；levels 为 SkillDataBundle.LevelData：

| id | 字段 | 含义 |
|---|---|---|
| 0 | name | 技能名 |
| 1 | rangeId | 技能攻击范围引用（3-6 等） |
| 2 | description | 描述（含 `{atk:0%}` 占位符） |
| 3 | skillType | 0=PASSIVE 1=MANUAL 2=AUTO（SkillType，dump.cs:1442389） |
| 4 | durationType | 0=NONE 1=AMMO（弹药型，dump.cs:1442399） |
| 5 | spData | SP 配置（见 §2） |
| 6 | prefabId | 技能 prefab 键（运行时 Ability 来源） |
| 7 | duration | 持续时间（秒；弹药型=弹药数语义另见 blackboard） |
| 8 | blackboard | 技能参数（i2f 已转换，保留 value_raw） |

## 2. SpData（dump.cs:188231）

| id | 字段 | 含义 |
|---|---|---|
| 0 | spType | 0=NONE 1=随时间 2=攻击回复 4=受击回复 6=攻或受 7=ALL（SpType，dump.cs:1442353） |
| 1 | levelUpCost | 升级消耗 |
| 2 | maxChargeTime | 最大充能层数 |
| 3 | spCost | SP 消耗（自动技能满 SP 释放） |
| 4 | initSp | 初始 SP |
| 5 | increment | 每次增长量（随时间型为每秒，攻击/受击型为每次事件） |

示例（skchr_amiya2_1 技能 1“影霄之夜”Lv1）：
`{skillType:1, spData:{spType:1, spCost:45, initSp:10, increment:1.0},
duration:25.0, blackboard:{atk:0.2, prob:0.6, talent_scale:2.0}}`

## 3. 常见黑板键（我方技能）

`atk`/`atk_scale`（攻击倍率）、`prob`（概率）、`duration`、`max_target`、
`range_radius`、`interval`、`sp`（回 SP）、`talent_scale`、`cnt`、`stun`、
`projectile_*`（弹道）、`trait_*` 等；`skcom_*` 通用技能（如
`skcom_charge_cost[1..3]`）提供模板参数。

## 4. 运行时注意（【推断】，基于 BasicSkill dump.cs:420664）

- `skillType=MANUAL`：玩家手动释放（需要玩家输入）；
- `skillType=AUTO`：SP 满自动释放（`BasicSkill.IsAutoSkillTriggerable`，dump.cs:421083）；
- `skillType=PASSIVE`：无 SP，出场即挂载；
- `durationType=AMMO`：duration 语义为“弹药持续/次数”，由 blackboard 驱动；
- 技能实际效果走 `prefabId` 对应的 Ability/BasicSkill prefab（在
  `data/battle/prefabs/[uc]skills.ab_unpacked` 等），blackboard 只提供参数。
