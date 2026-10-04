# 第八章按关卡推进

2026-10-04 最新实际输入：JT8-2 已重新组装为原生草案 V7（32 次出生、289 定义），
使用隔离合并底座 `82db6a9d…`，源定义与 V6、地图和操作均逐值保持；
仅基地生命值覆盖包为 `d8ebb5dc…`，同一公开十二人计划 `f2f73ffd…`。
实际 160 帧磁盘检查点至 330 帧续跑、公有重放、两次受理与环境状态一致，
四项新版本验证通过，收据 `6c21f5bc…`。新的完整三路过程已启动，
证据保存到 `E:/ArkSimEvidence/campaign/JT8_2_82db_native_v7/full_v1.json`。
旧 9ad 全程仍保留自己的身份，不作为已修复动态计时版本的正确性证明。

JT8-3 最新为原生草案 V4（44 次出生、四波、346 定义）：新增塔露拉视觉 Buff 所有权，
保留原生机关与循环分支；Boss V6 `d5c259d1…`、草案 `fdfa0bca…`、
仅基地生命覆盖 `a13f8eee…`，公开十二人操作仍为 `f74bd538…`。
真实八次外部剧情确认、CP10 驱动续跑和从头重放到 120 帧的两项新版本验证已通过。
联合底座的完整回归、独立源审查、Boss 完整四模式和关卡全程证据分别记账；
本次输入编译与前缀验证不增加正式整关数，当前仍为 12/36，用户实机反馈为 0。

以下旧版本段落作为历史证据保留；当前身份以以上版本和 [当前状态](CURRENT_STATUS.md) 为准。

本批固定目标为 **JT8-2（main_08-16）和 JT8-3（main_08-17）**，沿用固定十二人配置和标准难度。仅将基地生命值覆盖为99999；敌我HP、费用、SP、技能时间、部署槽位、出生、地图、路线与原生装置均取原始配置。漏怪、退场与合法操作拒绝完整记账。

当前组装输入为 [JT8-2原生草稿v3](../../packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.json)（8a5debd1...），使用隔离联合core9ad987。完整32出生、原地图路线、固定12、infection与六个volcano均可编译；[基地生命值覆盖](../../packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.life99999.v1.json)（f48318f6...）经type-exact还原只改变生命值及两项验收provenance，28条公开操作见 [commands](../../scenarios/campaign/chapter08/level_main_08-16/public_plan_v1/commands.json)（f2f73ffd...）。尚待source-input独立准入和全程，不把草稿或预设部署当实际接受。

