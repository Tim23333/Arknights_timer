# 0-10正式模型转换合同草案与来源审计

本草案为根任务独立复核准备材料，没有签收据或批准正式关卡。固定12人、E2 70、潜1、信赖100、选技专三、无模组及标准36关目标不变。M12模型源为bd60核心与0fb输入；旧C0_FIRST_MODEL_ACCEPTANCE_MATRIX.md保持历史，不重写其失败或旧证据身份。

## 产物与执行边界

- `tools/build_first_model_conversion.py`：受控离线构建与逐字段消费断言。
- `packages/mainline/main_00-10.json`：符合catalog/progress planned_content路径的conversion draft。
- `scenarios/mainline/main_00-10/commands.json`：planned_commands路径；复制已冻结12条命令、6人实际部署脚本，12人deck保持完整。源commands SHA4fe0c2f15121454bd7cef24d43c2eb148eabb07902f796671d51ae98382c2374。
- `packages/campaign/conversion_drafts/main_00-10.audit.json`：2796条来源记录、真实字节锁、12个配置/定义引用闭包、机制证据及当前full-suite节点映射。
- `packages/campaign/conversion_drafts/conversion_contract.schema.json`与`tools/validate_first_model_conversion.py`：明确草案字段/状态及离线schema子集验证，不依赖网络或安装新库。

草案只新增manifest/metadata中的合同，不修改任何canonical实体、能力、Buff、selector、rule等定义；编译逐定义比较确认相等，可执行scenario字段去除metadata后也逐项相同。合同新增导致content/program fingerprint变化，不能把旧整关三路证据的content身份改写成新草案。

`scenario.metadata.campaign`声明原生level、固定12完整配置与frozenSHA、选技nativeID/owned ability、35原生SPAWN、5种敌人、required_mechanics和mechanic_tests、source_locks、四类typed_gaps及原始pending列表。`native_fields_verified=False`、`pending_mechanics`非空、formal_approval/review_receipt均False。实际调用现有execution_gate会拒绝“pending native mechanics”；review_gate没有外部receipt也拒绝。schema只验证结构/草案边界，builder断言实际来源与消费；二者都不能自证批准。

## 原生字段消费者与真实判据

|来源范围|当前数学消费者/断言|何时必须阻断|
|---|---|---|
|全部options|deploy_capacity8；life10初始/容量；DP10/99及1秒恢复率；moveMultiplier.5；steeringEnabled真实绑定response/acceleration|任何未知option；训练/选预定义/功能禁用/正maxPlayTime等非默认选项；消费者值不一致|
|mapData矩阵/全部palette字段|9×13 topdown；palette index展开；build/pass masks精确枚举；height/tileKey/blackboard/effects相等；playerSideMask ALL是无附加限制 guard|非矩形/越界/未知mask；playerSideMask限制；非空blockEdges/tags/effects/layerRects或tile effects需要新转换|
|所有routes|只有SPAWN实际引用17条执行；bottom-up row→rows−1−row；E_NUM按已解析敌motion明确映射WALK/FLY；checkpoint/flags原文精确比较；randomRange/offset转placement y负号、x正号|未知字段/运动模式；敌motion冲突；未知checkpoint；本关原为零的reachOffset/randomize/reachDistance变活跃；几何/flag/placement不相等。未执行E_NUM占位不误当地面飞行|
|全部waves/fragments/actions|独立cursor时间展开35SPAWN/1STORY/1INFO；按敌ID人口守恒；源preDelay/interval/routeIndex及原生control payload精确比较|unknown/随机分组/hiddenGroup/阻片段/额外wave gating/动作替换；35/敌种/时间不守恒|
|STORY/INFO|0秒story input lock→5条原文命令→同逻辑tick ack/unlock；49秒enemy info/preview payload；SPAWN autoPreview作为UI来源保留，不虚称战斗事件|未知story/替换native action；preview route与源不一致；新的游戏时控制需新模型。UI壁钟/文本显示仍client_pending|
|enemyDbRefs及DB|同pin哈希；useDb true/level0/no override；m_defined false继承、true0覆盖；HP/ATK/DEF/RES/速度/AS/interval/mass精确比较；leak1；yokai FLY/NONE无普通攻击|source hash改变、等级/override/inline来源变化、实际属性不同、非零HP/SP regen或true stun immunity尚无消费者|
|敌combat/帧/mover|实际AB hash+对象PathID；四普通攻击源OnAttack f/30、scale/type一致；无activeBuff/projectile；第五敌applyWay NONE保持被动；steeringFactor/maxForce精确映射|原生active Buff/projectile、禁用combat或帧/scale/type替换。_halfBodyWidth原文保留，点体几何是显式模型，不称已恢复native碰撞|
|runes/predefines/branches/其余根字段|difficulty1不应用3条FOUR_STAR runes；predefines/branches/globalBuff等确为empty/null；bgm/map标识等纯展示单列|适用rune、预定义角色/卡、branch/globalBuff/exclude列表等任何非空新行为必须新转换|
|randomSeed|原953816614原文留审计；完整模型明确seed123、SHA派生MT/placement draw策略|不能称native seed/RNG绑定已核实；当前模型策略有定义和见证时单列client_pending，不伪造native对照|

