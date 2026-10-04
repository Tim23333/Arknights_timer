# 塞雷娅、铃兰、夜莺S3光环组合

三个包为 `skills.demkni.json`、`skills.lisa.json`、`skills.cgbird.json`，由
`tools/build_aura_skill_recipes.py` 离线构建；均为 **partially_implemented** 的合成属性模型。
完整单位配置、天赋、客户端动作对照和正式主线没有被提升，`require_complete=True`明确拒绝。

## 原始证据与最小接口

已读normalized所选专三、固定参考prefab/CAB闭包和实际角色charpack全部Mono组件，
保存精确pathID/scriptPathID、raw字段、官方选技、天赋、范围和文件SHA。
配置、SP类型/Cost/Init/increment/charge、duration/range/prefab/BB逐项对照，源变更会拒绝或check失败。
类标签只是提取器启发式，实际引用以CAB/pathID链核对。

三者实际Aura组件均声明 `_removeBuffWhenTargetLeave=1`、`_removeBuffWhenAbilityDetached=1`、
`_onlyAddBuffOnceForEachTarget=0`。据此向root提出并接入通用
`Buff.aura={selector,buff}`：parent持有每个child实例，成员实时进出、source死亡/退场、parent移除
均清理对应child。member为永久且independent，每个parent独立UID，不靠固定施放targets冒充持续范围。
常规移动及effect坐标移动都必须同步更新成员；checkpoint包含成员和周期任务。

范围来自纯离线 `ark_emulator/data_range_table.json`，没有导入历史运行时：
x-3共25格、y-8共23格、y-4共19格，完整grids保留。
当前native原始RangeTable位于 `../data/anon_textassets/range_table.dat`，与这个历史JSON的重新校准仍pending。

## 塞雷娅S3

SP80/初始70，自然回复1，持续30秒。charpack mode1的Heal
`_cooldown=1`、`_preDelay=0.5329999923706055`、`_isCont=0`；selector
`_limitTargetNum=0`、postFilter3、excludeOwner0。
模型以动态each_hit selector每次重新选择范围内所有受伤存活友军，合成ATK100每次治疗35；
首命中量化为16tick，随后每30tick一次，共30次，最后在29.533模型秒，源退场取消剩余任务。

敌方live member应用source BB的moveSpeed -60%和arts_factor1.55；进入、离开及退场清理均实际验证。
来袭effect显式绑定纯damage.pipeline graph，它委托V2标准管线，再只对arts乘有效arts_factor：
合成原始100伤害变155，physical/true仍100。没有为其他伤害类型套法术增幅。
这个graph尚须显式接入来袭效果，不能认为仅存了arts_factor就自动修改所有默认攻击。
治疗授予SP天赋、驻场20秒叠层和多光环同类规则仍pending。

## 铃兰S3

SP70/初始50，自然回复1，持续35秒并停止攻击。
实际mode2不是普通Heal，而是范围BuffAbility：`atk_to_hp_recovery`、interval1、waitFirst1、
ratio0.2，leave/detach移除，target validator明确ignoreHealFree=1。
采用root新增的 `regenerate`：使用可替换healing.base求有效source ATK比例，
但只发regeneration.accepted，**不发healing.accepted**，避免冒充医疗触发治疗SP天赋。
成员中途进入从自己的第一周期开始，离开取消未发生周期，再进入重新建立timer。
独立测试修改有效ATK100→150后，下一周期回复从20变30，不使用写死的20。

模型明确采用member firstwait1和parent半开[0,35)边界：初始成员回复tick1..34秒共34次，
atk100总680；第35秒先detach，不再产生终点周期。
这只是当前可追溯模型政策，不宣称native连续回复或终点同刻排序已经校准。
原生Sluggish[inf]由Buff DB加载，脆弱天赋0.03秒扫描及scale_delta_to_one的完整模板算法
尚未重建；没有从名称猜减速比例或默认把最高脆弱当多来源叠乘。辅助SP光环也pending。

## 夜莺S3

SP120/初始115，自然回复1，持续60秒。
技能Aura raw member是magic-resistance的MULTIPLIER和evade_magic模板，self passive Buff增加ATK。
已闭合自身ATK+80%、范围友军RES+150%的live成员管理；合成ATK100→180、RES10→25，
对应标准arts100伤害结算为75。成员出入和caster撤退后属性恢复均有实际模型断言。

**25%法闪没有伪造为已实现。** RNG与受击拒绝仍pending，模型本批只验证RES部分。
mode1引用Attack_C、三治疗目标selector，但缓存effect_frames只有通用Attack，不能证明Attack_A/C别名。
root尝试读取本地Spine时发现当前解析器的非法大数/负时间，未封存或据此猜帧。
因此本包不安排一个假t0/0.9治疗包；三目标治疗cadence、基础RES天赋和鸟笼仍pending。

## 验证与修复记录

18项独立场景包含来源/check、complete拒绝、SP付款、实时治疗、arts限定、出入/退场、
回复事件区分、有效源ATK、双caster成员隔离、半开边界、三个包的精确checkpoint/input replay。
首次实跑13过5失败：effect move发生在常规movement之后，旧Aura到下一tick才更新，导致
同tick离开后slow/RES残留、再次进入的第一回复晚一tick。
root将MovementSystem.displace置于atomic中并同步reconcile后，保持原独立预期，
**18/18通过，28.91秒**。这提升的是对应原型模型检查，不是正式关卡或客户端证据。

未闭合项还包括技能interrupt到native能力detach的具体时序、全单位官方配置与原生动作缩放。
parent移除、死亡和撤退已经测试；不能把这些通过推导为任意技能中断清理也已验证。

## 冻结后的交叉复核

本线冻结后再次执行build --check成功，三个来源/build一致性用例定向3/3通过（1.06秒）。
并行集成曾在本线补充demkni incoming绑定缺口、重建manifest时取到旧fixture与新builder，
发生一次manifest比较失败；保持原严格比较预期，冻结后没有漂移。

随后只读交叉审阅offensive线 `build_offensive_skill_recipes.py`、风笛/艾雅法拉两个包及测试。
build --check成功，15项模型/恢复/replay测试独立运行全过（23.52秒），在声明partial范围无阻断。
风笛原始SCALER+.7按基础间隔乘1.7处理，未错用flat+.7，三段根据Spine原始frame位置分离，
仅命中ground；动画倍率、模式切换时next_attack重基、随机天赋/初始SP/击杀DP仍pending。
艾雅法拉没有从空animKey/未知SkillAttack FSM编造自动时钟：只有显式命令probe，
使用动态有效max_targets限制当前存活范围内目标，RNG snapshot不变化，并明确not_native_fsm_or_rng。
真实随机选择、selectNum1到BB上限6的原生映射、技能攻击信号、弧线追踪和部署随机SP仍pending，
complete请求拒绝。没有用15项通过或这个deterministic probe宣称原生随机技能完整实现。

```powershell
..\.venv\Scripts\python.exe tools/build_aura_skill_recipes.py
..\.venv\Scripts\python.exe tools/build_aura_skill_recipes.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.demkni.json
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.lisa.json
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.cgbird.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_aura_skill_recipes.py -q
```
