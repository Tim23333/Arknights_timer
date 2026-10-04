# 1-11 原生预定义安德切尔：独立创建与普攻模型

本批交付 `tools/build_chapter01_predefines.py` 与 `packages/campaign/chapter01_predefines/`。它们恢复原生配置、生成可供组合器导入的独立NPC定义，并运行六项短Engine验证。状态为 **partial NPC create/normal attack model**；没有执行整关，不是完整干员实现，也不产生关卡审批。

## 配置与属性来源

`chapter01_sources/native.reference.json` 的 `stages.level_main_01-11.native_level_document.predefines.characterInsts[0]` 原样锁定为 `char_211_adnach`，`PHASE_0`、level20、favorPoint0、potentialRank0、skillIndex0、mainSkillLvl1。位置 row3/col6、方向RIGHT、hidden=true、alias=null及所有覆盖字段原样保存。生成器拒绝配置漂移、未转换的天赋或技能BB覆盖。

规范表来自既有公开源锁定 `56aee3d6c5a29c3a0d192456d70d14252cbb0804` 的 character/skill tables；完整锁含URL、SHA、缓存身份。生成器实际比较本次读取的角色与技能条目和冻结的Chapter01审计条目，禁止混用固定E270阵容。

| 属性 | 原生level1 | 原生level40 | E0 level20显式模型 |
|---|---:|---:|---:|
| HP | 531 | 831 | 677 |
| ATK | 150 | 251 | 199 |
| DEF | 55 | 93 | 74 |
| RES | 0 | 0 | 0 |
| cost / block | 9 / 1 | 9 / 1 | 9 / 1 |
| interval / ASPD | 1 / 100 | 1 / 100 | 1 / 100 |

使用精确有理数线性插值，alpha=19/39：HP=8803/13、ATK=7769/39、DEF=2867/39。favorPoint0直接对应原生favor关键帧level0，全零加成，未借用信赖百分比换算。整数属性按half-away-from-zero取整；这项中间等级取整是可替换模型，尚未客户端校准。源端点、favor端点与原始有理数均另存。移速1、重量0、再部署70及原生布尔免疫字段也保存；模型仅映射运行所需属性。

两个天赋候选均要求PHASE_1（level1/55，ASPD4/8等），在本NPC配置下均不解锁。charpack确实仍有 `Talent` 和 `PassiveBuffAbility`，后者包含 `adnach_t_1`、`templateKey=empty`、`loadFromDB=0`、`loadFromBlackboard=1` 的ASPD修改器。**Prefab组件存在不能覆盖规范表解锁条件**，故模型不施加这些属性。完整原始组件保存在源包；本配置无解锁的BSON天赋需要运行。既有审计 `predefined_skill_prefabs` 为空，源包如实保留为空，不伪造已恢复模板。所选 `skcom_atk_up[1]` 等级1的完整BB/SP/持续时间保存，SP50/init0，但技能执行未转换。

## 普攻绑定与运行选择

charpack default mode pathID `-3630041306819117224` 指向 `RangedAttack -1077909929435578536`，非combat替代。真实字段 `_damageType=1`、`_atkScale=1`、`_waitForAttackEvent=1`、`_timeMode=0`、`_animKey=Attack`、`_projectileKey=projectile_crossbow`、`_useCachedAtkOnly=0` 原样保存。Trigger是SelectorTrigger，`_keepTarget=0`、`_minTargetNum=1`、`_overrideSearchTargetTick=-1`。没有据此宣称已证明隐式选敌优先级或空中筛选。

新鲜离线绑定chararts前后两面均为Attack，duration30帧，OnAttack9帧。原始float32时间0.30000001192092896仍保存，只有严格float32再编码相等才确认authored frame9。生成器确认新鲜charpack SHA与冻结prefab SHA一致，并锁定模板/MonoScript源和读器SHA。私有BE解析器不会修改共享Spine库；库身份在提取前后相等。

