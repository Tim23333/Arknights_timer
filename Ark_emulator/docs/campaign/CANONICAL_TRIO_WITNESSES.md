# 陈、雷蛇、铃兰 canonical 机制见证

本批以首关的实际固定12人内容创建独立小场景，入口 `tools/witness_canonical_roster_trio.py`，独立期望位于该工具，pytest入口 `tests_v2/test_canonical_roster_trio.py`。读取当前已修正的 `level_main_00-10.m8_roster.json`；core保持冻结 `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`。固定养成为E2 70、潜1、信赖100、选技专三、无模组。

本批不修改任何canonical entity/ability/buff/selector/rule定义。小场景保留12人roster，移除主线波次及胜负目标；仅改变场景中的位置、朝向、初始SP/HP伤口，添加合成敌、100ATK探针和刺激能力。指定刺激目标的fixture标签保留原有canonical全部标签，只增加一项分类标签。不会用手写普攻/普通真伤替换三人的实际技能或人才。

每个动态case使用真实Compiler+Engine。检查点恢复后再前进两tick、命令replay均比较完整snapshot。所有刺激来自场景初态或submit命令；没有把ctx直接写入伪装为可回放输入。观察只读取资源/已有事件，无额外attribute calculator trace扰动。

最终冻结版本实际 **20 passed in251.56s**，主证据 `validation/campaign/canonical_trio_witness.m8_roster.json` 的 `identity_stable=true`，core/input/source/test/helper开始与结束身份相符。补充DEF见证 **1 passed in4.87s** 且相同输入/core/helper身份稳定；合计21个独立机制用例，未记为一次未经执行的全V2套件。主工具SHA `971abe08048f4e66a62a1490f45d58dc4cc6a4388f0c5b19d7eeff1f91fa3324`，pytest入口SHA `3544a03881a29b9ef0d2fca050d5b066098fbbc6ecd54f3daac6f6c21b1509a2`。

满血再生仍产生accepted amount0事件；35秒半开周期为30..1020的34个零增量脉冲，1050不存在该脉冲。初轮误写“满血不发事件”的19/1失败保存 `canonical_trio_witness.initial_expectation_failure.m8_roster.json`；后来的pre_identity_guard通过也保存历史，不代替本次guard版真实完整重验。没有放宽HP、伤害倍率、护盾、SP或事件/replay一致性的数值期望。

## 独立源与预期

| 干员 | 固定源数值 | 实際闭包见证 |
|---|---|---|
| 陈S1 | HP2724/ATK628/DEF388；人才ATK/DEF+5%、physical dodge.1；S1 cost4/init0、physical3.2、stun1.5；4秒SP1人才 | 普攻13/30tick两包、一次attack仅SP1；full4自动支付、玩家auto-only拒绝、16tick S1与61tick半开stun；4秒人才只给攻击/受击SP、撤退停止；物闪真实RNG、arts不采样 |
| 雷蛇S1 | HP3124/ATK461/DEF731；人才RES+10/selfSP1/四格随机friendSP1；S1 defense SP increment1/cost18/init0，DEF+100%/8秒，damage_block_once | 两hit四笔SP来源、无邻居无RNG、排对角、一/两邻居真实RNG；9个正损伤hit18SP，自动支付；三类shield只耗charge不计HP；owner技能冻结与邻居/半开恢复 |
| 铃兰S3 | HP1413/ATK576/DEF123；timeSP .4最高层、停顿fragile1.2；S3 cost70/init50/duration35、倍率delta2→fragile1.4、regen.2 | .4与Ptilo .3取最高；原生职业/SP过滤；sluggish passive120、S3最高140、source退场100；实时进出100/140；1秒regen115.2、停攻、SP冻结；1049tick140/1050tick100 |

数字来自固定normalized表、原生prefab/BSON/帧记录的独立读取，不从当前actual输出来构造expected。陈技能是当前固定S1，仅physical3.2，不能把别的技能的物理+法术叙述套入。二段普攻仍只一个attack事件。

模型时钟分开声明：资源periodic驱动从tick0累计时间量，30份1/30秒首先在tick29完成；陈的Buff interval首次等待4秒在tick120触发，铃兰regen Buff首次1秒在tick30触发。时钟算法由当前显式profile检验，未宣称原生callback/客户端逐帧已对应。随机期望用独立standard-library SHA256/MT模型计算，不从引擎的实际sample反推；当前profile不是对客户端随机算法已验证的声明。

## 雷蛇源调查与真实整合问题

开始时观察到自身一次受击SP2；不能仅从人才BB1认定双计错误。selected S1 `spData.spType=INCREASE_WHEN_TAKEN_DAMAGE, increment=1` 与人才独立selfSP1均有源，当前接受packet模型合法叠加。见证明确检查两笔增量1分别来自基础资源driver和人才来源，不删除任何一层。

