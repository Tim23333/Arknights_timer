# 攻击侧天赋与攻击时钟模型

本包为固定 E2 70、潜能 1、信赖 100、所选技能专三、无模组的六名干员提供实际可运行天赋模型。
源码为 `tools/build_campaign_attack_talents.py`，产物为 `packages/campaign/talents.attack.json`。
`complete_operator_count=0`、`client_validated=false`、`formal_mainline_approved=false` 保持明确。
以下运行验证不能将三十六关状态升级为正式通过。

## 证据与严格输入

官方属性/所选天赋/trait/技能来自既有 `operators.normalized.json`，其表源锁定
ArknightsAssets/ArknightsGamedata commit `56aee3d6c5a29c3a0d192456d70d14252cbb0804`。
所有 `selected_candidate.requiredPotentialRank` 必须为 0；配置的 E2/70/潜1/信赖100/专三/无模组逐项检查。
缺失或重复 blackboard、缺失 CAB、改变的关键动作顺序、属性公式、选择器和 Deck mask 均报错。

包内冻结六份实际 charpack 的 117 个 MonoBehaviour 字段、script/gameobject path ID 和 CAB SHA256，
不是只搜技能名称或凭描述生成算法。九个实际 BSON 模板直接读取
`../data/anon_textassets/buff_template_data.dat`，使用独立有界 BSON 解码辅助；每个模板保存
原 document 的偏移、base64、SHA256 和解析结果。类名仅作为证据数据，不导入或执行。
所有辅助工具、BSON、规范化表、旧已封技能包和 `dump.cs` 的身份均写入 source metadata。
公开2026-09-29表与本地原生资产的完整版本对应尚未证明，source version alignment 保持 pending。
V2 运行不会调用 V1；已有 range JSON 仅在离线构建时读入并封存为 selector offsets。

## 已实装机制

| 干员 | 原生依据 | 实际模型行为 |
| --- | --- | --- |
| 桃金娘 | `myrtle_t_1` empty Buff，attribute13/ADD，从 `hp_recovery_per_sec=25` 读取；validator 选择先锋。 | 持有者在场时维护全场活先锋成员；按每逻辑 tick 的 25/30 HP 积分，使用 regeneration 而非普通治疗攻击；持有者退场立即移除光环成员。积分时钟为明示模型，native continuous attribute 的客户端更新时点未校准。 |
| 风笛 | DeckBuffAbility `categoryMask=512`，`modify_sp[born]`；E2 SP6，潜1未使用 SP8。 | 风笛属于 roster 即为每个新生先锋加初始 SP6，不要求风笛驻场；source/target 是 newborn，DP 或不存在的 SP 不被伪造。 |
| 风笛 | `bpipe_t_1`: ON_CALCULATE_DAMAGE → IsBlackboardZero → Dice(prob .25) → AtkScaleUp(1.3) → SplashDamage(PHYSICAL, exclude primary)。 | 每个实际主伤害 packet 抽样；成功主包倍率乘1.3，并对原生范围内另一个活地面目标产生独立物理包。额外包携带 hook lock，避免递归掷骰；已接受主包才发额外伤害。三连击会抽三次，但 attack SP 按 cast 只计一次。 |
| 风笛 | trait cost1、`kill_to_add_cost` ON_TARGET_KILLED；character root `_withdrawCostRecoverRatio=1`、`_maxWithdrawCostRatioOfRawCost=1`。 | 实际 `combat.kill` 归因给击杀者后加 DP1；尸体不能重复产 DP。撤退返还 `min(paid_cost * 1, raw_cost * 1)`；高于原始费用的部署付款不会被误称为无条件全返。 |
| 陈 | `chen_t_1` 周期 interval4、SP1，ModifySp 的 ATTACK_OR_DAMAGE mask、force=false。 | 第一次等待4秒，然后每4秒给 attack/damage 型 SP 的活我方加1，尊重恢复冻结。类型 tag 从所选 SP 类型生成。 |
| 陈 | 第二天赋 ATK/DEF+.05；`evade_physical` 只过滤 PHYSICAL。 | 永久 ATK/DEF 各+5%；每个物理 incoming packet 抽 .1 闪避，术伤不消耗这一随机流。模型拒绝包不会触发 accepted-hit 回能。 |
| 雷蛇 | `liskam_t_1` 使用 `modify_sp[start]`；ability `_alwaysIncludeSelf=1`；RandomSelector selectNum1/excludeSelf1/appendSelf0；官方 x-5。 | 收到实际 accepted-hit packet 时自己 SP+1，并给随机一名相邻活友军 SP+1；排除自己及对角。无候选仍给自己，随机选择器不消耗样本。接受但 amount0 的模型包仍可回能；原生 block/免疫/回能事件顺序须客户端对照。 |
| 雷蛇 | 第二天赋 attribute3/ADD，BB magic_resistance10。 | 自身 RES+10，未混入潜能强化的数值。 |
| 能天使 | attribute7/ADD，BB attack_speed12；第二天赋 attribute0/1 SCALER，BB HP+.1/ATK+.06；native ability selfOption1/maxNum1。 | 有效 attack_speed_ratio +.12；自身 ATK+6%、最大HP+10%。部署回调随机选择一名活我方施加同祝福；空集合不耗 RNG。主人退场后友方 Buff 按来源移除。当前HP的 native maxHP变化重标定方式仍 pending。 |
| 艾雅法拉 | `amgoat_t_1` attribute1/SCALER，priority BB atk；选定14%。 | 在场时维护全场活术师 ATK+14%，包括自己，撤退清成员。多份同原生来源的最高优先级 override 尚未闭合，固定十二人只有一份艾雅法拉。 |
| 艾雅法拉 | `amgoat_t_2` ON_OWNER_LOCATE → RandomSetter(sp)，`_convertToInt=false` → ModifySp → FinishBuff，BB min7/max16。 | 部署模型从真实 imp 流取一次样本 `u`，SP增加 `7+9u`，范围 [7,16)。没有把显示文字“7~15”偷偷转换为整数抽样；native RandomSetter 算法与 born/locate 对齐仍待客户端验证。 |