弩箭真实prefab为SimpleProjectile，AdvancedMovement speed10、moveType1；其生命周期5、maxHitNum1、stopWhenSourceInvalid0和其他原始字段完整保存。运行profile声明用发射时平面距离/speed10，捕获目标ID，在impact读取HP/DEF；未实现原生曲线、跟踪重采样、碰撞或过期回调。

rangeId `3-1` 的原生十个格子直接由离线JSON读取，明确转换 `V2 row=-native row, col=native col`，再由通用grid_offsets按朝向旋转。模型选择一名范围内存活敌人，不加未经证明的隐式优先级；目标退场后丢弃伤害包。

## 实际验证与身份

最终源码实际执行 generate / `--check` 均通过；末次命令合计5.21s（不作为性能保证）。六项独立预期：

- 初始677HP；t9发射，相距1格/速度10，t12命中。199ATK对30DEF造成169伤害，1000HP目标剩831。
- 100ATK对NPC74DEF造成26伤害，NPC剩651HP。
- 右向中心前3格命中；前3格旁一行、身后一格均不命中；左向身后一格命中。
- 发射后退场的捕获目标不产生damage.accepted。
- impact前检查点恢复后，完整checkpoint与连续执行相同。

每组是实际Compiler/Engine执行，人工构建固定敌人与普通伤害/退场用于短probe，**没有声称人工ctx操作属于command replay**。证明身份为primary `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`；assertions保存program/runtime fingerprint及implementation digest，before/after不一致即拒绝写入。primary提升后，不能把新身份结果覆盖为旧f8证明；`--check` 会因断言身份漂移严格失败，届时应在新路径保存新批次证据。

## 阶段组合接口与明确缺口

导入 `npc.model.json` 的entity `unit/ch1_predefined_adnach_e0_l20`、唯一normal ability及selector即可独立创建该NPC。当前定义不含自动创建、部署卡收费或脚本激活；禁止同时追加第二个normal ability。属性cost9是原生属性，不能因为展示它就认定已实现预定义/卡牌费用政策。

源包保留完整native stage document（地图、routes、runes、options、predefines等）、全部控制/故事与**12张原生characterCards**。这十二卡不是用户固定十二人配置；后续组合器必须显式决定native-card与fixed12-deck覆盖政策，并保存两份来源。模型没有替换这些卡，也没有将原生NPC视为第13张部署卡。

ACTIVATE_PREDEFINED精确源位于wave0/fragment1/action_index2，preDelay2.99、key=char_211_adnach、routeIndex3、managed=true、dontBlockWave=false、blockFragment=false。`hidden=true` 的原生开场语义和routeIndex3的激活关系尚未恢复，不映射为route_hidden、不以猜测绝对时间自动create。STORY、PREVIEW_CURSOR、DISPLAY等源控制仍完整保留；2.99不是本批证明的可执行激活deadline。

客户端未证项包括中间属性取整、GetTimeScale/自动普攻FSM、隐式motion/priority/immunity、弩箭真实impact/生命周期/跟踪、选技、原生隐藏激活、fixed12组合和源版本对齐。这个可执行子集不能提升formal36状态。

## 冻结SHA256

| 文件 | SHA256 |
|---|---|
| build_chapter01_predefines.py | `3233b03e1c52fe98233569de8b14371d6084e645cfa4b9b746811001b14de5bd` |
| native.reference.json | `15eb6edf057af42e1c03acf441cc44852f1a3b4aefd511dd23428fcead1413e6` |
| npc.model.json | `4eb40df9ef979f54f289c099b78723da61fc49d00fc88fcdafb1ace3c77b779e` |
| assertions.json | `6a9f8fcffd922a98bbafc6dc18428b7dbc58ba7a044c903eb2bff3f53d70c4bd` |

Builder/model/source/证据已冻结；未改任何primary/candidate核心、旧helper或旧数据包，未提交推送。
