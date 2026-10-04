# 能天使 S3 与陈 S1：来源支持的 V2 攻击组合

`tools/build_attack_skill_recipes.py` 生成 `skills.angel.json` 与 `skills.chen.json`。
两包均为 `partially_implemented`、synthetic atk100、not_formal_mainline；
official_unit_config_imported=false、client_validated=false，没有正式转换审查收据。
这证明组合原语在隔离模型中执行，不能当固定十二人官方养成或主线通关证据。

```powershell
..\.venv\Scripts\python.exe tools/build_attack_skill_recipes.py
..\.venv\Scripts\python.exe tools/build_attack_skill_recipes.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.angel.json
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.chen.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_attack_skill_recipes.py -q
```

## 实际输入与校验

manifest.metadata.source_hashes 锁定 normalized 官方子集、roster.reference 原始冻结包、
operator_sources.lock、原 charpack CAB、effect_frames.json、离线范围 JSON 与本构建工具 SHA。
所选技能均为固定专三 levels[9]，官方 duration/prefab/range、非缺省 SP 参数、完整数值 BB 与本地冻结表对照。
旧抽取省略的零/null 字段只使用标准表实际值，不从文本补零。
技能 prefab 每个组件与冻结的 `(cabin,pathID)` 引用闭包完全一致才接受。

普通攻击直接用 UnityPy 只读 charpack 的 root→mode→attack/attackTrigger 链，
保留 pathID、scriptPathID 与完整字段；不会运行 V1。
OnAttack 动画事件来自有 SHA 的 `../data/tables/effect_frames.json`。
范围坐标来自 V1 目录中只读 `data_range_table.json`，原生 rangeId 来自标准 character phase；
这是离线数据参考，重新对照当前 range_table 尚 pending。

隔离单位使用 atk100、AS倍率1、敌 DEF10，真实物理 mitigation、HP资源和基本 lifecycle。
没有用真伤替代技能；目标 HP0 会真实死亡、产生 kill，后续选择器排除尸体。
原角色天赋、养成、部署/撤退和完整客户端动画/FSM尚未合并。

## 能天使 S3

标准所选 BB 为 attack@times=5、attack@atk_scale=1.1、base_attack_time=-0.11；
SP init20/cost30/time recovery1，持续15秒，AUTO。
native AttackAbility 的 modeIndex=1、allowSpRecoveryWhenAffecting=0。
mode1 真实 attack 有 projectile_angel、triggerDelta=0.050000000745、
waitAttackEventForAllAttacks=0、damageType=1；Spine Attack 的单个 OnAttack 为0.3秒，
来源帧表给出 projectileSpeed30。

使用通用 activation.on_start 在同一原子启动中同步设置 mode=1 和施加 Buff，
避免自动开启后同 tick 的攻击重复数仍读旧模式。普通/overload 为两个 declarative automatic_attack，
由资源 mode0/1 条件选择。Buff 只将 attack_interval 减0.11、attack_times 增4，
没有把技能伤害倍率伪装成裸 ATK 改动；burst 的 physical scale 明确为1.1。
repeat.rule 从有效 attack_times 取 count，合成外部 -2 modifier 的反例会真实变成3发，
不是写死五条 damage timeline。

技能使用自动满 SP 启动策略，不要求存在目标；无目标时仍消耗 SP、切换模式并暂停自然 SP，
不会产生虚假伤害或 attack.accepted。
当前 AUTO lowering 为 manual+auto_when_ready，用 manual cast 作为持续技能和 SP 冻结区间；
显式 auto_only=true 拒绝玩家或低级 API 强制命令，即使 SP 已满也不扣资源或改变模式，
自动系统仍可正常开启。

本模型 30Hz、未缩放1×动画时序：初始20SP，第十恢复周期在处理 tick299 时满30并自动开启；
已有攻击时钟下一次在300，首个五连发启动于300，launch309/311/313/315/317。
目标距1格，speed30，arrival310/312/314/316/318；每发 `100×1.1−10=100` 物理伤害。
五个目标命中只产生一个 attack.accepted cast 见证。
基础间隔1−0.11=0.89秒量化27 ticks；同一施放的后续发射间隔0.05秒量化2 ticks。
这个逐段 ceil 的模型策略保留在证据中，不冒充客户端分数时钟或动画缩放对照。

