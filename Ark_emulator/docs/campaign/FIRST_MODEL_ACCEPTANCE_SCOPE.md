# 首个模型验收的独立范围审查

审查日期为2026-10-02；对象是 `level_main_00-10.m7.json`、`build_m7_mainline_model.py` 与冻结 M8 core `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`。固定12人、E2 70/潜1/信赖100/选技专三/无模组，以及18章共36关目标不变。本文件不签收据、不批准转换、不把探索胜利提升为正式验收。

可重复清单由 `tools/audit_first_model_acceptance.py` 写入 `validation/campaign/first_model_acceptance_scope_audit.json`，记录输入SHA、实际编译队伍/技能绑定、基础属性逐项比对、35个出生、原生路线、难度及部署情况。旧 unsuffixed M6 包只作为历史来源。

## 类型与七门

使用五种状态：**model_gap**（数学行为未执行或整合丢失）、**witness_missing**（存在实现但该输入/身份缺独立见证）、**client_pending**（完整显式数学模型已有，原生逐帧/版本对应未证）、**historical_resolved**（旧标签已由新定义实现）、**gate_contract_gap**（证据/审核接口尚未闭合）。前两类及 gate_contract_gap 阻止本次模型验收；client_pending 必须保留，不能借此宣称 native/client verified。

| GOAL七门 | 当前可见证明 | 尚需证明/实际问题 | 类型 |
|---|---|---|---|
| 1 源闭包 | pinned enemy/official表、prefab/BSON、Spine私有BE reader、实际12属性和配置、固定35spawn | 给每个当前整合定义建立源→转换→定义哈希链；外部2025 token与本地2026版本区别仍列出 | witness_missing / client_pending |
| 2 固定12技能/天赋/召唤 | 当前选技均为实际ability，人才和三个token定义已整合 | Saria S3法伤增幅在默认真实pipeline未生效；未部署六人需当前canonical包独立闭包测试 | **model_gap** / witness_missing |
| 3 原生敌/地图/路线/控制 | M7真实随机放置、8邻接无穿角、steering、旋转索敌、自己的阻挡者优先均已实现；difficulty1不套三个突袭runes | 同身份源动作消费计数、出生/退场/剩余守恒、锁输入及显示控制负例；原生连续空间/客户端UI时钟仍待对齐 | witness_missing / client_pending |
| 4 独立预期与事件 | 既有各recipe/domain/source套件和peer反例；本次新增实际Saria反例 | 旧prototype通过不能代替wrapper变换后的canonical actor见证；列各事件时钟与数值操作数 | witness_missing |
| 5 固定脚本模型胜利 | parent报告M7探索35kills/0leaks，实际脚本部署六人 | 完成artifact绑定真实输入SHA，保存合法部署/DP/HP/kill/leak守恒；胜利不自动给12人全部机制盖章 | witness_missing |
| 6 三路同身份 | parent正在顺序连续/检查点/回放验证，旧成果保留旧身份 | 尚未完成的live进程不得记通过；需最终state/tasks/RNG/逐事件比较和源/命令/内容/runtime身份 | witness_missing |
| 7 独立审阅/模型与客户端分开 | 独立审核工作已展开；客户端证据继续单独列 | 正式execution_gate还没有当前转换receipt，且现证据结构不匹配审核字段 | gate_contract_gap |

## 实际整合反例：Saria的倍率只有属性，没有结算绑定

`tools/probe_first_model_saria.py` 读取当前包，以真实Compiler+Engine创建其canonical Saria/Eyja和无RES的敌方探针。仅把Saria SP置80以隔离付款等待，清波次，不注入自定义伤害规则。相同 `damage_type=arts, scale=1` packet 在S3前后均结算 **809.4**，同时目标 `arts_factor=1.55`；独立预期为 **1254.57**。证据保存为 `first_model_saria_integration_probe.json`，明确记录实际内容、runtime和program身份。

位置：`build_aura_skill_recipes.py` 的 `buff/demkni_member` 添加属性，但旧fixture的 `ability/aura_probe` 才显式绑定 `rule/aura_arts_amplification`；当前M7 Eyja普通/S3packet使用默认伤害pipeline，member没有incoming hook。本缺陷不能归类client_pending。下一内容wrapper应给实际目标绑定arts-only incoming hook，利用支持health allocations的settlement scale，独立检查physical/true不变、离开/死亡/到期清理、多来源叠加策略和shield+HP混合分配。冻结core及M7包本审查不改。

```powershell
..\.venv\Scripts\python.exe tools/audit_first_model_acceptance.py
..\.venv\Scripts\python.exe tools/probe_first_model_saria.py
```

## 历史标签与当前模型不能混读

M7已经执行非零spawn jitter、8-neighbor/no-corner、steering、rotate-with-facing与own-blocker。旧包的 `native_diagonal_and_steering_semantics`、spawn/控制总括标签不能直接判当前数学模型未实现。当前Cartesian halfextent、bounded proportional velocity、arrival radius .05、零逻辑时长headless STORY ack都是显式可替换模型；客户端分布、连续碰撞/原生方法体和UI暂停次序仍是client_pending。

integrated squad的pending数组把模块级标签复制到多个operator，不能按每条标签判断该角色实现。例如Ptilo现在有持续三目标.75s模型，Mon3tr有f7/f20自动攻击，Weedy cannon有f1/travel4默认攻击，Night有AttackC三目标、RES及bird，Saria有驻场层与heal-SP；旧manual-only/normal-runtime-pending标签已过时。保留原文作为历史，不删除原生callback/2025-2026 source版本/客户端clock对齐的真实待证项。

