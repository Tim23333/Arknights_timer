# c0 / M10 首个完整模型验收矩阵

2026-10-02独立只读审查。当前primary digest `c0b92545a714e763f3e43d4e13d25f0be99ecda912cb8479536982ac38f8216e`，输入 `level_main_00-10.m10.json` SHA `2b7fe8d63a30765614a63a9914b6c3a59248600663f85972527491390bd44de8`，program `6a465840bdbea6a74e30b2753db097ed3a789e62efbab6a074e7f8982f92f018`。固定12人、E270/潜1/信赖100/选技M3/无模组及标准36关目标不变。旧 `FIRST_MODEL_ACCEPTANCE_SCOPE.md`、f8/f6bb证据保留历史；本文件不签receipt或formal approval。

`tools/audit_c0_first_model_acceptance.py` 实际读取并编译当前包、零tick构建身份，导出 `validation/campaign/c0_first_model_typed_audit.json`。当前240defs/20entities包括12operator、3token及5enemy；逐一比较normalized固定配置与HP/ATK/DEF/RES、选技native ID及actor ownership，12项均正确。M10纯构建 `--check` 实际通过。12配置与技能身份存在不等于技能、天赋全部已被执行。

## 证据身份层

| 实際证据 | 内容/实现身份 | 对当前c0的解释 |
|---|---|---|
| Chen/Liskam/Suzuran主20+DEF1 | roster7604b… / f8；全部21通过 | 历史独立数学见证，不能提升当前c0 input2b7通过 |
| Night13含60s半开 | targeting_v2 aa272… / f8；13通过 | targeting/RES/三治疗/卡与生命周期已见证，当前c0仍需真实重验/明确collect清单 |
| Weedy10 | roster7604b… / f8；10通过 | 卡、20s/CD35、SP、f1/travel、联动、ledger及末段已有独立预期，不是当前身份收据 |
| Kalts15 | M10同input2b7… / f6bb；15通过 | 同内容、不同实现，保留原program/runtime；不能改成c0通过 |
| M10精确资源peer4×2 | 纯资源d694…及综合2b7… / f6bb | 证明当时修复原SP/ordinary-heal中断与atomic；现c0需原期待当前来源记录 |
| primary targeted105 / 0-1 | c0真实主路径、0-1完整CP/replay已通过 | 当前底座回归证据，0-1不能替代正式0-10或固定12机制 |
| M10 full0-10报告 | input2b7，运行中的独立runtime报告 | 必须待最终退出与连续/恢复/replay完成；临时passed=false/replay=false不当失败结论，也不提前标通过 |
| 旧damage0-10 | 内容3038… / f8，35kill0leak/CP/replay通过 | 旧脚本范围成功且真实保存；增伤/盾/资源后续内容身份都不同 |

当前全suite如已真实collect这些具体test/helper版本并锁定c0、PACKAGE env2b7和输入/source SHA，可成为当前机制执行来源；否则补这些冻结场景的单独fresh导出。不能从终端“总数通过”或末尾新文件hash推导某个新用例已被当时collect。sourceinventory与actual test selection/输入必须一一对应。

## 四种缺口的当前分类

| 类型 | 当前具体项目 | 判定依据 |
|---|---|---|
| **model_gap** | Myrtle S2停止阻挡不同步、ready skill在normal windup被blocking cast拒绝 | 实際canon t0阻挡→enemy cast1→伤害19；source BLOCK_CNT FINAL_SCALER0 active-skill buff，模型声明停攻停阻但实际采样旧link |
| **model_gap** | grid range与collision的精确半格投影不一致 | `_cell` half-up与selector_grid Python half-even；row4.5被碰撞归5却在row4水平range攻击，row5.5两者均6 |
| **witness_missing** | c0修订内容的all12能力/人才/召唤与正式0-10三路全程 | 既有独立见证绑定f8/f6bb，现Package/runtime身份未同；运行中的报告未最终完成 |
| **witness_missing** | 已部署六人按actor/ability分组的命中/治疗/DP/SP/RNG/状态区间 | 目前正式报告只有总体event_counts与commands；12命令accepted不自动证明autoExu、每个人才及数值边界 |
| **gate_contract_gap** | execution_gate的campaign namespace、required mechanic→executed tests表、正规路径和外部receipt | 当前实际编译调用返回“compiled scenario belongs to a different native level”，因campaign nested metadata尚未作者；不是选技native ID缺失 |
| **client_pending** | explicit clock/FSM/RNG/selector/外部token版本策略与原生逐帧不对应 | 数学定义已完整时单列，不能泛称实现不存在；同样不能声称native已恢复 |