实际缺陷是旧 `m8_damage` receiver没有绑定盾pipeline：S1 charge1存在时，100 physical/arts/true packet分别让HP3124→3119/3034/3024，charge仍1。旧prototype攻击effect显式绑guard，但canonical默认incoming path没继承。

确切源不是模板名猜测：`../data/anon_textassets/buff_template_data.dat` SHA `0c438b57b176e0fa430b5b982a58c7b524f4121aa8dbab33d3e647aa0fc1ee59`。`damage_block_once` BSON offset148552/docSHA `40026ba797109a7ef485e4077fef29a60dfe443dc9cad7f1155945482aea4e7b`，`ON_TAKE_DAMAGE` 动作为 `BlockDamage` 然后 `FinishBuff`，`_filterDamageType=false, _damageMask=NONE, _filterApplyWay=false`，不是只挡physical。S1prefab component path8807449468584965344，buff `liskam_s_1[b]`，lifeTimeType1/maxStack1。

旧失败保存 `validation/campaign/canonical_lisk_counterexamples.m8_damage.json`，passed=false，不覆写。Root新 `build_m8_roster_corrections.py` 绑定receiver after hook，结果为amount0、只消耗shield_charge1，没有再次执行基本pipeline。对被挡packet不回SP采用明确的**正HP损伤模型profile**；原生ON_TAKE_DAMAGE/防御SP/talent的事件顺序仍client_pending，不能把这条condition称为已恢复方法体。

同一工具显式传新包，5个独立case **5 passed in4.90s**：三类护盾、两源SP、blocked邻居无SP/RNG、下一unblocked packet邻居SP1且owner active仍冻结。证据 `canonical_lisk_corrected.m8_roster.json` 绑定新包SHA `7604b67eb0d226f96e15bf567799dd8daf97857718b62a075ba5615c5c13b49a`。该短证据只覆盖所列case。

## 证据接口与验收范围

工具导出 `ark-sim/campaign-mechanism-test-evidence/v1`：真实pytest结果、`passed`、`implementation_sha256`、`tests[]` 的path/source_sha256/result、helper SHA、实际input package SHA、固定配置、源包hash、逐case实际event/resource/RNG及program/runtime身份，并封存原始盾BSON子集。该结构提供campaign_progress.review_gate读取的必要字段，**没有**生成 `campaign-conversion-review/v1`、审核人、approved状态或关卡收据。

`--case` 子集会写明selected_cases；通过五项不能当全部三人闭包通过。client_pending原文不删除，外部2025token或其他九人不在本批范围。这是固定12人中三人的模型机制见证，仍不是首关全程或formal36关证明。

```powershell
..\.venv\Scripts\python.exe tools/witness_canonical_roster_trio.py --package packages/campaign/mainline_models/level_main_00-10.m8_roster.json --output validation/campaign/canonical_trio_witness.m8_roster.json
```

直接pytest默认读取当前m8_roster，`CAMPAIGN_MECHANISM_PACKAGE` 可以显式选择另一输入。工具 `--package` 也会把目标路径传给真实pytest子进程。显式选择原m8_damage时盾反例仍失败；旧输入不会被悄悄替换或提升。

补充 `tools/witness_canonical_lisk_defense.py` 与 `test_canonical_lisk_defense.py` 通过实际默认physical packet证明DEF绑定：tick1护盾伤害0，tick2的2000ATK packet面对DEF731×2结算538，tick240面对恢复的DEF731结算1269，最终HP1317、SP2。没有用attribute查询代替结算。独立command/checkpoint/replay相等，保存 `canonical_lisk_defense.m8_roster.json`。

## 尚需明确的陈S1回能策略

`tools/probe_canonical_chen_sp_boundary.py` 保存另一个真实观察，未算作通过的机制case：初始SP4、敌出生tick119，真实S1自动支付；tick120人才在S1风up期间令自身SP1。`skills.chen.json` exact wrapper `_allowSpRecoveryWhenAffecting=0`，当前SP资源没有freeze策略。原生flag的完整方法体未有证据，必须明确其对应的模型策略，不能静默忽略字段并宣称native闭包。

证据为 `canonical_chen_sp_boundary.m8_roster.json`，带源组件路径/字段、输入/hash、真实事件及三路snapshot。现通用freezer按activation mode区分，而S1与正常普攻都使用automatic_attack；简单冻结此mode会误停普通攻击SP。若模型选择selected-skill期间冻结，需要按active ability定义或显式cast阻回能字段区分，并留正常双hit一次SP的独立预期。本批没有为此改冻结core，也没有把其他21用例通过当作该策略已闭合。
