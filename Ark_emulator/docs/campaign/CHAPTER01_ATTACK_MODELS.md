# 第1章 MultiMelee 与 ranged 内容模型

本批在冻结M8全套之后新增工具、内容与定向测试，没有修改ark_sim、旧源审计或旧包，不运行整关长程。`tools/build_chapter01_attack_models.py` 构建 `packages/campaign/chapter01_models/attacks.model.json` 与 assertions.json，供后续关卡组合导入。

输入锁定chapter01 native.reference的SHA `a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd`，构建时重核敌DB/锁表、相关prefab、动画CAB、projectileCAB以及源manifest等原始文件SHA。所有原生特殊字段、combat PathID、确切类名和动画绑定放入各profile；没有调用V1或改共享动画reader。

三个实体的HP/ATK/DEF/RES/move speed/mass/attack interval来自实际level0敌DB；攻击组件、模式数、OnAttack帧、弹道速度/寿命/hit限制/source-invalid策略有严格source guard。能力ID为 `ability/<nativeID>/ch1_model_normal`，单位ID保持 `unit/<nativeID>`。manifest.metadata.integration提供单位→普通攻击覆盖表及ranged behavior覆盖。导入时替换旧普通攻击，保留关卡spatial、melee behavior与实例规则，不在同一单位上追加第二套automatic normal；不要将本包同ID完整实体盲目重复加入另一份draft。

旧draft对ranged也使用ground_melee机器（attack仅blocked），仅换能力会令未被阻挡的投掷者不发包。新包提供显式声明式move+attack允许的ranged模型机器；独立反例证明旧gate不发射、应用behavior_overrides后28tick命中。这不是原生ranged停步/FSM正文实现，移动期间选敌、施放停移与转向时钟仍model_gap。导入不能遗漏该覆盖，也不能把模型move+attack允许称为原生行为。

## 潜行者 enemy_1014_rogue

原生类MultiMeleeAttack，ATK350、baseAttackTime1.2。源additionalTimes1、splitDamage1、waitAttackEventForAllAttacks1、triggerDelta0、refreshInputTargetOnCheckSpell0；exact Attack中OnAttack12/23。模型捕获施放时当前blocker，两次命中不刷新目标。

显式profile `equal_total_attack_split_before_defense_v1` 将raw atkScale1均分为两个scale0.5，再逐包运行现有物理伤害规则。DEF30时每包350×0.5−30=145，HP2000经过12/23帧后为1710。先减DEF再平分会得到160×2，是另一种公式；独立测试明确区分它。

原生splitDamage正文未恢复，因此这是可替换模型选择，不能称为客户端分伤公式已校准。模型保留live source/target属性读取、未缩放source-event windup与普通attack interval驱动，原生GetTimeScale、maxAnimScale1.1、FSM/协程仍client_pending。

目标在首包死亡时第二包通过内容condition跳过，保留captured target而不偷换到其它友方；攻击者在首包后退场会通过现有Lifecycle取消未发出的第二包。一个双击cast只发一次attack.accepted；两个实际接受packet各发damage.accepted。测试通过明确合成clock资源验证source+1、receiver+2，没有给原生SP恢复0的敌人添加假SP。

## 两个鸡尾酒投掷者

enemy_1028_mocock与mocock_2分别ATK180/250，baseAttackTime2.7/2.2；源都是RangedAttack、physical1、rawScale1、OnAttack22、rangeRadius1.75、projectile_mocock。SimpleProjectile寿命10秒、maxHit1/stopAfterMaxHit1、stopWhenSourceInvalid0、alwaysHitTraceTargetInTheEnd1；ParacurveMovement speed5。全部字段原样保存。

模型选择living player+ground，圆形半径1.75，limit1。native selector的postFilter4（HATRED_DES）没有可恢复的仇恨算法；本profile明确用 `newest_runtime_id_priority_v1` 作为可替换排序，而不是默认近距离排序或假称原生仇恨公式。原生target-free/camouflage/abnormal过滤尚不能完整表达，记录model_gap；测试的明确合成目标不具这些特殊状态。高台站立的地面单位可由转换后的ground标签参与，air标签被排除。

施放时捕获目标；22帧发射时读取双方平面位置。纯flight rule输出 `min(launch_distance/5, 10)`，向上量化到逻辑tick。已发射后目标移动不重排飞行，也不在途中重算弧线路径。这不是native Paracurve追踪算法；曲线、碰撞、动态追逐与失效正文仍model_gap/client_pending。

常规距离1得到0.2秒（6ticks），在28帧实际命中，DEF30损失150/220。目标在施放后、发射前移至距离60时，distance/speed为12秒，本模型明确以原生寿命10秒封顶并尝试命中仍活着的captured target；这一到期策略参考alwaysHitTraceTargetInTheEnd1，但客户端回调未验证。测试严格在tick322命中，而非382。没有把寿命10忽略掉或将正常圆内最大飞行0.35秒错误宣称为移动目标的全局上限。

waitForProjectileInvalid0映射为发射tick结束cast，不等待弹道，后续普通attack时钟保持独立。发射前攻击者死亡取消未发包；发射后已排的impact保留，与本模型source-invalid字段选择一致。目标死亡/退场时，impact内容condition跳过伤害，无retarget，任务正常清理。source attributes/target defense在hit读取；source原生useCachedAtkOnly0保留为依据，实际客户端采样规则仍未校准。

## 实际验证与证据

builder生成与 `--check` 实际运行三个独立damage/frame/flight断言，并将三个正式实体同时纳入闭包验证，Compiler56 definitions/43 rules。新 `tests_v2/test_chapter01_attack_models.py` 是M8全套后的新增定向套件，不重写M8全套数字。

定向测试覆盖：源/产物一致、两个分伤时点及DEF顺序、换blocker不刷新、无blocker不乱打、首包HP致死、source退场取消剩余包、source/receiver资源时钟、两个ranged变体、单目标与排序、圆半径包含边界、air隔离、死亡/withdraw清理、发射前后source死亡、发射后移动、到期封顶、纯flight规则替换以及live属性。

checkpoint验证组合中和飞行中的恢复一致。ranged完整command replay一致；MultiMelee另使用真实自动blocking场景（player有合成block_count1/deployable，敌人有真实普通WALK route），t0 movement建立阻挡、t1开始cast、t13/t24接受145两包，中途checkpoint和完整replay均一致。没有把未记录World手动写入冒充可回放输入。

assertions.json锁实际program/runtime/implementation身份与模型SHA。所有profile仍 `client_pending`，manifest正式标志false；没有宣称Boss、教程、预定义单位、DISAPPEAR/APPEAR或整关已完成。

最终2026-10-02 fresh定向 **26 passed，9.73秒**；builder generate/--check均成功。Primary implementation digest仍为冻结 `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`。Multi模型实际runtime fingerprint `996cdfb729a171854626879646454071a6e55d8a2a9c6df4f6ebcdb0d7e58c54`，两个ranged模型为 `39c4ab3d7f71770b6b223b62710cc9538908e9f11b622582ad4dd00daefe00aa`；这些是新内容的规则身份，不用于重标旧长程结果。
