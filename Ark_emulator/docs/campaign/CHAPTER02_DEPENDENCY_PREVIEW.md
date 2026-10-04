# 第2章源依赖预览

读取已恢复的原生level与固定enemy数据库，用现有离线依赖构建器实际生成
`packages/campaign/chapter02_plans/level_main_02-09.json` 和 `level_main_02-10.json`。
这是源依赖计划，`runnable=false`；没有将首章攻击、Boss模型或旧pending标签直接当成当前完整实现。
固定公开表pin仍为 `56aee3d6c5a29c3a0d192456d70d14252cbb0804`。

| 原生关卡 | 出生 | 敌方variant | 控制 | 实际引用checkpoint |
|---|---:|---:|---|---|
| level_main_02-09 / 2-9 | 52 | 5 | DISPLAY7 | MOVE56、WAIT_SECONDS18 |
| level_main_02-10 / 2-10 | 36 | 12 | STORY1、DISPLAY1 | MOVE70、WAIT_SECONDS10、WAIT_FRAGMENT1 |

2-9依赖：yokai、yokai_2、airdrp、airdrp_2、defdrn。下一源审计应恢复每个exact prefab/combat/selector/projectile，
区分空降地面兵、被动飞行与实际攻击无人机，并验证空中路线、索敌/阻挡资格、伤害类型和倍率。
不能仅由enemy key或“飞行”标签推断全部能力。

2-10依赖：aoemag、mob/mob_2、mocock、shield、litamr、wizard、skulsr、wteeth、nsabr、defdrn、handax。
已取源的mocock和基础近战可作来源参考；导入前需核对实际DB level/override及该关版本，
保留所有技能/天赋，不因ID相同就复用不匹配variant。
碎骨与AOE/术师/重装敌人的技能及阶段需单独恢复。当前计划的通用required_mechanics列表
只是保守粗分类，不能用它证明敌方只有physical damage。

地图、native options、runes/predefines/branches、敌DB继承、实际波次、完整路线及source hashes均由计划保存。
后续按第1章通用接口闭合状况推进这一批源审计；当前没有跑这两关、没有新增正式批准。

## exact源初读后的分类纠正

子agent实际读取DB/prefab后确认，airdrp/airdrp_2是WALK+MELEE空降兵，不能从名字猜成drone。
defdrn是FLY+NONE防御光环，源def+300/radius2.5；攻击飞行单位为yokai_2 FLY/RANGED。
yokai_2的mode combat组件虽叫MeleeAttack，但source分类RANGED、无projectile，不能按类名自动套blocked-only行为。
aoemag为RANGED、combat arts2、无projectile，粗计划中的physical机制列表不是准确伤害分类。
碎骨有两mode，combat与attack指向不同真实节点，源审计正在分开冻结全部指针/选择器/事件。
这些是初读事实，完整source产物与SHA交付后再作机制转换，不当作已运行攻击模型。
