# Mephisto 作者模块与可复核收据

范围是固定5-10中的 `enemy_1507_mephi@0/6468197a2a582f8b`。
模块实际消费普通治疗与常驻全场光环；Faust、整关编排与客户端对照另行推进。
固定运行核心是M94：
`cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7`，未修改核心。

## 核明的原始来源

- HP28000、ATK500、DEF200、MR60、移动0.5、ASPD100、普通间隔6s。
- UnitMode `_combat` 和 `_attack` 共享同一Heal PPtr，故只实现一份治疗能力。
- Heal：OnAttack33帧，FROM_OWNER1、AT_BEGINING0、非持续、非HP比例、无EP治疗、无附加Buff。
- AdvancedSelector：ALLY1、motionALL3、CHAR1，HP_RATIO_NOT_FULL_ASC3，max3，owner允许。
- CircleRange可缩放、trigger circle原半径1、DBrangeRadius20；采用显式db-scaled point radius20政策。
- 无DB EnemySkill/SP行，不伪造skill priority、SPcost、initCooldown或额外技能。
- GlobalAura TargetValidator同样ALLY/ALL/CHAR，无mutant标签过滤。
- Buff mephi_t_healaura，attributeType13=HP_RECOVERY_PER_SEC，formulaItem1=MULTIPLIER，
  loadFromBlackboard1，来自 `healaura.hp_recovery_per_sec=1`，maxStack1、empty BSON模板。

## 实际消费者

治疗使用真实heal效果，每次源ATK500，最多捕获三个未满血最低HP比例的友方角色，
在33帧包生效，按6s间隔启动。生命上限实际钳制；允许治疗自己，受heal_free、
target_free、ally_target_free、阵营/运动/类别与显式healing_allowed资格约束。
目标在开始时捕获，死亡/失活目标被跳过，不将第四个目标替补成新目标。
HP比例相同使用稳定actor ID作参考排序。

行为触发器使用纯targeting.eligibility图，先消费原始资格，再明确过滤满HP与heal_free。
这使“全满HP时继续走路”和“有伤员时停止行走准备治疗”都由实际资格决定，
没有使用假治疗事件触发AI。未声明selection_state的旧玩家角色采用明确side0默认，
不会被错误当作Mephisto的友方；作者C5敌人均显式side1。

光环使用现有owned aura父/子Buff，真实修改有效hp_recovery_per_sec，
与已审核中的C5regen资源消费者联动：200/s→400/s，80/s→160/s，零基础仍为零。
资格为全场友方CHAR，不强加mutant标签；有正恢复的未标mutant友方同样翻倍。
Source死后立即移除其owned成员，恢复基础值；未出生/初始dormant源不会提前挂光环。
真实晚出生regen单位会在首tick前加入已有光环。

## 明确可替换的参考政策

模块metadata保存原始prefab、Heal/Selector/GlobalAura/Validator、BB、几何与原生枚举原文/SHA。
固定DB/关卡提交为 `56aee3d6c5a29c3a0d192456d70d14252cbb0804`，native.reference SHA
`323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5`。
本地prefab/Spine与该表、旧dump枚举与当前客户端版本的对齐未验证。

下列是明确参考政策，不表示已恢复原生方法正文：

- point radius20包含边界；body/collider重叠与CircleRange实际缩放需校准。
- 相同HP比例按actor ID；原生比较器tie细节待校准。
- cast时资格、hit时读取源属性及目标资源状态；windup期间新状态旗标细节待校准。
- windup为33/30/ASPD，minimum .01；普通6s间隔采用现有time.interval。
  通用cast在末包完成，原生动画95帧、clamp与FSM尾段时序需独立校准。
- aura非heal通道，heal_free不禁自然恢复乘数；native basic TargetValidator/status细节待校准。
- 每source父持有一份maxStack1成员；多source独立贡献相加是可替换参考stack政策。
  固定关卡只有一个Mephisto，双源测试证明的是该参考政策和分父移除行为。
- 固定Mephi使用route1，仅MOVE/MOVE/WAIT_CURRENT_FRAGMENT_TIME。
  多地图layer、reborn或route-hidden/Disappear时的native开关保留原值，需在其他使用场景明确组合政策。
- 失活/死后移除光环；initial dormant激活走既有生命周期初始化。

## 作者验证

45项实际作者测试通过，覆盖Heal33/180tick间隔、max3排序、自己与饱和、飞/地资格、
类别/阵营/状态资格、半径边界、cast捕获/死亡目标、满HP移动与伤员停止、
全场200→400与80→160、零仍零、未标mutant正恢复、重复reconcile不叠加、
双源参考policy分父移除、真实28kHP损失击杀、dormant激活、真实mutant联合治疗/恢复、
晚出生成员，以及pending治疗/光环/伤害命令的实际落盘CP与公有replay。

`evidence/author.evidence.json` 保存alive、damage_death、dormant_activation三组
独立可重编译probe、实际CP、replay、全载荷JSONL和三路径的观察SHA。
复验时编译probe并额外加载 `packages/campaign/chapter05_units/regenerating/model.json`。

作者测试代码位于 `tools/chapter05/mephi/test_module.py`，构建器为build_module.py，
收据工具为emit_evidence.py。所有formal/independent/whole-stage/client字段保持false，待独立复核。