上述两个model gap在当前c0保持真实阻断。M11专门修block同步、M12拟修格投影，两者未promote前不能从本矩阵删除，也不能把未测投影补丁塞进已冻M11。

## 两个新counterexample

`tools/probe_c0_myrtle_block_boundary.py` 与 `validation/campaign/c0_myrtle_block_boundary.json` 保存原始命令/场景/source/实际事件及纯内存通用假设。Myrtle与真实gopro同格WALK，满24SP并命令0，当前NoBlock在timeline0的后阶段应用，仅改变block_count−100%。movement在t0已建立link，enemy在t1启动新attack，再t1才释放，t19HP伤9.5。

Native引用为skills.myrtle.prefab component7458720872929114507、`astersi_s_2[a]`、attributeType5 BLOCK_CNT/formulaItem3 FINAL_SCALER/value0/lifeTimeType1，以及switch_mode_restart_fsm。纯内存on_start+control.blockFalse+cancelpending能防命令0新建阻挡；但已经held的真实关系仍在cmd1后被enemy cast1采样，说明需要通用同步release/reconcile。未加cancel时normal windup会拒S2命令；该fixture混淆已分开，不能当control失效证明。M11应保留已真正cast/launch的敌方攻击政策，重点阻止释放后才启动的新cast，不硬编码角色分支。

`tools/probe_c0_corner_projection.py` / `c0_corner_projection.json` 读取canonical Myrtle水平range1-1。目标(4.5,5)的GridTopology `_cell`=(5,5)，但selector round-row4，actual tick15攻击一次；(5.5,5)两者均6、不攻击。独立half-up预期由floor(pos+.5)明确计算。此为内部数学策略一致性，不是把缺方法体的native continuous comparator伪称已验证。circle/raw distance应保留连续几何，修格投影时另测负边界、4.5/5.5、原点/朝向与own-blocked跨格。

## 固定12人的最小机制闭包与当前来源

| 角色 | 真实定义中的必需数学行为 | 当前剩余验收见证 |
|---|---|---|
| Myrtle（已部署） |24/16秒/16DP、.5ATK单伤员、25HP/s先锋aura、停止攻阻 | 修M11；sameframe held/new、释放恢复/first-last heal/DP16 endpoint与source退场；native同帧末DP先后单列 |
| Bagpipe（已部署） |40/20秒/triple14,17,20、interval+.7、ATKDEF120%/block+1、critical/splash、killDP1、deckSP6/退款 | 当前stage actor对应多段与RNG、目标死亡后splash/DP、mode结束/源退场/冻结；未布场的deckSP仍独立见证 |
| Exu（已部署） |AUTO30/15秒/5packet/1.1、AS+.12、ATK6%/maxHP10%、随机友方祝福 | rawself/friend/on_deploy/source退场、HP策略按M7明确模型、auto-only/empty targets/半开/多段；normal源是SimpleAttack非S3projectile，不能按名称虚加弹道 |
| Ptilo（已部署） |100/init85/40秒、三伤员/flat.75 interval模型、global最高+.3 TIME SP、正常模式恢复 | actor分组40秒/first packet/三目标重选、进出/源退场/与Suzu最高层、事件SP不加；没有源曲线字段不硬造ramp |
| Eyja（已部署） |80/15秒/.5 automatic随机count/dynamic6targets、ATK+130%/interval−1.1、caster14%aura、deploy float7..16SP | source→RNG→目标集合/伤害event链、满/不足目标、on_deploy/retire；nativefirstsignal和selector1→BB6绑定属显式profile/clientpending |
| Saria（已部署） |80/30秒/slow/arts1.55 incoming hook、.35ATK全伤员heal、20秒五层ATK/DEF、ownheal目标SP1 | 累层值、arts-only健康alloc/fragile叠乘、source退场/leave、healing.accepted emission freeze，regen不误返SP；旧Source包括两个人才均已实际绑定，未发现“缺人才” |
| Chen |13/30两hit一attackSP、AUTO4/3.2/stun、4秒人才/5%stats/.1dodge、精确S1freeze | 原21与M10peer当前c0重验或锁定fullsuiteinventory，恢复普通SP与同帧冻结 |
| Liskam |防御1+人才self1、随机邻居1、AUTO18/盾1/DEF100%8秒/RES10 | 三类型shield、HP统计/positiveHP SP profile、死/无SP/空/冻结邻居与半开；blocked native SP事件顺序待client |
| Kalts |self/own/foreign profile64、ownedDP10/cool25/block3、15/20秒/curve/死亡1200stun3/kill penalty |15冻结场景当前c0真实来源；other-killer与范围外DEF可补，不能旧prototype转新scope；普通heal必须不被SP门取消 |
| Suzuran |.4 SUPPORT TIME最高层、passive1.2/S31.4 fragile条件/优先group、35秒.2regen/停攻 | 当前身份来源bound math/ghost反例、life enter/leave/retire/halfopen/不同damage allocations；native comparator pending |
| Night |三heal f27/60秒/RES/artsdodge、卡2+DP5/cap0/taunt/healfree/drop/death/cool20 |13当前c0来源，enemy-only生产score绑定/真正block/retire/filter；native hidden非tag资格，固定12/0-10无隐匿来源时不虚扩wholegameblocker |
| Weedy |33/3.5AoE、push表/实际ledger1200/EXTEND/tail、炮DP5/20秒/CD35/f1/SP3秒/owned联动 |10当前c0来源；空目标explicit pays/no-forward profile、nativeforward/invalid/physics曲线待client，不升完整native |

