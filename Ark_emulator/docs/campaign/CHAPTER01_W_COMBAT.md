# W 两模式普攻与HP/C4组合：可替换内容模型

本批新生成 `tools/build_chapter01_w_combat.py` 与 `packages/campaign/chapter01_models/w_combat/`，没有覆盖旧 `chapter01_models/w/` 或旧源/断言。模型具有可执行普通攻击、半血模式切换与C4互锁，状态仍为 **partial W composed model**。完整Boss、原生FSM与整关均未完成；formal36状态不变。

## 真实来源与尚未证明的连接

两关使用同一冻结审计条目 `enemy_1504_cqbw`。原始audit SHA为 `a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd`，生成器拒绝其漂移，逐一校验原生CAB/DB/声明文件SHA。新source包保存敌DB、完整prefab子树、MonoScript、两mode、Spine原字节/parsed、BSON、projectile全组件及原生声明；声明里的方法stub不是恢复的方法体。

| 源字段 | 已恢复值 | 本批转换 |
|---|---|---|
| native mode0 normal combat | RangedAttack pathID2133109785975003083 | mode=0的automatic_attack |
| native mode1 normal combat | RangedAttack pathID5588662921156499403 | mode=1的automatic_attack |
| 普攻数值 | ATK470、physical1、scale1、interval4、ASPD100、radius2.5 | 无额外阶段ATK倍率 |
| Attack动画 | authored duration39帧；OnAttack9/23帧 | 按显式packet profile选择信号 |
| 普攻RangedAttack | waitForAttackEvent1、timeMode0、waitForProjectileInvalid0、useCachedAtkOnly0 | 模型帧时间；发射后不等弹道才结束普攻cast |
| selector | 每mode子树唯一AdvancedSelector，side2/motion1/postFilter4/max1；真实SelectorTrigger PPtr | 一名活的地面player；stable排序是模型选择 |
| 普攻projectile | projectile_enemy_cqbw；Paracurve speed5 | 发射时平面距离/5 |
| SimpleProjectile | lifetime10、maxHitNum1、stopAfterMaxHit1、stopWhenSourceInvalid0、alwaysHitTraceTargetInTheEnd1 | 单包命中；flight上限10秒；已发射包来源退场仍保留 |

普通combat的 `_selector` 实际是null。mode子树包含关系与attackTrigger PPtr精确保存；它們不能证明隐式selector继承、postFilter4的真实排序、仇恨/伪装/异常过滤算法。Spine事件从保存的原始base64重新经受控私有BE读器解析，与冻结parsed逐字段一致；库读器身份前后相等，没有修改共享库或旧helper。

## 两个明确packet profile

`model.json` 选择 `two_full_packets_model`：9/23每个信号各发一包scale1物理伤害。**两个OnAttack只证明两个信号，不能证明原生恰好两发弹道或两次完整攻击值。** 此选择是显式可替换模型，保留原生signal-to-packet/GetTimeScale/FSM待校准。

`first_signal.model.json` 使用 `first_signal_only_model`：仅frame9发包。独立运行证明30tick只有一次launch与一次370伤害，不是仅存在一份未运行的替换配置。未支持的profile名称严格拒绝，不接受“native_two_shots_proven”等无证据声明。

二者都将capture固定在cast目标ID，impact读取当前源ATK与目标DEF。飞行时长采用 `min(launch_distance / speed5, 10)`，未根据目标后续运动重算。目标退场后不命中、不换成另一候选；来源死亡/撤退时保留已launch的包，取消尚未launch的任务。真正曲线、追踪、碰撞、过期和hit/reached回调仍是model_gap；选敌排序和计时仍client_pending。

## 与原HP/C4模型组合

新的作者工具只离线调用冻结旧HP/C4作者函数，保留原半血检查与C4输入。HP<=5000进入可逆mode1，HP>5000恢复mode0；ATK仍470。每种普通攻击有独立mode条件，阶段切换取消未launch普攻并重置时钟。旧模型包含source-backed值和显式回调/时序假设，本批没有把它升级为native确定算法。

C4增加内容层模型互锁 `cancel_pending_attacks=true` / `reset_attack_clock=true`。C4开始取消旧cast未launch信号，已经发出的弹道继续；C4 cast的blocks_attacks保持到固定3.8秒效果结束。结束后恢复普通攻击。C4模型仍是固定延迟area：没有恢复真正AttachToTarget、invalid callback或原生能力finish语义。它与普通弹道无效目标策略必须区分，不能把普通target-invalid测试当作C4真实附着取消证明。

默认C4模型时钟含tick0恢复：首次start269、下一次869，间距600tick=20秒；area impact为start+114。mode1入场立即准备C4，phase entry/exit的原生驱动回调顺序尚未证明。本批可以组合普攻与这些明确假设，不称fullBoss。

