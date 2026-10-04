# 第2章完整关卡组装进展

当前固定目标仍为2-9与2-10。Root准备严格stage scenario转换，roster负责敌方精确variant/出生/光环和Boss内容，catalog负责M41通用坑洞contact机制。当前资料支持声明模型完整交付，用户实机反馈后置；缺必需实现仍不能标整关完成。

## 2-9 调度

`tools/build_reference_stage_scenario.py` 直接消费原始level、显式native enemy→精确unit绑定和实现后的map profiles，不读V1战斗代码。转换保wave pre/postDelay、maxTimeWaiting、fragment preDelay、每个action preDelay/interval/count以及managed/dontBlockWave/blockFragment。
实际源有52次SPAWN、两条DISPLAY_ENEMY_INFO action共7次重复。两个控制定义使用现有logical immediate-ack且拥有真实control/timeline成员，不把count6缩为1、不抹 UI 控制时钟。无法转换的action、grouped spawn、随机分组、active rune、predefine或branch直接报错。

四检查已实际通过：52出生/7控制、原管理标记与源片段不变、missing enemy/tile profile拒绝、unknown action/active rune拒绝，以及假mechanic profile类型被实际profile validator拒绝。
当前保存 `scenario_ir/level_main_02-09.scheduling.reference.json` SHA `3b566466c8c765087e8c959d51295493aa9e0fc4bf96630c6d4ce015d745d43b`。它不含可执行map profiles，runnable=false，缺坑洞/地板/实体闭包会被Compiler拒绝，不作runtime或整关收据。

## 精确敌人与地形闭包

- 五variant绑定由 `chapter02_units/main_02-09.enemy_binding.plan.json` 锁定，总数26/8/2/12/4=52。两airdrp使用actual L0/nulloverride的单位/攻击/选择器/decision与45tick born Buff，不在关卡开始提前创建未来敌人。
- yokai明确无攻击飞行；yokai_2实际circle2/f8攻击；defdrn防御+300、声明radius2.5光环还需silence/资格完整转换。
- Gazette/gazebo使用typed `selection_state.motion` 的FLY-only1.7加成与AS−20，避免fly/flying标签拼写导致错误。实际地图BB保留，并由profile全部绑定。
- HoleTile实际map数据与template通行字段不同；正常路线避坑、强制位移接触与ground/fly环境死亡必须显式实现M41，不能把坑当无效果field或平地。
- 原始runes按当前固定NORMAL1难度掩码单列active/inactive，NONE0保原数据而不无依据套倍率；策略来源/版本后续审阅，active未知符文不忽略。

完整包下一步合入固定12人配置、52出生/7控制/各地图cell机制、所有enemy closed dependencies，锁新来源/core后跑完整过程、公开操作、durableCP、fullreplay、独立source-consumer审阅。2-10还需STORY/WAIT_CURRENT_FRAGMENT、skulsr50%/3×3榴弹与aoemag范围接口，不能直接复用2-9已通过状态。

## 已冻结的公共组装模块

`tools/campaign_content_composition.py` 使用当前选定 Compiler 收集实际可达定义，删减后重新编译并逐项比较定义、scene、ruleset和rules。相同重复定义可以合并；数值冲突必须显式提供完整替换、原因与来源；缺引用保持报错。四项实际检查通过，不使用标识符名称猜测依赖。

固定十二人独立模块 `roster/fixed12.m26.reference_module.json` SHA `fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04`，保留176个author定义：12人和3个实际召唤物及其闭包；第一章W、EMP、预定义NPC和控制均被实际引用排除。旧名称包含probe的三个ability仍由正常选技实际引用，保持其现有事件执行实现，不按名称删去。每项保留定义记录原模块、定义digest和继承的规则/反馈说明。它没有独立关卡，不是整关通过证据。

地图field模型 `chapter02_tiles/fields.reference_model.json` SHA `b35e21da93109e4d32b17cc413dcf5d2744d36b5bbf90c251171cb136e45f167`，绑定现typed numerical operands与实际TargetOptions。BuffTile sourceSide1→显式虚拟我方side0、ALLY1/motion3/category1、advanced disabled；每cell来源独立child是现通用Aura的显式适配，保留原native maxStack反馈项。九项实际测试通过：公开入/离格治疗500→530、敌方/category/free/camouflage拒绝、typed飞行友方接受、gazebo AS1→.8→1、实际field伤害90ground/160fly/离格后90fly，以及保存CP续跑/同序查询平衡重放；最终报告 `validation/campaign/chapter02_tiles/reference_fields_final.json`。坑洞未在此模块伪造为field。

候选M38完整回归已终止成功：1224项／1982.01秒，源码前后均2165，报告 `validation/campaign/m38_integration/full_suite_20261003.json`。随后新地图field8项也fresh通过；两项新增模型不靠旧整套回归自动自证。

