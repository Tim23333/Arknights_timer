# 固定队伍技能组合原型

第一份可执行组合为桃金娘S2，输出 `packages/campaign/skills.myrtle.json`。
它以真实技能数据、技能prefab和角色mode2治疗组件驱动V2能力/效果/选择器/Buff，
状态为 **partially_implemented**，场景明确标记 not_formal_mainline。
测试使用合成atk=100及受伤友军，不是官方E2/70/信赖100单位的验收。
没有修改ark_sim内核，没有调用V1运行时，没有创建转换批准收据。

## 桃金娘S2原始证据

官方规范化表的所选专三 `skchr_myrtle_2`与固定参考包逐字段对照：duration16、SP24、初始SP10、自然回复类型1，
blackboard value16/cost1/interval1/attack@heal_scale0.5。
技能prefab `AttackAbility._attackBlackboardModeIndex=2`，`_allowSpRecoveryWhenAffecting=0`；
periodic_cost Buff的triggerInterval=1、waitFirstTriggerInterval=1、firstTriggerInterval=-1。
另一个switch_mode_restart_fsm Buff把模式设为2、将block属性乘为0。
这些是实际读出的字段，不凭技能文本猜第一tick。

进一步只读UnityPy提取桃金娘charpack，原始CAB及相关组件随skill包manifest.metadata封存，
包含精确pathID/scriptPathID和来源SHA：

- 角色root `6228503509698720609` 的 `_modes[2]` 指向 `4170900438269670241`。
- mode2的 `_attack` 指向治疗组件 `673272970802344801`。
- 治疗组件 `_cooldown=1`、`_preDelay=0.5329999923706055`、`_escapeTime=1`、`_isCont=1`、`_timeMode=2`。
- 治疗selector `-4407543729288334495` 的 `_maxNum=1`、`_limitTargetNum=1`、`_excludeOwner=0`。
- mode2 attack trigger `-661438494929734815` 的 `_keepTarget=0`，支持每次重新选择。

范围 `x-4` 从历史目录的离线 `data_range_table.json` 原始JSON行读取，实际为包含自己的3×3九格。
该文件仅作为离线来源，不导入历史代码；hash已锁定。其与当前native range_table的重新对照仍需补齐。
最低生命比例选择由V2 healing score提供；native selector `_postFilter=3` 已实际读取
`Ark_data/dump.cs` 的 `FilterUtil.FilterType.HP_RATIO_NOT_FULL_ASC=3` 映射，
并核对BLOCK_CNT=5与FINAL_SCALER=3；枚举原始定义和dump hash随包锁定。
客户端同生命比例下排序仍须对照。

## 当前可执行模型与时序边界

| 项目 | 实际V2组合 | 独立预期 |
|---|---|---|
| 费用 | manual activation支付24SP；初始SP10，每秒周期回复1 | 14个回复周期后24；不足时无支付、无技能效果 |
| 费用产出 | effect.modify_resource作用于system/battle.dp；first wait1秒、repeat16次 | t=1..16秒共16DP，t=16端点不遗漏 |
| 治疗 | each_hit重选3×3范围内一名受伤存活友军，含自己；scale0.5 | 第一命中preDelay量化16tick，再每30tick一次；atk100每次50，共16次 |
| 停攻 | manual cast blocks_attacks=true，持续16秒 | 普攻在施放中无damage.accepted，结束后恢复 |
| 阻挡 | Buff将block_count的final_ratio设为-1，持续16秒 | 施放时有效block_count=0，结束恢复1 |
| SP暂停 | sp.resource参数freeze_while_cast=true，仅manual冻结 | 施放中SP保持0，结束恢复周期驱动；普攻不冻结 |
| 无伤员 | 治疗selector为空，但能力不要求目标 | 仍支付SP并产生16DP，不产生虚假治疗 |

此模型选择明确的DP末端结算政策：t=16的最后费用effect先结算，然后能力完成。
因此在V2的 `advance` 半开推进区间中，推进到结束tick本身还只有15DP，必须执行该tick才到16。
治疗位于[0,16)内，命中为ceil(.533/(1/30))=16tick，之后每30tick，共16次；结束端点不多治疗一次。
SP/停攻/Buff恢复遵循当前阶段顺序，技能结束tick后普通攻击才重新执行。