skill mode/Buff 在299+450=749 到期并恢复 ordinary 单发，保留已采样的 next_attack 时钟。
在 mode 删除事件中，cleanup 同时检查 source、target 与 buff 身份，避免别的单位同款 Buff 事件清错模式。
弹道/多发任务按 cast 时规划继续结算，native 不同模式交接和客户端同 tick 到期排序仍 pending。
each_hit 在存活范围内重选；前目标死亡后剩余弹道可转下一目标，本模型行为已有真实 kill/retarget 测试，
客户端多发目标细节与对空优先仍须独立对照。

## 陈 S1

标准所选 SP init0/cost4/INCREASE_WHEN_ATTACK，BB atk_scale3.2、stun1.5。
native 普通攻击 additionalTimes1、waitAttackEventForAllAttacks1，Spine Attack 有两次 OnAttack，
0.4333秒与1.0秒；合成普通间隔采用动画源 duration1.5秒，不套未校准的官方 AS/动画缩放。
每个普通双击 cast 只由一次 attack.accepted 恢复1SP，不按目标或两次 damage 加2SP。

S1 采用优先排列的 automatic_attack、真实4SP成本和 replace_attack 标记。
不能支付或没有合法目标时明确拒绝这个 cast，普通攻击可正常选择；
满 SP 时在下一次攻击时钟代替整个双击，不能由玩家手动强制开启。
S1 自身的 attack.accepted 不恢复 SP，因为 native allowSpRecoveryWhenAffecting=0；
事件 driver 的 normal ability 资格由内容条件显式声明，没有内核角色 ID 分支。

模型四个普通 cast 启动0/45/90/135，命中13/30、58/75、103/120、148/165 ticks。
恢复发生于13/58/103/148，SP变4；下一次 attack180 用 S1，196 命中一次物理
`100×3.2−DEF10=310`，SP归0，然后下一次 ordinary 恢复。

本地 current dump 的 DamageType.PHYSICAL=1、AbnormalFlag.STUNNED=0 已只读核对，
与技能/角色 prefab 中 damageType1 和 stun abnormalFlags[0] 对应。
S1 skill prefab 的 preDelay=0.532999992 与 Spine Skill OnAttack=0.4667 不同。
本原型使用实际 prefab preDelay，量化16 ticks；两种原始证据同时封存，
**没有把差异隐藏成已验证客户端命中帧**。FSM动画、escapeTime/后摇与官方间隔缩放还需采样。

伤害成功后向存活目标施加1.5秒 Buff.control：move/attack/abilities/block=false，interrupt=true。
这是 root 提供的通用控制契约，真实阻止移动、后续攻击和能力，并显式中断已有 cast。
196生效、241半开到期恢复；致死命中先结算 lifecycle，再禁止把 stun 施给尸体。
原生 stun 免疫、状态抵抗和特殊敌人条件尚未转换，所以不能将该 fixture 当全敌人控制兼容证明。

## 模型证据

19 项独立测试覆盖 build/source与Compiler、自动满 SP启动、满 SP玩家强制拒绝且原子状态不变、同步模式切换、
五物理弹道和一次攻击计数、动态重复反例、到期恢复、无目标、死亡重选、
普通双击仅一次SP、自动下一攻击替换、玩家强制命令拒绝、真实 stun 控制与恢复、取消已开始但未命中的敌方前摇、
无目标不支付、致死不 stun尸体、cleanup身份过滤，以及两包 checkpoint/input replay 精确一致。

两包需要由其他 agent 独立复核后才能被主任务用于下一层组合；模型测试不生成转换批准。
没有改 ark_sim 源码，没有新增角色专用 provider，没有修改其他 agent 文件。
## 后续光环复核揭示的结束边界

通用Buff的半开清理现先于phase0命令，而技能mode cleanup在effectphase的
ability.finished反应中完成。独立将能天使攻击时钟对齐到S3的endtick450后，
实际出现mode仍为1、连射Buff已经移除的单发burst。
该原生mode detach/末tick FSM顺序仍pending，不把中段五连射与当前属性恢复测试
提升为完整持续技能边界；完整官方单位整合必须增加对应反例并闭合该顺序。