随机流经过真正的 Kernel sampler；结果、消费次序、资源和事件可检查点恢复与回放。
默认模型随机算法不被宣称为原生客户端算法。

独立复核另暴露并修复两个实际边界。雷蛇可抽到没有 SP 的友方设备，原 grant 会抛错并回滚
敌人伤害；现在显式 `if_resource_present` 跳过该 grant，不造 SP，不重新抽选，自己仍回1。
另一反例中，hit 在 recipient manual cast 活跃时发出，cast finish 同 tick 先于排队的 Buff reaction；
原先读取 reaction 的 live state 错回 SP。Root 已令 Buff 事件捕获 emission 的恢复冻结状态，
本包测试要求自己和随机友方都保持 SP0，即使两者在 reaction 前刚结束施放，也不弱化期待。
动态 `amount_rule` 也有独立正/负反例：先解析实际变化再检查恢复冻结，正 SP 增量被抑制，
负变化仍执行。原先只检查 literal delta 会让动态规则在冻结中错误增加 SP，现由 Root 修复。

## 艾雅法拉 S3 自动模型与时钟证据

本轮替换了先前只能手动发包的 `ability/campaign_amgoat_probe_packet`：模型实际使用
`automatic_attack` 和 `auto_only`，按当前有效 interval 产生攻击，玩家不能强制发这一能力。
源基础 interval1.6、S3 flat -1.1 得到 .5秒；每次 cast 随机无放回选择当前活范围成员，
人数由当前有效 `max_targets` 读取，不把固定六个目标塞入模拟。使用 `at_cast` 避免 start 和 hit
各随机一次造成双重消费。这个从 `_selectNum=1` 到技能 `attack@max_target` 的连接仍是明示模型假设。

原生 mode1 `_waitForAttackEvent=1`、`_animKey` 空、preDelay/cooldown0，触发器仅提供
keepTarget0/minTarget1/searchTick-1。严格大端 Spine 读取发现 front 的 Skill_Start48帧、Loop36帧、End60帧
均无事件；back 只有 Attack/Default/Idle/Start，根本缺这些 S3 动画。
`switch_mode_restart_fsm` BSON 只提供 SwitchMode/restartFSM，没有恢复出攻击 signal 的发生时间。
因此本包将首个 signal 偏移0封为 `effective_interval_first_signal_zero_v1` 可替换 profile，
`native_first_signal_offset_verified=false`。没有伪造 Spine OnAttack，也没有把自动运行当成客户端时钟证明。

