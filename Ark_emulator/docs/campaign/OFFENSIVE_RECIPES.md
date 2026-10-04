# 风笛 S3 与艾雅法拉 S3：进攻组合的来源与边界

本批 `tools/build_offensive_skill_recipes.py` 生成 `skills.bpipe.json` 与 `skills.amgoat.json`，
仅组成 V2 属性/Buff、模式资源、空间选择、攻击与物理/法术结算，未修改内核。
两包均 `partially_implemented`、synthetic atk100、official_unit_complete=false、client_validated=false。
`build(..., require_complete=True)` 对真实未实现依赖明确拒绝，没有 formal approval receipt。

```powershell
..\.venv\Scripts\python.exe tools/build_offensive_skill_recipes.py
..\.venv\Scripts\python.exe tools/build_offensive_skill_recipes.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.bpipe.json
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.amgoat.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_offensive_skill_recipes.py -q
```

## 输入与确定语义

读取同 pin 的 normalized 专三技能行、roster 冻结 skill prefab/CAB 组件闭包，
UnityPy 只读 charpack 的实际 root→modes→attack/trigger/selector，effect_frames 的 OnAttack，
和离线范围 JSON。source_hashes 保存所有输入与所复用 attack-helper 和本 builder SHA。
范围当前版本、动画/FSM播放缩放和完整单位养成都列为 pending，不凭文本补事件时钟。

帧表的 t 是四位小数，而 f 保留原事件帧，例如0.4667会错误向上量化成15tick，真实源 f=14。
本原型按 `f / meta.tick`（源 tick30）构造1×动画时序；这不是客户端AS/动画缩放校准。

普通/技能均真实走 damage pipeline、health resource 和基本生命周期；无真伤替代。
风笛使用 physical，羊使用 canonical arts。此前未知 magical 字符串被旧 default pipeline误作物理，
已作为独立复核问题报告 root 并由 core 增加未知类型拒绝门；本内容使用明确的 arts。

## 风笛 S3

真实技能 SP init25/cost40/time increment1、持续20秒；BB atk1.2、def1.2、base_attack_time0.7、block_cnt1。
prefab BASE_ATTACK_TIME attributeType8 的 formulaItem=1 是 SCALER，故间隔为 base×(1+0.7)，
不是 flat+0.7；ATK/DEF同为+120%，阻挡为 ADDER+1。
native mode1 additionalTimes2、waitAttackEventForAllAttacks1、triggerDelta0、damageType1，
Spine Skill_2_Loop 三个 OnAttack 为 f14/17/20，不能把三个伤害都放在同一时刻。

合成基础 ATK100、DEF100、间隔1、阻挡1，技能后 ATK/DEF220、间隔1.7、阻挡2。
基础间隔2的独立反例应得到3.4，明确排除错误flat结果2.7。
敌DEF10时三次物伤各210；三个独立damage仍只有一个attack.accepted cast计数。
SP是按时间，普通/三击不授予攻击SP，manual active窗口冻结自然SP。
源 selector.targetMotion1 由 ground 标签资格表达；flying敌人不会被该近战fixture攻击。

ordinary/mode1 两个 automatic_attack由 mode0/1 切换，on_start同步施加真实增益，
到期恢复裸属性与普通单击。概率额外目标天赋、编队先锋初始SP、击杀DP/撤退返还尚未转换；
未用确定加伤或假SP把它们填满。

## 羊 S3：明确的发包探针

真实 SP init55/cost80/time increment1、持续15秒；ATK+130%、interval flat−1.1、attack@max_target6。
合成正常间隔1.6变0.5、ATK100变230，source mode1 damageType2 对应 arts。
原普通攻击 OnAttack f20，普通 projectile speed10；S3 projectile CAB 直接恢复 `_speed=6`，
并保存同前缀 logic/graphic/movement 原始组件与 CAB SHA，不仅从历史速度表猜数。
弧线/跟踪飞行和客户端撞击时刻仍 pending；fixture使用现有距离/速度投影。

native S3 attack.waitForAttackEvent1，但 animKey为空、源帧表没有 Skill_Loop攻击事件，
native随机 selector.selectNum1 与 BB6 的运行时绑定也未校准。
因此**没有造自动每0.5秒发包的FSM**，没有随机选敌实现，也没有伪造RNG消费。
只有显式 `ability/campaign_amgoat_probe_packet`，metadata.synthetic_attack_signal=true，
由可回放 activate_ability 命令注入尚未重建的原生包事件；仅 mode1允许。
`native_rng_fsm_unknown` 与 `skill_attack_signal_clock_unknown_explicit_command_probe_only` 保持 pending。

确定的多目标属性通过 `selector.limit_attribute=max_targets` 闭合：基础1、S3 Buff+5变6，
每包重取实际活着且在范围内的候选，deterministic scored probe选 min(有效上限,N)，没有固定六个ID。
2/4/7个候选的实际命中数为2/4/6；外部−3 modifier把有效上限改3，死亡/范围外目标排除。
同一多目标包只产生一次 attack.accepted，不按目标给SP，RNG状态保持完全不变，
这一不变恰好说明 probe不是原生随机实现。
MRes20时每包单目标230×0.8=184法伤，明确不同于错误物理220。

## 末tick模式交接：真实未闭合边界

core 半开 Buff维护先于 commands/自动攻击，但 mode资源归零仍在技能末端 effectphase。
若攻击时钟恰好到期tick就绪，可能采样到 mode1与已移除增益。
已实际探测而非掩盖：

- 风笛 external baseInterval20/(12×1.7) 对齐 end600，614/617/620仍有三发各90的无增益burst。
- 能天使 source满SP且external baseInterval1.11 对齐end450，460仍有一发100（times恢复1、倍率literal1.1）。
- 羊显式probe command@450在mode归零前接受，455只造成基础ATK100×0.8=80，而不是184。

这不是已验证的原生模式脱离/FSM顺序。两包均保存
`native_mode_detach_end_tick_fsm_pending`，完整转换继续拒绝；不修改已有中段增益和到期后恢复预期。
核心技能末tick效果必须保留，下一阶段真实单位模式整合再解决交接契约。

## 独立验证与跨复核

本套件覆盖来源build/Compiler/complete拒绝、真实SP周期、ratio与flat反例、三击独立帧/一次攻击计数、
ground/air过滤、属性/ordinary/SP恢复、未造羊skill时钟、实际动态目标上限、死亡与越界资格、
确定探针RNG不变、mode gate、无目标拒绝、末tick pending见证、checkpoint和输入回放。
完整单位、客户端验证与正式关卡推进仍由独立转换/复核门负责。

另发现并复现Aura到期输入at_cast读过期增益的问题：在expires30提交技能，旧处理把ATK10+5捕入snapshot，
敌HP985而非990。root修复phase0维护和direct ability start prune；本agent新
`tests_v2/test_aura_review.py` 保留原期望，并独立覆盖历史snapshot不失真、同中心双source、
parent/child独立移除、withdraw清理、effectphase位移和失败事务回滚。