## 实际运行与独立预期

全部probe使用显式运行根：

`D:/Arknights/Arknights_timer/unpack_work/campaign_m10_cast_freeze_candidate`

实际导入 `.../ark_sim/__init__.py`，身份 `f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e`。启动检查真实module path和digest，完成再检查digest；不得混入正在提升的primary或将历史f8証據覆盖为新身份。

`assertions.json` 七项短模型场景实际执行：

- 两个phase分别frame9/23 launch，距离1/速度5在tick15/29命中，各470−100=370；下一cycle cast120、launch129、impact135。阶段1fixture使用真实半血状态，避免初始HP10000触发恢复模式。
- 同范围两个player只命中捕获的第一身份，HP分别4260/5000。
- t10记录withdraw来源或目标：仅一发已经launch弹道；来源撤退后目标HP4630，目标撤退后不受伤。命令回放完整snapshot一致。
- t10开始C4：取消未来signal23，旧signal9仍在15命中；C4在124造成746伤害，普通攻击恢复后134 launch/140 impact，最终HP3514。CP恢复及完整commands replay一致。
- 通过记录的fixture技能command把HP设置为5000/5001，实际观察normal0→normal1→normal0；完整commands replay一致。这是场景输入模型，不是恢复了真实玩家伤害事件。

`tools/experiments/chapter01_w/test_w_combat.py` 为本批新独立套件，不属于冻结M8全套。它在fresh subprocess锁定f6bb，检查六类反例：未知profile拒绝、首信号单包、DEF250时每包220且两mode一致、range3排除/air排除/目标失效不retarget、C4实际269/869周期及停攻区间、HP归零引发实际entity.died并遵守已launch保留/无效目标丢弃。测试保持独立期待，不从actual反推数值。

最终同源码版本 `generate` 与 `--check` 均实际通过；上述独立套件最终 **6 passed in 20.38s**，没有失败或skip。结构化结果另存 `test.report.json`，它仅记录模型测试结果，不是审批收据。

完整CP比较与commands replay覆盖实际recorded输入和全部state/tasks/events/RNG。数据读取不插入会污染命令回放的额外calculation.trace。没有运行整关长程。

## 导入约束与gap矩阵

新package沿用 `unit/chapter01_w`，包含唯一mode0与mode1 normal ability；替换旧W定义时应整体组合新entity/abilities/selectors/rules/buffs。禁止同时追加旧normal或其他enemy通用攻击，避免双重攻击时钟；保留关卡instance属性与routes来源。源包的 `gap_matrix` 区分resolved字段、声明模型、client_pending与model_gap。

| 机制 | 状态 |
|---|---|
| 原始两mode/RangedAttack/帧/DB/弹道字段 | resolved source |
| 声明的普攻damage/flight/clock/目标隔离/退场 | executable model，独立验证 |
| HP模式与C4timer/area组合 | executable inherited model，独立验证 |
| signal→packet数、GetTimeScale、FSM顺序、隐式selector | client_pending |
| Paracurve真实body/碰撞/追踪/过期 | model_gap |
| C4真实AttachToTarget及invalid callback | model_gap |
| fullBoss / 1-11、1-12完整执行 / formal36 | 未完成、未执行、无审批 |

生成命令：`..\.venv\Scripts\python.exe tools\build_chapter01_w_combat.py`；一致性检查加 `--check`。可用 `--runtime-root` 和 `--expected-digest` 明确指定其它独立运行身份，不能隐式切到primary。

## 冻结文件SHA256

| 文件 | SHA256 |
|---|---|
| builder | `7d3c48209c0520a84186a1823a198a15b9b3de39cc94aee39f1535c89bd710ff` |
| new independent tests | `2cb74142d634df70808a2f0d543613fda8a7b8ff273826f1b219e5cb5baa0207` |
| native.reference.json | `e182463277369f7ddd9a377e038ef30476a3d96c24daf4ee977bfe50c8b0fe5c` |
| model.json | `4b647811d8808130970ac85b8a068b4623feb2e1e4fa68dca61d87cccea0df9a` |
| first_signal.model.json | `43fbc5e22aca3230e0d5cbff1d13862239620d4238a30d3c57b0fa65b8873896` |
| assertions.json | `a4b8a040c51daeb395a7e9f868f1da1c68cf46e819634f18f53a3871355bf658` |
| probe.json | `e723ee3f3bc25f99a1c391b5b903cbad7d305306960ed3c574d60eb6b19fe5d5` |

没有改核心/candidate、旧W包、源pin、reader/helper；没有提交推送。