实际曾发现普通攻击 start0、S3 command10 后，旧 next_attack 让首个技能包等到48，且旧 normal hit23
仍发生。Root 的通用 `reset_attack_clock`/`cancel_pending_attacks` 同原子事务修正了这一模型不自洽：
本包 S3 激活显式启用这两个参数，现在技能包从10开始，未 launch 的旧 normal 不再命中；已经 launch
的 normal projectile 仍保留。两种分支分别有独立反例，客户端 exact cancellation 时点继续 pending。

普通攻击的 `_timeMode=0` 与 dump 的 FROM_ATTACK_SPEED enum、MIN_ANIM_SCALE=.1、各原生 maxAnimScale
用于声明 `from_attack_speed_divisor_model_v1`：
`authored_delay / max(.1, min(effective_AS_ratio, positive_native_maxAnimScale))`；非正 max 不设上限。
SPECIFIED=2 的模式保持指定时间。已有真实帧来自 source converter；缺帧不会用此 profile 补造。
原生 GetTimeScale 的方法体没有恢复，base interval addition 如何影响播放缩放仍未知，
因此 `client_clock_unverified` 和 `client_formula_verified=false` 保留。

## 编队消费接口

`manifest.metadata.unit_patches` 以真实 unit ID 为键，给出追加的 `buffs.initial`、`tags`、
`talent_abilities`、`deck` 与 `deployable` 字段。合并时应去重追加 initial Buff/ability/tag，
保留已存在的真实属性、HP、所选技能 SP/resource freeze 配置；本包的独立测试输入不替代编队资源。

`manifest.metadata.skill_definition_overrides` 是完整 definition rows，替换对应已选技能依赖：
Eyja 的 S3 activation/自动 packet/随机 selector、各普通攻击 windup，以及 Bpipe/Angel S3 restart 参数。
这些引用所需的新 rule/buff/selector 定义位于包的标准 sections，需一并加入真实依赖闭包。
SP类型 tags 应取自 patches，而不是凭角色ID在 kernel 中分支。
`source` 保存全部来源、`coverage` 列实际模型机制、`model_profiles` 给可替换算法、`pending` 保持缺口。

## 验证

独立套件 `tests_v2/test_attack_talents.py` 检查源与潜能配置、BSON bytes、属性独立端点、光环退场、
无驻场 Deck、SP mask和冻结、随机相邻/空/死候选、随机回滚、逐包 crit 与 splash 锁、击杀归因、
物理闪避 mask、自动时钟和动态成员、双模式 restart、已发射 projectile 保留、windup上限、
费用 cap、三连击只回一次 attack SP，以及检查点与回放。

构建和检查命令：

```powershell
..\.venv\Scripts\python.exe tools/build_campaign_attack_talents.py
..\.venv\Scripts\python.exe tools/build_campaign_attack_talents.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/talents.attack.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_attack_talents.py -q
```

当前套件包含33项；Builder/check 及 Compiler 校验成功，实际最终运行结果见本轮交付记录。
最终源码冻结身份和复核结果由本轮交付消息记录；后续 core 变化必须重跑回放身份。
`build(require_complete=True)` 始终明确拒绝完整 native 验收请求。

支援侧只读交叉复核另发现并复现了无效高优先级 fragile modifier 污染有效低优先级 hook 的问题：
应为100→120的包错误成为180。支援作者改为所选有效来源绑定倍率，原反例已实际回到120。
跨复核的旧全套18过/3失败包含核心改动期间的 checkpoint 身份拒绝、Suzu 初始SP推进后测试旧基线，
以及旧进程中的 emission 冻结反例；没有将旧身份结果重标通过。当前 fresh 进程的最高SP、
emission、sluggish/fragile、S3双倍率及混合allocations六项定向复核通过25.95秒，且支援 builder --check通过。