**灼烧来源策略已修订。** 下文eaf1a／c59aa的旧父timer拒绝重施、永久子ramp不重置策略经独立源反例否定，保持历史证明范围，不批准完整Boss。新 [dragon_fire.module.v3](../../packages/campaign/chapter08_consumers/boss/dragon_fire.module.v3.json)（d8c834d1...）消费原EXTEND3为refresh剩余持续时间，区别EXTEND_TIME4相加；父live时子ramp不重启，父结束后同子UID重施generation2并重置ramp与1秒首触发。4作者及6独立实际场景通过，独立报告2b1da9d485f91aeb71cd02a82df508eaa1b8324002a0ef84119fb68b92c52126／26pins冻1f99c2a60bd5fa561ec3ba542b197f52d018a220d63e70079b196ce4915d2ea3，旧两个counter完整保留。来源来自原Buff/BSON/enum和 [PRTS塔露拉页](https://prts.wiki/w/%E5%A1%94%E9%9C%B2%E6%8B%89)的refresh、效果结束reset参考；首56与重启1秒相位仍为可替换解释，动态remaining抵抗未证。

Root火山消费者 [volcano.module.v1](../../packages/campaign/chapter08_consumers/environment/volcano.module.v1.json)（bbd934d3...）已核同历史Prefab的全原raw与两radius1.710000038／.709999978。7项实际作者checks通过c463d833e7c4dfe8a8252ec6642695d820af4c43630cac95a9d1c8aa6529922d：六真实cell、1000PURE、8–12随机公式与RNG、typedmotion/category/free/真实camo17、afterhook500以及完整CP/head。仍使用明确cell+combat正交邻格参考模型，未冒充原Collider物理body验证。

当前仍在内容开发阶段，未登记第八章整关完成。第七章两关的冻结全程进程继续运行，其输入不被第八章开发改写。

新独立source-input窄准入冻结为4c74235557e630b2753e438df6ace90ff08c65eed2eff6ae651d6a2fdfaa968b，支持9ad的JT8-2输入按声明参考规则运行，完整机制状态仍False。动态抵抗afterapply真实缺口已另开 [动态Buff寿命](BUFF_DYNAMIC_LIFETIME_DESIGN.md)；旧9ad/fad92全程只为参考过程，不能因终局批准动态正确性。

原long27642在700保存检查点/导出时因Root选错helper接口而退出（failure4b6bc052...），partial166MB日志保留，未算通过。新同输入V14helper任务35050输出到独立`JT8_2_9ad_native_draft_v2`，launch14f498b1...保原package／commands／core，已正常通过700真实CP继续前进；此为工具选择修复，不修改游戏输入。

源石地形独立7项已实际通过c84961ccfaab374fc633493569952cd88e6af439c9ee47ec5dcf7acf427c3089／冻结12d1db24ccca04bd3604b8af2f1ae5d019653430ec27319b55ef82a0884abbfe：完整300s、299包180、HP70000→16180，公开离格／返格不刷新，ATK246→369与AS1.2→1.7、到期恢复；allside groundCHAR忽略free/camo，而飞行和装置category拒绝，CP100续到9001及head全状态事件一致。

## 原始输入与源闭包

| 项目 | JT8-2 | JT8-3 |
|---|---|---|
| 标准原生文件 | level_main_08-16 | level_main_08-17 |
| 原始出生总数 | 32 | 44 |
| 初始DP | 10 | 15 |
| 部署槽位 | 9 | 9 |
| 原始基地生命值 | 3 | 3 |
| 原生控制 | DISPLAY_ENEMY_INFO 1、PREVIEW_CURSOR 1 | STORY 1、DISPLAY_ENEMY_INFO 1、PREVIEW_CURSOR 9、PLAY_OPERA 17 |
| 原生预放置 | 无 | 10个hidden trap_021_flame，位置与alias全部保留 |

两关共有8个精确敌人变体。来源清单见 [source.manifest.v1.json](../../packages/campaign/chapter08_source_prepare/integration/source.manifest.v1.json)，SHA256为`53b2754ea569b945da3ee6692f6c2f40e97d84d43ba213aae04bf8f4d290ea74`；机制字段矩阵见 [mechanism.plan.v1.json](../../packages/campaign/chapter08_source_prepare/integration/mechanism.plan.v1.json)，SHA256为`e11f14aaa691455c8a9b2ed10b96f14af819d0cea5573110ad8224bc0277eda4`。

[原始源冻结](../../validation/campaign/chapter08_source_prepare_integration_v1/freeze.json)为`fb1b2e42ff92a5f9d5b51108571bc87571c2cf294bbc2252b13124a39a2be4a6`，实际重新读取验证为`7e95159c59f15f02bd276aabd2c705cf29aa7264912893de89dc0ed5b0935d30`。该批核验58个来源／导入／工具文件的起止身份，重新解析两份原生JSON、8变体、15份BSON、8份Spine和对应外部引用对象。源字段矩阵保留240个组件，源准备通过不等于这些组件已有运行消费者。

固定表版本为`56aee3d6c5a29c3a0d192456d70d14252cbb0804`。本地Prefab／BSON／Spine使用各自源SHA；本地缺少的trap_021_flame从已冻结2025-03-27官方资源包提取，明确记录版本差异。不得将缺失本地组件解释为空Actor。JT8-3原生PREVIEW_CURSOR为9，旧目录解析的5保留为历史差异；DB中m_defined=false的HP值50不覆盖真实50000。

## 内容开发与并行边界

| 消费者 | 负责人 | 首批实际工作与验收 |
|---|---|---|
| enemy_1108_uterer@0/dfc143b32f205b76 | Root | 原始近战、阻挡、移动、12帧／45周期、真实伤害与动态属性、撤退／死亡取消、检查点与从头回放 |
| uoffcr、uamord、ucommd | integration_next | 普攻与阻挡combat分别保留、精确弹道／范围／选择器／动画、动态DEF/RES/ASPD与资格边界 |
| emppnt、empace | chapter05_sources_next | 源ScanRange、被动、BB与所有Buff的实际消费者、触发／取消／多个演员与状态变更 |
| 全源与字段复核 | chapter04_review_next | 独立读原始字段、当前接口依赖、真实反例及消费者证据；先完成第七章输入准入收口 |
| Talula、bsnake与环境集成 | Root后续分派 | 完整模式、HP阈值、技能优先级、复生、灼烧、提示位置、分支、火焰装置、全屏技能与剧情控制 |

子agent沿用用户指定的gpt-6.1-sol／medium。每组内容目录独立；通用底座保持当前3992，真实反例证明接口缺口后才创建隔离候选。运行时不得以敌人ID新增专用内核分支。

## 消费者准入

1. 对精确变体绑定DB引用、等级／覆盖项、Prefab完整模式和技能、Buff原始定义、动画事件与弹道组件。不得只从名称推导机制。
2. 全字段列出执行消费者或明确的表现层／参考策略。目标捕获、动态属性读取、时钟舍入、范围边界、叠加和持续时间均可替换，并保存未知原生方法正文及版本冲突。
3. 普攻以不相等DEF/RES和真实Buff变更核对实际伤害，技能以独立源预期核对触发、取消、SP／CD、模式与生命周期。原始60秒／15秒等长时间不得压缩来加速证明。
4. 使用真实公开部署、技能、撤退、控制确认与合法资源。保存连续、分段、磁盘检查点续跑和从头回放的完整状态与事件一致性；中途读取不得污染其中一路事件。
5. 独立复核后再接原始地图／路由／波次／hidden装置和固定十二人操作。整关要求出生守恒、所有演员生命周期结束、pending0、timeline complete与完整操作结果。

PLAY_OPERA的blast_effect_x/y现已定位原始二进制文本，尚未找到本地战斗GameObject。需先确定表现控制与伤害消费者的源语义；不得用任意damage或仅emit来替代必需行为。用户后续客户端统一核对仍保留为反馈阶段，不阻断当前基于参考来源的内容开发。


## 首个实际消费者

[uterer源内容包](../../packages/campaign/chapter08_consumers/uterer/module.v1.reference.json)已在3992编译，SHA256为`97f67cd2aebf8e6d2ea01f1b5ff55ff8ff2ffaf1208634807be218f1149e5c54`。[作者实际执行](../../validation/campaign/chapter08_uterer_author_v3/verification.json)6项全部通过，SHA256为`ec6cf0ef5513b34e4f840dc2c6caa5f1f4e9b9618fb193bb707be146c046a25f`，冻结为`ffc67debb63b92545cc29abd893b6833400af7f8bc0dc39f32ab2c8cd03f7a77`。当前独立复核待完成。

原始3500HP、380攻击、100防御、20法抗、1.7移速和1.5秒攻击间隔保持；真实阻挡从tick1起攻、tick13命中、下一tick58命中。DEF137时每包243，公开Buff增加100DEF后143；公开ASPD增加2使总攻速3，实际tick5／20命中。撤退tick8后无旧命中、tick85实际退出；公开隔离3500ATK／scale1真伤技能使源敌实际死亡并取消在途近战。每个过程都有磁盘检查点与从头回放的完整状态和事件一致性。

作者v1误用了route.exited名称及不完整damage_flags，v2隔离攻击者ATK为0产生真实0伤害；原失败收据c117f...／5e066...保留。v3使用正确entity.exited事件及公开actor ATK3500／scale1，未改源敌数值或底座。


塔露拉半血消费者已单独落地为 [talula.threshold.v3.reference.json](../../packages/campaign/chapter08_consumers/boss/talula.threshold.v3.reference.json)，SHA256 `b3043f93d379d3bf43770adc08203b05f1c8eb0839a22eddf601a0e2b353e1ef`；5项实际作者检查全通过 [verification](../../validation/campaign/chapter08_talula_threshold_author_v3/verification.json) `7bc1e6544cef21c74312b365492aabe16963b34b27a64038304a590dc4641834`／冻结`0d0331af6082da69d9a9c1eb6614ab73809578528fef2bcb567c087dcc4bb3b6`。原始50000HP未缩，25001不触发、25000进入half，真正永久max1 rage使DEF700→1400和RES50→90；恢复血量后保留，二次跨阈值不重复叠加；实际50000真伤死亡不触发半血。全部过程磁盘CP／head全状态及事件相同。

该模块只覆盖阈值／Buff／模式锁存，明确不是完整Boss。两模式攻击、DragonFire、DanceFire原40秒／160秒、原FSM重启与取消尚需完整消费者。阈值当前读取明确源base.max_hp50000；整合引入maxHP修正时必须转为effective maxHP。旧v1对不存在resource.capacity求值失败39b08...和v2错误percent层未产生预期1400/90的失败847aef...保留，v3修正内容读取与预设direct_ratio层，未改源值或预期。


## 两模式攻击与四技能的实际消费者

Talula两模式攻击模块`talula.attacks.v1.reference.json`（31ed589a...）的9项实际检查已全部通过，收据`4e1913d9907b13a9d5b14816860999cb3c936aa068e1a38d6faddf1da95ed361`／冻结`1da2e13db98f3fe632d43debee854ddef08d27345da8745489cff5a66f079bda`。原40帧近战PURE1500不受DEF811／RES27影响；远程30帧launch、homing10、当前RES27／43真实438.0000065／342.0000051。初始自动t0施法先于阻挡建立，旧range在31命中、135改combat175命中；此真实时序单独保留。隔离一tick initialcooldown仅用于先建立公开部署阻挡后的40帧近战证明，不写回原生模块。

原DBraw四技能和stage仅DanceFire覆盖见`talula.skills.source.v1.json`（1ac74d76...）。现有离线resolve_enemy整数组替换只留下一个resolved.skills，按真实Prefab EnemySkill引用逐key消费原DB其余三项、覆盖匹配DanceFire是明确可替换参考规则；独立来源审查已确认四wrapper和rawfields实际存在。

递归灼烧来源见`special/dragon_fire.supplement.v1.json`（d6dd9945...），父timer创建damage子Buff的BSON、原FB字段和30.5／50／180／30技能BB保留。`dragon_fire.module.v1.json`（eaf1a220...）6项实际通过`c59aa86b8c62c99ad61affe0eedc17d02607cb36adfc749a6aeec76da66feea2`／冻`e30083b5ff60be746ec849a62abf0fe1c4a04e38c0f706a619373803ce24ed6e`。当前参考provider按50+180*clamp(elapsed/30)解释增量cap，1秒首包56、30秒230；完整30.5秒父到期后永久子保留但停止伤害，重复父存在不刷新，复用子不重置增量，普通afterhook与source退场仍执行。缺少原生正文下首packet／重燃／child重置仍需独立核对，不当实机证明。

四技能组装`talula.skills.v2.reference.json`（8fb847df...）在**隔离26c47时间上下文候选**运行，5项实际通过`21bf075b9e126494fa831ca414e3c113c853b8877616fdeac7c8458f69dc409a`／冻`53d866b3b1c2f0faf94af48ee5a6fae1bef1f4b7a82772c61b3f713b891aa4de`。原DragonFire19秒570start／600apply，Half7秒210／240；原DanceFire关卡初160秒4800start／4865damage，Half15秒450／900start与515／965命中两个目标1095。Skill_2原mapping1.2000000477时钟与CDstart-relative选择均有显式规则，CD数值没有缩短。

旧skills_v1将CD作为V2 finish-relative recovery导致992而非900的真实失败c669566...保留；v2使用既有ability.recovery契约按实际quantizedduration补偿start-relativeCD，没有修改内核。此前夹具metadata缺失067556...也保留。完整Boss的`restartFSM=true`仍未实现，具体通用设计见 [状态机重启](BEHAVIOR_RESTART_DESIGN.md)；状态抵抗时长、完整集成和独立准入也仍待完成。


## 当前整关组装入口

[精确消费者清单](../../validation/campaign/chapter08_stage_inventory_v1/inventory.json)（9249b7bc096a8e24d8f8ad8f6d03b720d81697e8a51e1f8d340a76b5ce5ac333）实际逐变体核原HP／ATK／DEF／RES／移速／攻击周期／重量／漏怪损失与内容包一致。JT8-2五个精确变体已有内容包，JT8-3四个中黑蛇完整消费者仍缺；其余内容尚需独立review和当前合成core组装，不把module存在当准入。

三个远程普通消费者实际16项source tests通过，冻结74ff47d02253d58b8f196b77e9b64ab593edeaf507378b53f295aa7b6a880dd1；uoffcr v3、ucommd v2、uamord v4保原双路径、真实blockVolume、marker资格、SecondaryFilter3源enum与CP/head。capture前用现有settle_blocking true消费真实阻挡，避免同刻未settle误走射击；未改source属性。三者仍待独立来源准入。

状态机重启隔离candidate cba02a10...已23项作者全通过，自己的完整88424／基线43714和独立复核进行；详见 [重启设计与实际证据](BEHAVIOR_RESTART_DESIGN.md)。尚未推广主3992，旧全程process保持各自core身份。

灼烧初始状态抵抗消费另有 [dragon_fire.module.v2.json](../../packages/campaign/chapter08_consumers/boss/dragon_fire.module.v2.json)（8bac2024...），原AttributeType26／minimum.001／maximum1000从dump逐字核，使用当前target effective属性缩放初次30.5秒duration。4项实际通过 [verification](../../validation/campaign/chapter08_dragon_fire_initial_duration_v1/verification.json)：总倍率.5对应458tick／15包，真实-.5modifier同，最小倍率.001使1tick到期而无30tick首伤。该模块只实现初始duration，抵抗在Buff存续期间变化的剩余时长尚pending，未标动态通过；暂未替换既有Talula冻结模型。