JSON来源使用真实JSON pointer；DB记录另附derived_resolved_pointer并指回真实m_value位置，不把resolved视图伪装成原表路径。Unity二进制字段记录`unity_object_pathid_and_typetree_field`，不伪造JSON文件中的offset。布尔FSM字段即使为0也不会笼统当“没有行为”；其方法体/比较器/时钟未恢复的部分明确client_pending。

## 我方12人源闭包

逐人断言normalized与roster配置完全一致，基础HP/ATK/DEF/RES/AS/interval/速度/阻挡/DP/再部署/mass与canonical相同；选技initSP、capacity、实际cost及owner引用一致，charge/increment为受支持1。所选官方level_index9全部叶字段列consumer；每人的普通/所选能力、初始人才Buff、源适用人才及可达selector/rule/Buff/token定义身份列入闭包。该引用闭包不把“存在定义”说成“每个effect已执行”。

真实raw source locks包含官方character/skill/enemy表、level/story原始bytes、charpack、BSON模板/buff数据库、enemy AB/mover、恢复帧来源及2025外部tokens bundle；哈希和可定位文件均实读校验，并在构建结束重验。外部2025与local2026对应仍client_pending。旧frozen roster/normalized中历史missing和partial文案完整保留在原产物；草案通过新消费者与实际机制证据逐项解释，不清空原pending。

## 实际机制证据与身份

Root已部署23个listed case按各case引用当前bd60/0fb、实际artifact SHA/test source/case。Kalts3个范围内外DEF/其它killer和Angel友方实际ATK/容量补充也引用当前独立执行artifact。所有旧trio20+DEF1、Night13、Weedy10、Kalts15 artifact保留历史身份，不迁移旧event结果。

当前primary1133 full-suite已真实exit0且no skip/fail，runtime起止bd60。新映射检查原canonical59节点(20+DEF1+13+10+15)对应的实际test/helper已在完成后source inventory，并从这些准确CAS列表构造节点表。**来源哈希记录在completion，不冒充source-start guard**；pytest -q没有逐node事件ledger，本表不捏造它。原CASE预期/负例/CP/replay断言在该全套执行；PACKAGE环境由根任务明确报告为0fb，须由独立审阅者核其launch证据与映射。范围从“没有当前执行”更新为“当前全suite已通过，node/source/env映射待独立审阅”。新增experiments测试不混入1133计数。

## typed剩余门

- `model_gap`：本次未发现冻结声明数学profile内的新执行阻断；Myrtle同步阻挡和半格投影旧反例已由M11/M12当前实现独立见证，不继续列为c0未修状态。这不等于所有native方法体已恢复。
- `client_pending`：原native RNG/seed、selector comparator/碰撞/steering、FSM/攻击时钟与曲线、Kalts preference64方法体、shield事件顺序、Weedy空目标forward、external token版本、UI壁钟。每项有明确已执行模型策略，不假native。
- `witness_missing`：新planned_content身份的整关连续/CP/replay、35人口/5敌种/合法命令/胜利与守恒。原0fb完整长程若仍live，必须待真实结束；完成后仍是原content证据，不能重标草案内容身份。
- `gate_contract_gap`：独立native字段/source审阅、59node/env/source范围审阅，以及绑定完整case_inputs的外部conversion receipt。本builder不自签。

最小下一步：根任务独立审阅上述字段消费者、模型策略与59节点映射，决定哪些pending可按当前model scope确认为已消费；随后固定正式合同/内容身份，实际重跑正式三路关卡并导出可由review_gate读取的证据；由独立reviewer签外部receipt。不得仅把pending数组删空或native_fields_verified改True来解锁。0-1基础回归和总1133通过均不能替代此关正式验收。正式计数仍未在此工具提升。

## 最终验证与冻结身份

实际`--check`通过；离线schema/source/output验证通过；14项定向测试fresh通过（5.39秒），证据起止source/content/commands/core均一致，`execution_gate`及缺receipt的`review_gate`负例通过。没有执行正式关卡战斗。新commands保持源字节完全相同，而非重新排版后声称旧SHA。

- `tools/build_first_model_conversion.py`: `47888d78022c8ad64c1ddd2d2c9f26241bd435f955914628282c9bf0ec8894c9`
- `tools/validate_first_model_conversion.py`: `6d886b2077508b3dd0c004d314533bef16838c60c4fabac08ee17d62da14cf2f`
- `packages/campaign/conversion_drafts/conversion_contract.schema.json`: `eb5577e7a5aca4cf3f59747a9216fa8bc670d6a187a1152b4fb992ad87d836ea`
- `packages/mainline/main_00-10.json`: `d656e138a387e3852c117eb6eeb580ca8b8aac3ee1f32d6d8e21f53818b5b441`
- `scenarios/mainline/main_00-10/commands.json`: `4fe0c2f15121454bd7cef24d43c2eb148eabb07902f796671d51ae98382c2374`
- `packages/campaign/conversion_drafts/main_00-10.audit.json`: `e963ac9944eb93a4a476fec61c0e7c220e0db2f8e601979461d0d2c94caf8d03`
- `validation/campaign/first_model_conversion_tests_20261002.json`: `803123ddeb575b91b7160f045931bc91b513166b49e52f62fc833d3442338b50`
- `validation/campaign/first_model_conversion_validation_20261002.json`: `bf3253966c641066484ee9defb382ad1055d78e2533fc5df85be16ab7b0a9f41`
