# 0-11外部source/contract草案与共享机制提案

本稿保持primary M12 bd60、battle输入0c8736089ebd08b1768499c4e043486275c2ccdbbb08f4fa6c4007590f55a149及固定12/36目标不变。没有批准receipt，不修改旧0-10draft、源模型或旧机制报告。外部合同不会进入战斗metadata，因此planned内容与冻结battle字节、program fingerprint保持一致。

## 路径与入口

`tools/prepare_external_00_11.py`构建：

- `packages/mainline/v2/main_00-11.json`：原0c battle字节copy。
- `scenarios/mainline/v2/main_00-11/commands.json`：冻结commands字节copy，SHA6947628516e57bfba40dd913559e01b43ba0b5d5d522e6fd95667928dbb47baf。
- `packages/mainline/contracts/main_00-11.json`：external-model-contract/v2，source_review_pending=True，typed gaps和mechanic refs未审。
- `packages/campaign/conversion_drafts/main_00-11.external.audit.json`：独立source audit，2616条field与真实源/asset锁。
- `packages/campaign/conversion_drafts/main_00-11.witness_scope.proposal.json`：结构适用性提案，由`tools/propose_witness_scope_00_11.py`构建，不是target case执行或批准。

当前合同的mechanic_tests全部空，旧0fb refs仅放shared_witness_proposals，且保留原path/SHA/case/输入身份。contract_gate的仅结构检查可通过；要求executed refs的门实际拒绝。root正在开发的witness_scope外部审查完成前，不跨包放行。

## 0-11专属field消费

原关卡是3个wave、4个fragment，20个SPAWN原actions展开37次出生；STORY一个原action/一次执行，INFO一个原action/count2展开两次执行。每wave出生6、9、22。新审计逐wave/fragment/action/repeat对照相对时间，绝不将0-10 flat cursor假设移到此关。

每个SPAWN的managed、blocks_wave、blocks_fragment分别精确消费managedByScheduler、!dontBlockWave、blockFragment。原pre/post delay、fragment preDelay、maxTimeWaitingForNextWave逐项匹配；实际policy为managed_clear及负timeout wait_for_clear。wave_start在wave entry、fragment_start在其preDelay之后、action_start在首repeat launch；后wave受真实managed clear影响。原生negative sentinel/调度函数体仍client_pending，明确模型本身已定义。

人口：slime4、gopro4、nsabr7、slime_2 17、shdsbr3、wteeth2，合计37。六敌DB按同pin/level0/m_defined语义解析，实际属性逐项比较；真实prefab/Animator/Spine字段、AB字节hash、private BE reader身份重验。六攻击OnAttack帧分别10、10、18、12、19、12，模型timeline/type/scale精确对照。不是按干员或敌人名字猜帧；reader/library没有shared patch。敌机体宽度、动画缩放/AI callback等仍是点体/未缩放source帧模型与client_pending。

route13/14的WAIT_CURRENT_FRAGMENT_TIME30秒有实际consumer：runtime timing_origins.fragment_start+quantize30，而不是arrival+30或spawn+30，WAIT位置只保留并不成为MOVE目标。两次对应wave/16、17。route17的MOVE offset(.44,.44)实际复制到wave/28..32，共五次；topdown位置(4,6)按row−y/col+x到(3.56,6.44)，绑定rule/m9_checkpoint_cartesian。未知checkpoint、offset政策丢失/符号变化均独立负例拒绝。

8×10 matrix/palette/build/pass/height/tileKey逐项一致；playerSideMask ALL、map extras与特殊effect确为无附加行为；options部署8/life10/DP10-cap99-rate1/移动*.5/steering映射。FOUR_STAR runes在difficulty1不套用；predefines/branches/globalBuff等空内容守卫。任意未知或非默认活跃字段不静默删除。

### 同步control必须单独审阅

STORY与两个INFO在原source都是managed=True/blocks_wave=True，当前内容在同步headless完成profile中改为managed=False/blocks_wave=False，原flags与payload保留。该模型解释是effect在launch同tick已完成、没有live控制成员；**不能据metadata说已执行原生异步managed control生命周期**。六个相关原字段被列gate_contract_gap，完整timeline控制语义仍需独立review；不是将有意义的标志强归“已消费”，也不是把M13候选能力偷偷算到冻结bd60内容。

STORY原HEADER/两个PopupDialog/Blocker四行逐字保留，对应lock/发事件/同tickack/unlock。INFO按fragment-relative27/28秒发出，不能引用旧flat toy1380/1410作为当前真实波次时刻。native UI壁钟/pause/confirmation和文字展示编码保持client_pending。

