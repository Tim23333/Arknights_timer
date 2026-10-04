# skulsr 原生阈值冲突与可实现状态接口

先完成本地source闭包调查，再实施独立partial内容。原chapter02 first7/projectiles7、M26、primary和M27不改。

当前dump `Il2CppDumper_current/dump.cs` 的HpRatioToggleChecker具有serialized `_minHpRatio/_maxHpRatio`、运行 `m_minHpRatio/m_maxHpRatio`，并具有Hotfix_LoadData/OnTick/_CheckCondition。LoadData原生RVA0xEDE040/Offset0xEDC840，_CheckCondition RVA0xEDE220；这些是函数位置和空签名，不能推出算法。

`probe_skulsr_managed_bodies.ps1` 用System.Reflection.Metadata/PEReader读取两份DummyDll，未加载或执行游戏程序集。DummyDll与Cpp2IL_DummyDll里的LoadData/OnTick实际IL均为单byte `2A`（ret）；_CheckCondition是ldloca/initobj bool/ldloc/ret的默认值桩。两者不能恢复阈值判断或Blackboard覆盖。工具build/Check和DLL hash留存于skulsr.managed_bodies.reference.json。

独立 `audit_skulsr_native_sources.py` 重读enemy与projectile Unity Typetree和BSON原文，锁两dump、两DLL、源包及原资产。当前workspace无GameAssembly/libil2cpp/global-metadata匹配，扫描范围和命令保留；684份release20260831 base/hot Lua原文哈希封存，没有HpRatioToggleChecker/skulsr_t_1/atkup.hp_ratio三个确切key命中。此结果只覆盖所枚举本地数据，不证明其他安装盘或加密/压缩代码不存在。

实际serialized checker `_maxHpRatio=0.4000000059604645`，DB `atkup.hp_ratio=0.5`；`_loadMinHpRatioFromBlackboard=0`仅明确min开关，不能证明max是否始终加载BB。source版本对应和LoadData body不足，阈值冲突当前**无法解决**。后续partial必须要求显式threshold_policy：serialized或DB都是声明模型，不给默认，不标native accurate；require_native/full closure仍拒绝。

确定的源字段：

- 双UnitMode：每个COMBAT源MeleeAttack OnAttack f53；ATTACK源RangedAttack OnAttack f14/f17、raw atkScale0.25999999046325684、projectile_skulsr。
- ToggleablePassiveBuffAbility的ATK multiplier从BB0.5加载，BSON switch_mode_restart_fsm ON_START mode1、ON_FINISH restoreDefault、两端restartFSM=true。恢复延迟0与toggleOnce0保留，但原生OnTick/同帧优先/哪些cast重启的body未取得。
- PassiveAttachmentAbility `_targetFamilyMask=1`，当前enum ATTACK1/COMBAT2；DEF multiplier-.5、fixed5s。Ability.Options.familyGroup由Wrapper传入，UnitMode._attack映射ATTACK/_combat映射COMBAT是明确声明adapter，不能称已经恢复原生Wrapper赋值算法。
- SimpleProjectile `_hitNumType=2`。当前LifeType enum INFINITY2、LIMITED1；因此 `_maxHitNum=1`是inactive字段，不得解释为有限1。寿命仍LIMITED10秒，source-invalid不取消，同target不可重复，sourceHitBehaviour范围Box3×3、onlyCheckHitWhenReachTarget1保留。

M28只扩通用 `max_hits:null` 无限总hit cap；缺字段/负数/bool/string仍failfast，有限整数旧语义不变。null不解除life、same-target policy或stop-after-first；stop_after_max+null明确不因cap结束，仍受reach/invalid/life规则约束。没有官方ID分支或大数sentinel。

新partial内容以显式资源mode0/1、可替换条件表达式/参数及source Buff定义拼装双packet/近战接口。第一次只用公开manual/probe指令选择可证明时钟/模式，原生自动路由、阈值加载、Projectile Box原生物理仍硬gap。ATK采样/重启优先/在途packet保留策略均写明profile；执行正确仅证明声明profile，不降低实际游戏准确性要求。

Aoemag source两Box和父链已封。当前dump的MapToWorldPosition/WorldToMapPosition/WorldToGridPosition及GridMap/PhysicsRange仍空签名；没有实际Map→World函数body或paired-client锚点，不能把prefab root(4,3,0)当地图坐标转换证明，不实现猜测box投影。