防御无人机模块独立测试发现手动移除沉默后同帧Aura还未恢复：本应防御+300、伤害600却得到900。原2165失败命令与事件已保存，M42正修通用Buff.remove同步reconcile及重入/回滚；不会把期望改为下一maintenance或覆盖已有运行身份。

2-10剧情模型 `chapter02_stage_models/controls.reference_model.json` SHA `c901279e9b3366faa8731d88a56f531733aed81ebfb32987937d926f108a2e5a` 使用原payload SHA和原dat SHA审计，逐项保留HEADER/两PopupDialog/Blocker字段。使用真实control生命周期、input lock及两个即时ack步骤；画面Blocker fadetime保留为UI metadata，显式逻辑时钟不把它猜作战斗延时。一次实际完整控制fixture验证4行事件、锁解除、managed成员释放、下一fragment和保存CP/重放；另检查2-10 36出生/2控制及WAIT_CURRENT_FRAGMENT_TIME82秒引用原fragment，不扁平化。加原converter4项共6checks通过，报告`validation/campaign/chapter02_stage/story_control_tests.json`。未知STORY或缺exact key/source绑定直接拒绝，未执行整关。

M41候选43cdc冻结后，Root新增 `chapter02_units/airdrp.birth_contact.model.json` SHA `ee1b526bafdd61f3c924d9f58bc7c9c109e0db300ff2c72a84455989744bb44e`，原born8bbe、HP、出生计时、能力与Buff控制保持不变，仅显式声明`contact_flags.defer_fall=true`。真实airdrp在坑出生fixture验证44tick仍存活/1450HP、45tick坠落并HP0、保存CP与完整命令重放全部相同；报告`validation/campaign/chapter02_airdrp/birth_contact_adapter_tests.json`。这是声明的出生完成接触规则，不从stun/target-free猜环境免疫。

## 当前整关探索及新发现

M43修正完整request保真后，独立15case及两public savedCP/replay通过，peer报告`validation/campaign/chapter02_fields_peer/m43/final_review.json`。M44把无重叠的M41/M42/M43合并为core81d，175组合checks通过35.52秒。Root 2-9初版`level_main_02-09.m44.reference_model.json` SHA `8f0bcbfe9cb1d556775c46d2c22c0fd3edeb44f8519edad7d9d2da2dbf552b3b`实际Compiler通过209author定义，真实初始化两gazebo cell field，99999派生71850和40条十二人轮换公开操作正整关探索。

该初版不作来源闭包验收：三fly旧prototype没有写入actual MoveController steeringFactor20/maxSteeringForce100，roster正补新五敌module；原输入及正在运行身份冻结不迁新输入。整体调度实际Compiler发现并修正max_wait_seconds名称和null checkpoints规范化，新原始数据/Source记录不改。当前输入源缺口存`validation/campaign/chapter02_stage/m44_v1_source_gap.json`。

M42新独立peer还发现合法重入错误：A移出aura、A child.on_remove撤source后，旧desired仍给B保DEF+5，同技能后续ATK100/裸DEF10应伤90实际85。旧M42/M44通过范围保留，不能签所有中途时点。catalog在M45新候选修通用失效desired/membership和重入回滚，Root不把它藏成内容特殊分支。

16956初轮最终真实exit1：最后报告tick900／3kill+3leak／pending42，下一帧gazebo typed hook因airdrp实体缺selection_state而失败，没有完整执行报告。新五敌4d9已经补source steering，但也未给无攻击yokai和airdrp写typed state；它的18检查范围仍只支持自身属性/运动与选择器默认投影，不能自证field输入完整。Root stage adapter给全部五敌逐variant添加typed motion1/2、明确side/category/status策略；旧module4d9保冻结。source_closed_v3 SHA `bd55760519160c002bcef498e04d91eeb64ca432f6dfdbabf40380871661f1ed`实际Compiler/整调度/source mask/初态field检查通过，99999派生badbf6在新session85067用v7进行完整运行。此输入仍保留M42重入问题范围，后续新core不能迁用本次结果。

source_closed_v3接线补充实际伤害fixture：真实native gazebo cell、实际yokai/airdrp目标和各自typed运动；隔离施法者天赋以固定ATK200，源DEF50/100保留，对空200×1.7−50=290、地面200−100=100，两个命令链/完整重放相同。与完整源调度检查共2pass1.83秒，未改变长程输入。该fixture避免将未执行的selector defaults误当成entity typed字段。

当前stage composer进一步给moveMultiplier守恒门：复用的movement.speed规则multiplier必须与实际options一致，否则要求显式新规则。2-9/2-10源均.5，旧复用规则也是.5；新增门不改运行公式，后续源值变化不再静默沿用.5。两stage checks在M48 fresh通过，新builder身份与旧89df输入保存的builderSHA分别保留，live包不重新生成。