本关脚本确实deploy Myrtle/Bagpipe/Exu/Ptilo/Saria/Eyja，12人deck没有换成六人。旧full0-10报告的accepted commands明确各技能请求；Exu AUTO没有显式skill命令，必须另从其AUTO cost/ability与五packet事件证明。编队存在、accepted command或总35kill均不能填满上表。

## 源链与非阻断pending

当前source chain为native关卡/敌 pin→normalized官方配置与frozen roster→各skill/talent raw子集/reader identity→base unit→integrated squad→M7空间/朝向→Saria/Lisk receiver修订→enemy targeting v2→M10 exact resource fields。每层sourceSHA与builderSHA已保留，审计JSON逐operator列其两个recipe/talent包SHA。要签complete model，还需可重复复建与实际资产/表/锁hash匹配，不只信包内metadata。

字段确有数学消费者时，未知native方法体可以保留client_pending：Ptilo fixed cadence、Eyja随机count绑定/clock、Kalts profile64比较器、三token外部版本、native force/collision/动画缩放、headless STORY暂停与UI映射等。旧flattened pending把跨operator模块标签抄到每行，不能据此宣称当前实现缺失。M7非零放置、8邻接/no-corner/steering/rotate/own-blocked与M10 offset（0-10无非零checkpoint offset）已经有显式数学实现。

dynamic taunt modifiers的score adapter仍在wrapper model_gaps，但固定12当前没有任何改变taunt_level的Buff，bird常量1已被enemy profile消费；不能把该通用扩展当本场必需数学阻断。另一方面Myrtle真实旧link与半格投影不一致不能降成client_pending。未发现其余固定选技/人才被普通真伤placeholder替代。

## 足以给首个complete model收据的最小余项

1. 以新独立M11/M12修两个真实数学缺口，保留本c0失败；所有改动后封新core/content身份。复核必须继续包含command0、held、已cast/launch政策、corner/方向/own-blocked边界。
2. 当前身份重验上表12闭包。可复用冻结21+13+10+15场景，但source/helper/test SHA、PACKAGE环境和实际collect范围必须锁定；六个已部署者补actor/ability事件数值、资源、RNG、伤害/治疗/状态时刻。每个required机制有独立expected和事件范围，不靠victory。
3. 新完整首关脚本连续/分段/checkpoint/replay胜利及35spawn/5enemy/kill-leak-remaining守恒、控制消费/input-lock/legalcommands证据。保存真实退出与最终文件hash；运行中的False不作failure或pass结论。
4. 正式转换builder补campaign namespace、固定源/配置/hash、12选技映射、source字段检查及mechanic_tests；把已明确数学模型与client待证逐条类型化。不得直接清空旧pending数组或把native_fields_verified解释为客户端已证明。
5. 将当前真实test evidence/export schema与所审input_identity对齐，再由独立审阅者签外部review。当前progress正规路径/receipt仍缺，当前模型探索路径不能靠改metadata自行升级；0-1只作底座回归。正式计数继续0/36。
