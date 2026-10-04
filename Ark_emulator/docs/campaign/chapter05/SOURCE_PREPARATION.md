# 第5章固定关卡来源准备

范围从 `mainline_catalog.json` 的 selected 字段核定为 `main_05-09`、`main_05-10`。
固定数据表提交为 `56aee3d6c5a29c3a0d192456d70d14252cbb0804`。
这份交付是独立来源清单、闭包与两种普通近战的部分内容定义；未通过独立 review，
未执行完整关卡，未做客户端对照，不代表第4章或第5章验收完成。

|关卡|主波次敌人生成数|预置弩炮|使用中的路线检查点|
|---|---:|---:|---|
|5-9|51|4|MOVE 20|
|5-10|73|10（初始 hidden，具独立 alias）|MOVE 24、WAIT_CURRENT_FRAGMENT_TIME 6、WAIT_FOR_SECONDS 5、DISAPPEAR 1、APPEAR_AT_POS 1|

5-10 的 `faust_ballis` branch 保留完整分阶段 `ACTIVATE_PREDEFINED` 动作。
主波次计数来自原生 SPAWN 动作；弩炮激活是不同的动作与计数。
原生 map、routes、waves、blockEdges、predefines、options、branches、runes、
enemyDbRefs 的 level/overwrittenData 均完整保留。FOUR_STAR 的 rune 行留作来源，
当前固定 normal difficulty1 没有将其当作生效 Buff。

## 文件与验证

- `packages/campaign/chapter05_plans/source.plan.json`：精确 stage/variant 和复用来源候选矩阵。
- `packages/campaign/chapter05_sources/native.reference.json`：8 精确变体、8 prefab、3 弹道闭包；Spine 命名绑定、OnAttack 帧、PPtr、MonoScript、SerializedState 和 Buff valueStr 完整保留。
- `packages/campaign/chapter05_environment/source.reference.json`：tile_telin/tile_telout 原生闭包、几何与路线转换原始操作数。
- `packages/campaign/chapter05_predefines/source.reference.json`：trap_007_ballis 配置、固定表、sktok_ballis 技能与 projectile_ballis、几何与 BSON 源。
- `packages/campaign/chapter05_units/ordinary.reference_model.json`：lunsbr 与 wteeth 两个无额外 passive、DB skill、talent 或回血的普通近战定义，OnAttack 分别为12、19帧。
- `packages/campaign/chapter05_reports/source.inventory.json`：逐变体语义消费者缺口、原生枚举、来源冲突和 SHA。
- `packages/campaign/chapter05_reports/ordinary.compile_validation.json`：空场景中普通定义的 V2 依赖编译检查；仅证明内容引用与能力可编译，不能作战斗或整关行为证据。

各来源 builder 的 `--check` 均完成字节复核。敌人、弩炮 BSON 的 missing_templates 均为空。
构建工具位于 `tools/chapter05/`，没有导入 V1 战斗运行时。

## 来源冲突与后续消费者

本地没有表版本对应的 token prefab；采用已冻结的官方 2025-03-27 token AB 源，
SHA `b9f16db4bfc8e8c880a0f90a1a7a74eda3b47c2188d0a151e5239d154716d475`。
下载证明、官方 manifest 身份与版本差异均写入弩炮闭包。它是明确可替换的参考候选，
获得表版本对应源后必须重新提取和审核；本交付没有将候选版本默认为固定表版本。
本地 sktok_ballis skill 与 projectile_ballis 各有唯一精确 prefab；混合源身份保留。
`dump.cs` 枚举保留完整原文和文件 SHA，但旧 dump 与当前源版本对齐也未验证。

zomstr 每秒回血200、zomsbr 每秒回血80，均被普通模块排除。
hammer 的 EnemySkill/ReadyEnemySkillEffect 与 DB stuncombat 不能省略。
lunmag 的双 RangedAttack 槽、SelectorTrigger、21帧和弹道需要精确目标与攻击消费者。
Faust 的源 BB invincible.duration=150、CriticalHit cooldown/initCooldown=17、atk_scale=2，
以及 SummonBallis cooldown=30/initCooldown=15/branch_id=faust_ballis 均保留，
需要技能、无敌、分支调度和弩炮激活的消费者审核。
Mephisto 的 Heal 33帧、GlobalAuraAbility、源 BB healaura.hp_recovery_per_sec=1
需要治疗目标、全局光环及回血语义消费者。
弩炮还需要技能 SP 时钟、TrapMode 地块重写、FarthestPointMovement、
HitBehaviour/SimpleProjectile 碰撞与生命周期消费者。完整关卡必须同时消费这些依赖。