原生字段给出模式、预延迟、周期和暂停条件；**客户端同tick到期/费用结算排序、动画/FSM切换对齐
仍pending**。这些边界没有被本原型提升为客户端验证。不能把该组合的合成fixture通过当作桃金娘
完整官方单位通过；驻场天赋25HP/秒、官方属性/信赖、部署/撤退、动作动画和生命周期还未并入。

## 其余十一技能的阶段依赖

构建工具仅实现桃金娘S2，其他选定技能调用会明确拒绝，保留真实技能ID及待验证机制列表。
没有用普通真伤替代以下技能：

| 技能 | 可复用组合方向 | 必需先补齐/验证的依赖 |
|---|---|---|
| 风笛S3 `skchr_bpipe_3` | atk/def/block Buff、三段攻击 | 普攻mode切换与生效帧、概率天赋、击杀DP、编队初始SP |
| 陈S1 `skchr_chen_1` | 下次攻击替换、物伤倍率、眩晕状态 | 攻击SP触发与双击原始攻击边界、眩晕阻断/恢复、周期SP天赋 |
| 雷蛇S1 `skchr_liskam_1` | 受击SP、自动触发、防御Buff | 一次挡伤消费、受击SP边界、随机邻友SP与目标资格 |
| 塞雷娅S3 `skchr_demkni_3` | 范围周期治疗、减速/法伤增幅Buff | 治疗SP授予边界、驻场属性叠层、同tick结束与范围进出 |
| 白面鸮S2 `skchr_plosis_2` | 攻击间隔Buff、扩大治疗selector | 原生三目标治疗模式、SP光环同类最高、自然回复速率生效 |
| 能天使S3 `skchr_angel_3` | 自动满SP启动、五段攻击 | 15秒模式和原生连射间隔、对空优先、部署随机友军增益 |
| 艾雅法拉S3 `skchr_amgoat_3` | 范围/攻击间隔Buff、多目标法伤 | 随机六目标选择和原生RNG消费、部署随机SP、术师光环 |
| 凯尔希S3 `skchr_kalts_3` | 召唤绑定技能、随时间下降atk、真实伤害 | 原生Mon3tr配置/绑定/距离防御、击杀条件、未击杀HP流失、死亡触发 |
| 铃兰S3 `skchr_lisa_3` | 停攻、范围停顿/脆弱、生命回复 | 生命回复与治疗区分、停顿续期/范围离开、脆弱同类规则、SP光环 |
| 温蒂S3 `skchr_weedy_3` | 法伤弹道、炮台技能联动 | 真正力学位移/重量/碰撞/坑洞、移动距离真伤、炮台范围SP与联动 |
| 夜莺S3 `skchr_cgbird_3` | 范围治疗、法抗Buff | 概率法闪RNG/命中拒绝、鸟笼嘲讽/生命流失/退场、原生三目标治疗 |

原始数据已读并冻结不等于这些能力存在；上表是实现路线和拒绝边界。

```powershell
..\.venv\Scripts\python.exe tools/build_campaign_skills.py
..\.venv\Scripts\python.exe tools/build_campaign_skills.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.myrtle.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_skills.py -q
```

测试通过真实Compiler/Engine验证付款、周期、动态单目标选择、范围、边界、停攻、SP冻结和精确
checkpoint/input replay。它们不创建独立review批准，不提升正式主线状态。

开发检查：build/--check与V2 validate成功；此前九项组合测试在同一实现下通过（30.29秒），
同行独立运行七项非构建/回放机制用例也通过。随后按同行建议加入native maxChargeTime=1、
postFilter/excludeOwner/keepTarget拒绝门及第十项自疗/死亡友军过滤反例。
最终十项与检查点/回放将等root事件资源原语定型后重新验收；开发中曾因V2源码并发改变被
runtime身份锁明确拒绝续跑，未绕过身份锁或放宽回放预期。
