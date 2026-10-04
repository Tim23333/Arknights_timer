# 雷蛇与白面鸮支持技能原型

本批交付 `skills.liskam.json`、`skills.plosis.json`，由
`tools/build_support_skill_recipes.py` 离线构建。两包状态均为 **partially_implemented**，
使用明确的合成属性；不是完整官方干员，不是正式主线内容，没有转换批准收据。
权威所选技能、天赋来自 operators.normalized.json，技能prefab对照冻结CAB依赖闭包，
角色charpack由UnityPy读取全部Mono组件并保留pathID/scriptPathID与来源哈希。

## 雷蛇S1

真实专三 `skchr_liskam_1` 为AUTO、受击回复SP、SP18/初始0、maxChargeTime1，
blackboard DEF+1、duration8。技能prefab含两个Buff：DEF的MULTIPLIER修饰器，
以及 `damage_block_once`；两者lifeTimeType均为1，阻挡资源随8秒结束清理。
`_allowSpRecoveryWhenAffecting=0` 支持施放期SP冻结；`_waitForAttackEvent=1`
的具体客户端启动动作帧仍pending，不能把本模型瞬时激活当作已校准动画。

已组合的真实V2部分：

- `damage.accepted` target事件每次授予1SP，达到18后自动启动并支付18。
- `auto_only=true` 在满18SP时仍拒绝玩家强制启动，只有系统自动启动可支付，避免用SP不足假装AUTO边界正确。
- 通用 `activation.on_start` 在支付后同步原子施加DEF Buff和一枚shield_charge，
  避免时间线排队导致同tick来袭先穿盾。
- DEF Buff持续8秒，将合成DEF100变为200；阻挡资源为非health的独立一枚charge。
- 来袭damage effect显式绑定纯damage.pipeline计算图：有charge时分配消耗charge，HP损失为0；
  无charge时委托原生V2 `rule/ark_damage_pipeline`，没有另猜物理/法术/真伤公式。
- 8秒末清除未使用charge并恢复DEF，模型施放中目标驱动SP冻结，结束后重新受击回复。

独立测试实际查出并推动root修复“所有allocations资源都计入HP伤害”的问题：
现在charge消耗不计damage.accepted.amount或battle.damage_dealt；资源分配仍被提交。
fixture中第一击消耗一枚charge但HP与伤害计数均不变，第二击按DEF200受7.5物理最低伤害。

当前限制：fixture的来袭effect必须显式绑定该guard pipeline，不能认为给单位命名为雷蛇就
自动拦截所有默认攻击。随机邻友/自身SP天赋、被挡攻击是否触发SP的原生语义、完整普攻和
官方养成尚未并入。`require_complete=True` 明确拒绝。

## 白面鸮S2首治疗包框架

真实专三 `skchr_plosis_2` 为MANUAL、SP100/初始85、duration40、range y-7，
blackboard BASE_ATTACK_TIME=-2.1。技能prefab为switch_mode_restart_fsm，攻击属性8加值；
charpack root `5905979480863349313` 的mode1指向 `7437552239043549761`，该模式治疗组件
`1664878042392173121` 的preDelay为0.20000000298023224。它引用selector
`-6848490883347113407`：maxNum3、postFilter3、excludeOwner0。

当前只执行原生mode1首治疗packet框架：支付100SP、40秒技能占用/暂停SP、扩大到y-7，
首packet最多治疗三个受伤存活友方单位，合成ATK100每人恢复100。
当前V2量化对原始float预延迟取上界，得到7tick；这是模型量化结果，客户端动作帧仍待对照。
第四友军不会得到第四份治疗，死亡友军被排除。

**没有用固定0.75秒治疗序列冒充渐变过程。** 技能/charpack已读取字段中没有发现渐变曲线的
序列化时间参数；BASE_ATTACK_TIME=-2.1只能证明所选增量，不能证明整个逐渐过程。
后续攻击cadence、mode切换/复原、动画事件与SkillAttackTimeCurve类的行为仍待源证据。
包中的first_packet_only=true和pending_mechanics明确标记，完整请求拒绝。

天赋SP光环原文与0.3数值已保留，但没有写成静态recovery_rate=1.3后宣称实现全场光环。
成员进出、退场清理、自然回复类型限定、同类取最高、技能冻结和与铃兰职业光环交互
还需要通用aura/资源速率领域逻辑与独立场景。

## 检查

构建与两个V2内容包validate成功，支持测试现为10项，覆盖构建一致性、完整请求拒绝、
18次受击自动付款、单盾非HP伤害、同tick启动防穿透、8秒恢复、三治疗首包、
拒绝常数替代未实现渐变、死亡筛选和雷蛇checkpoint/input replay精确相等；新增满SP玩家拒绝/系统自动启动边界。
收尾与activation独立review15项和root controls6项在同一当前核心下重跑，31项全过，5.75秒。

```powershell
..\.venv\Scripts\python.exe tools/build_support_skill_recipes.py
..\.venv\Scripts\python.exe tools/build_support_skill_recipes.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.liskam.json
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.plosis.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_support_skill_recipes.py -q
```

这些是组合原型的模型证据，不提升固定十二人完整可运行、主线胜利或客户端准确性状态。