WIP数学模型选择仍必须有完整行为边界。例如Eyja .5s automatic随机人数/clock与原生firstsignal/binding未对齐，但不再是“普通真伤placeholder”。Weedy实际无目标S3施放消耗33SP、30tick内零projectile是已观察边界；wrapper `_allowNoTarget=1` 仅证明允许施放，不能单凭此字段推断原生前射。需完整native action图证据或明确可执行空目标模型profile及独立预期，不能把未部署当证据。

## 未部署六人的最小独立闭包见证

本关脚本部署Myrtle/Bagpipe/Exu/Ptilo/Eyja/Saria。固定deck仍12，另外六人的证据可由同canonical包的独立小场景完成；不能把deck改六人或用旧手写普通能力替代。

| canonical operator | 必要独立预期与边界 |
|---|---|
| Chen | 一次attack的SP与多hit区别、自动S1支付、物理+法术与stun、风up取消/restart；dodge.1及4秒SP源/非SP/冻结类型 |
| Liskam | 18次受击到auto-only支付，8秒DEF+100%、一charge抵伤；charge分配不计HP受伤；随机邻居、空/死/无SP及emit时冻结 |
| Kalts | self/ownedMon/foreign治疗分类，host .1s owned-live SP门/失token清SP中断；DP10/cool25/block3；Mon f7/f20、true与衰减capture时钟、DEF零化/回收，ownkill与otherkill/no-kill50%、death1200+3秒stun及withdraw区别 |
| Suzuran | .4和Ptilo .3最高SP层，sluggish-only fragile1.2/S31.4来源优先组；inactive ghost不增伤；35秒regen/禁攻/live进出/半开到期与source退场 |
| Nightingale | 基础+15RES，S3ATK/RES/arts-only dodge、三伤员AttackC27f重复/恢复；bird两卡+DP5原子/容量0/无攻击/禁普通heal/taunt/3%HP每秒、物闪、耗尽/敌杀真正退场；卡片native回补和外部版本边界 |
| Weedy | DP5/容量0/cool35/cannon20秒/SP3秒/距离/owner退场；f1正常射击与travel；S3host/cannon联动、arts AoE、推力/墙裁剪/飞行资格、真实ledger每格1200与EXTEND/来源/末段；空目标行为单列 |

已部署六人也要实际技能/人才事件见证；例如35击杀不能证明Saria倍率（本次已实证失败），Myrtle半开16DP、Exu多段/自动首tick、Eyja RNG、Ptilo恢复、Bagpipe倍率/首SP/killDP、Saria20秒五层/heal SP都应绑定当前包。

## execution_gate的具体接口缺口

当前 `campaign_progress.execution_gate` 要求 `scenario.metadata.campaign`、固定引用/完整12配置、显式空pending、`native_fields_verified`、每个selected ability metadata中的exact `native_skill_id`、required mechanics与test对应表，以及外部绑定input/runtime/source/config的review receipt。实际M7尚无该campaign结构；Bagpipe/Eyja/Suzu/Weedy selected ability缺 `native_skill_id`。这是审核身份绑定缺口，不意味着其能力是placeholder。

run_case正式路径是 `packages/mainline/main_00-10.json` 与 `scenarios/mainline/main_00-10/commands.json`，当前实验m7路径不会自然被运行/提升；不能用0-1替代。review_gate要求测试artifact含 `implementation_sha256` 和 `tests`，而现fullsuite artifact含 `implementation_digest_at_completion` 与 `test_sources_at_completion`；需要可信且可重复的证据适配导出，不伪造receipt。pending必须先按上述类型逐条复核，不能把全部native待对齐项一键删除来过门。结果保存/历史身份已有独立integrity测试，但新输入仍需实际review。

## 足以审查首个model验收的证据清单

1. 新wrapper修Saria结算并封SHA；记录M7→修订内容差异，旧35kill和正在运行的三路结果继续标旧输入。
2. 源/转换闭包表逐定义绑定12固定配置、技能/人才/三个token、官方表/reader/source模块；逐pending明确数学模型选择与native/client待对齐，model_gap数量必须0。
3. 当前canonical整合内容的12机制矩阵：至少独立预期、事件操作数/首末tick、负例、selector/clock与source retirement；未部署六人见证单独链接，不需改首关固定脚本。
4. 首关35出生/5enemy/完整路线与控制动作消费、正确难度/runes、输入锁、击杀/漏怪/剩余守恒，以及命令资源/地形/容量合法性证据。
5. 修订同SHA输入的固定脚本胜利与连续/分段/checkpoint/replay完成artifact；state、tasks、RNG、events完全一致，报告持久文件hash及真实实现身份。
6. 有兼容schema的实际测试证据导出和外部独立review绑定完整input_identity；审核人检视此矩阵后才签model门。client_pending数量和内容独立保留，正式目标仍36，当前本审查批准数0。

## 同日修订内容复核

上述实际缺陷属于冻结M7原输入。Root随后新增 `build_m8_damage_integration.py` 和 `level_main_00-10.m8_damage.json`，没有覆写原包/旧长程证据。用**同一独立probe**显式传新package、新output得到809.4→1254.57，factor1.55，独立预期一致；保存 `first_model_saria_m8_damage_probe.json`，旧失败证据不改。新wrapper的12 selected ability均有exact native_skill_id且由对应actor拥有，四项结构缺字段已经闭合。三份wrapper `--check` 实际通过；这些短机制见证不把旧全程胜利/replay迁移到新内容，其他七门和未部署六人证据仍须完成。