新runner v7同时记录实际scenario.finished帧与所有计划命令结果；终局后的既定操作由正常公开API拒绝，不能少记录后续操作。独立提前漏怪结束fixture验证终局早于tick150、后续撤退明确拒绝、保存CP和完整重放全部一致，报告`validation/campaign/runthrough/v7_terminal_commands_tests.json`。v6及所有旧live工具没有改写。

2-10碎骨推进M46通用纯area.members可替换合同：既有area只支持圆形，不能准确表达目标格及八邻格。新九宫格按声明offsets与现格投影消费真实impact中心，未配置者仍用原radius路径；精确source范围/飞行splash/源归属和半开DEF−50%5秒需实测。原serialized40%与当前参考/DB50%差异继续保留，不能默默删去。

2-10治疗地板接线准备：`tools/campaign_tile_recovery_adapter.py`明确向HP健康资源挂MaxHP ratio连续恢复rule，增加hp_ratio_recovery0属性，保持原HP/容量；已经有恢复驱动或ratio的单位拒绝自动覆盖，需要显式组合规则。实际固定桃金娘MaxHP1565隔离天赋占格1秒，HP500→546.95（1565×.03）；完整回放一致。新`roster/fixed12.healing_tile.reference_module.json` SHA`e1e4f053f5c0e45e4aa3d3e54be7e923b40ba76ad9c54c6f351c605257da1f31`给12+3owned单位挂明确driver，原HP/容量/选技逐项不变，合原HP规则后实际Compiler闭包15entity通过；另既有恢复拒绝共3pass1.66秒，M48报告`validation/campaign/chapter02_tiles/recovery_adapter_tests.json`。场景正式组装仍需合实际全单位恢复及技能规则，不靠这个隔离例子批准整关。

## 2-10 新完整输入

敌方module正式冻bf13eb78c7b81dd0727c60f3d88d4f7d09a5244c6cfb9dad1e959ad0c5dd3859，十二variant／36出生／71定义，native_motion元数据完整，实际15cases26.19秒，报告9aa4d08cfa005cca82e4dd1432e416609a10ef054f0f836c99a80707abc1f0f8锁真实包与corea829。原未带motion版本及收据保留。combat INPUT_TARGET2只给mocock/wizard/aoemag对应能力绑定阻挡优先，不覆盖Boss或其他单位的规则。

Root完整scene经Compiler得到256author定义，SHA`b0f014359f908e47dd612f3cfb277efa97d011c230d418b82276cd7938360f30`，base99999派生`b5a19abf31d51c737d1d20a755b65db1b4f0a94a33312acf2c7389c6d8955f86`。短fixture实际100tick四field cells1:4/1:7/4:4/5:6、原STORY四行/锁清、36 pending，保存orderedCP与完整replay等，报告`validation/campaign/chapter02_stage/02_10_composition_tests.json`。38条公开12人部署/选技/轮换与末段释放脚本逐项地形检查合法，实际命令结果仍由runtime记录。完整v9 session81406已启动，独立敌方闭包复核继续；没有整关终局或客户端准确性声明。

后续独立peer发现原bf13优先级声明不成立：INPUT_TARGET2三个source能力仅用有限负分偏向blocker，合法taunt20会压过它。wizard/mocock实际公开部署已形成blocked_by后仍攻击另actor，两个反例保存，真实代码/内容缺口不列成客户端反馈。全12lifePointReduce另实际短漏怪验证正确（Boss减2/leaks1）。新content修订将blocked时只允许实际blocker候选，未blocked保原资格与taunt；原bf13/b0f0/81406继续仅作探索，不能自动批准其目标正确性。

新combatguard模块5594dde9已实际14case通过26.92秒，blocked候选身份是资格而非有限分数，taunt20／±1e6不能抢其他primary；原filter/free/geometry仍保。新场景257定义SHA0ecf95b9、99999派生ca905a，短剧情/四field/CP/replay检查通过。新v9整关20766启动，原81406在保输入/CP/末进度后停止actualexit1（已知优先级错误），不是终局验收；独立原反例fresh复核继续。

2-9当前M47至6600的8剩余yokai2源HP1550/attackTrue/moveFalse，引发移攻profile复查。实际sourceMeleeAttack endAnimKey=Move、f8，wizard/mocock/aoemag则Idle；旧stop_on_targetTrue是声明默认而非源等价字段。roster将只对yokai2新内容采用施放期间暂停、结束恢复route的明确source/referencepolicy，源属性/时点不改、movingfire正文具体细节保反馈。必须实际存活目标/结束移动/攻击周期/CP回放，不用withdraw来证明这个中途规则。旧44645/input仍锁，新的运动选择另生成身份并完整验证。