场景原seed1995623974保留；根stage run明确Engine seed123覆盖，reader审计记录两者。不假称已证明客户端seed/RNG关联。

## 共享干员机制证据提案

0-10和0-11非enemy的180个实体/能力/Buff/selector/rule/behavior定义逐项完整相等；固定12配置、所选skill、基础属性、token/人才ingredient实际hash也相同。仅此还不足以跨包迁移执行证据。

新工具在冻结helper真实make边界记录构造JSON并抛sentinel，停止case；没有返回fake Simulation，没有运行case战斗。source与target各构造一次后，真实Compiler及零tickEngine比较：有效初态/参数、明确传入seed、实际可达完整定义、rule runtime fingerprint、provider源码/版本descriptor、初始化world/events/RNG。捕获的原package loader anchor也须分别对应源/目标原生reference，防两次都误读0fb。

86个入口中77成为structural_candidate_requires_review，5个多fixture入口保持scope_not_proven，4个没有make的配置/来源case另列static proof：两个源断言返回值等价、12/ingredient/source资产同一，没有冒称fixture已捕获。多fixture未证明项目是风笛deck/refund双场景、Night失败DP/位置、多死亡/owner退场、taunt多场景、Weedy近远SP。

source与target fixture编译身份通常因scene.metadata/native seed不同而不同，原program/runtime/报告inputSHA绝不改写。有效比较将明确Engine seed替换入view，但同时保留两边scene seed；metadata不是一删就批准：须额外核它不是该case未来rule/provider/helper数值输入，且零tickworld/events/RNG一致仅为必要条件，非完整执行证明。lambda转发/后续分支/所有fixture也需review。实际用0-10 native enemy依赖而目标不同或缺失的case，严格依赖比较必须拒共享或补0-11独立见证；未使用的stage enemy差异只有在真实依赖集合不包含时才排除。

该提案仍formal_approval=False/default_cross_package_gate_must_still_reject=True/target_case_executed=False。root可以在独立scope proof与receipt中批准共享边界；不能把旧0fb actual artifact输入SHA改成0c。

## 剩余验收与测试范围

source_review_pending、独立control语义、共享scope批准、0-11特定地图/敌人/波次/控制事件见证、完整连续/CP/replay最终退出与守恒都是独立项。当前37kill/0leak及CP报告只按实际完成范围记录；cmd replay尚live时不提升pass。即使0-10当前100refs可解析，其flat-flow已发现model gap，也不能批准native-flow或替代0-11timeline审核。

新14个source/contract/proposal负例测试fresh通过：bytecopy/结构门vs缺refs拒绝、拒flat/managed丢失/wave flag丢失/fragment delay错误/deadline错误/offset轴反转/population缺失/story原flags替换/unknown options/map effects；实际Spine源frame/alias重parse及scope保守分类核验。它们只算source审计测试，不是0-11整关或target微场景重新执行。

## 冻结身份与实测

14 source/contract tests fresh通过，实际1.59秒；两个builder的--check均通过。提案构建最初出现列表集合迭代顺序漂移，已改稳定排序并fresh复建/--check，未改变任何数学预期。它们是草案构造/字段拒绝/proposal结构核验，未执行完整0-11战斗、未签source/scope/review receipt。

- `tools/prepare_external_00_11.py`: `19fe07eafb04f2a4ecbdafd6ebcbf9704659d5b95b1db898abfe021ea7b0ec0b`
- `tools/propose_witness_scope_00_11.py`: `cd2391ea7bc5983625f9b9da49d9d5972b388ad6f97429198c7b99f947a0bf6c`
- `packages/mainline/v2/main_00-11.json`: `0c8736089ebd08b1768499c4e043486275c2ccdbbb08f4fa6c4007590f55a149`
- `packages/mainline/contracts/main_00-11.json`: `99fbe84726cead8e5b96ac383a0359093936020b601e34fec67e6ad799a458e3`
- `scenarios/mainline/v2/main_00-11/commands.json`: `6947628516e57bfba40dd913559e01b43ba0b5d5d522e6fd95667928dbb47baf`
- `packages/campaign/conversion_drafts/main_00-11.external.audit.json`: `660f09ed59fec9cba9e4edc9f64a57ab0853f05cb79deeb1278145bb124c225a`
- `packages/campaign/conversion_drafts/main_00-11.witness_scope.proposal.json`: `a189cc978fe1213804ae1879fcadb4d0854b186f2c050398b3f90afda686b46f`
- `validation/campaign/external_00_11_draft_tests_20261002.json`: `9abb2906a21f385902a9f6e189594cff89a48fa8753cdbef86c9eb7148b3d5b4`
