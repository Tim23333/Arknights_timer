# M6 0-10 内容与十二人闭包只读复核

2026-10-02。本轮只新增本文档；没有新增/修改测试、源码、已冻结的攻击侧四文件或 M6 kernel
复核文件。使用现有 builder 的 `--check`、独立读取和内存中的 Compiler/Engine 定向操作。
本报告不是审批收据，也不将编译成功或短模型执行视为正式关卡通过。

## 实际发现并验证的内容修复

| 问题 | 初始证据 | Root 修复后独立确认 |
| --- | --- | --- |
| enemy massLevel 遗漏 | native `enemy_1030_wteeth` 真实 massLevel2，转换后的五种敌人都缺 mass_level，会错误影响温蒂推力/距伤。 | 最终 wteeth mass_level2，另四种0，保留实际敌人重量。 |
| 支援 pending 丢失 | squad 只读 talent metadata.pending，support 使用 pending_mechanics；八条支援明确缺口没有进入对应单位记录。 | 兼容两种字段，六名支援侧正式单位的 integration records均保留这些缺口。 |
| 旧 Mon3tr 召唤少付 DP | old ability 无 activation.costs，仅 on_start DP delta-10；battle DP5 被 clamp0，召唤实际成功且无 rejection，native token cost10。 | authoring 将无条件 plain负DP提升为 battle activation cost10，原行保留 metadata，spawn认领真实10。独立实跑 DP5拒绝/无token/DP5保持；DP10成功/DP0/token paid_cost10。原 skills.kalts未改。 |
| native options/seed 审计记录缺失 | 最终模型仅保留部分执行映射和源 SHA，缺完整原始 options及 randomSeed记录；不能称所有 options已转换。 | 最终 metadata.native_options逐字段等于锁源，native_random_seed953816614保留，并明示 seed角色、spawn jitter、diagonal/steering pending。 |

这几项是内容/审计闭包修复，Core implementation identity保持原冻结状态；修正前短测内容 SHA
不能被当成修正后同一内容的结果。

## 原生关卡数据对照

源：`packages/campaign/native_reference/level_main_00-10.json`，固定 public commit
`56aee3d6c5a29c3a0d192456d70d14252cbb0804`。独立逐项断言而不是只计总数：

| 数据域 | 实际内容及保留范围 |
| --- | --- |
| Spawns | 35次：gopro14、mob5、wteeth2、slime12、yokai2。全部敌人 key、route index、wave/fragment index、逐次绝对时间与独立展开的 native动作相等。 |
| Map | 9×13=117瓦片。逐格 tileKey、buildable mask、passable mask、height、blackboard、effects与 native palette展平结果相等。当前 keys为empty/end/flystart/forbidden/road/start/wall；没有将特殊瓦片伪装floor。原 blockEdges/tags均None，无当前非空字段遗漏。 |
| Routes | 17条被 SPAWN 引用的原生 route（1..9、11..18）在35个实例里完整保留。除声明的 native row→8-row轴转换外，start/end/checkpoints/time/motion/全部flags均逐字段相等；route18保留FLY。 |
| Unused/preview routes | native总19条。route10仅用于enemy-info preview，原始路线完整放入控制payload；route0是未被SPAWN引用的合法E_NUM占位，仍在锁源原JSON中，不将它伪称为实现了WALK。 |
| Runes | 三条FOUR_STAR rune在NORMAL1不适用，原记录保留在 inactive_native_runes。当前无applicable rune，不是删除真实生效效果。 |
| Predefines/branches | characterInsts/tokenInsts/characterCards/tokenCards四集合均空；hardPredefines、branches为None，globalBuffs/extraRoutes/enemies/tilesDisallowToLocate为空，excludeCharIdList/operaConfig/cameraPlugin为空或None。当前没有需要执行却被跳过的实体/分支。 |
| Options | 完整原 options保留metadata。运行已映射characterLimit8、life10、DP初始10/max99/每秒1、moveMultiplier.5；剩余字段不能被称为全部实现。 |
| Seed/motion assumptions | native randomSeed953816614保留metadata，不假称等于当前Kernel imp流种子或算法。spawnRandomRange=.2、allowDiagonalMove=true被保留在routes；当前运行仍是明确的无出生jitter/网格WALK/直线FLY模型，native steering、diagonal与random-seed binding pending。 |

单wave的 maxTimeWaitingForNextWave=-1，无后续wave；advancedWaveTag为空，五个fragment preDelay
为0/0/0/10/12。当前所有control/SPAWN action的 blockFragment=false。
模型没有为未知的生效控制 gating补默认实现。

## Controls 与可执行边界

原生 control为 STORY1、DISPLAY_ENEMY_INFO1，分别模型时间0和49秒。
Story资产来自本地 `hot_raw/main_00-10.dat`，name/length/padding/SHA与reference严格核对；原脚本
序列 HEADER、三条PopupDialog、Blocker五条命令逐条保存参数字符串与正文并产生observable events。
不支持的命令会报错。

`headless_ack_zero_game_time_v1` 显式在同一个逻辑tick里锁输入、输出story事件、ack、解锁。
它保留可审计的控制事件，不模拟native UI墙钟时间或客户端pause/input callback先后。
enemy-info action保留route10原始preview。control model `client_validated=false`、
`formal_stage_approved=false`；没有把完整UI实现状态补成True。

## 十二人天赋/所选技能闭包

最终 squad恰有十二个真实 roster单位和三个真实依赖实体（Mon3tr、水炮、鸟笼），没有混入
support_enemy/injured等 fixture实体，也没有token_leave/token_enter/aura_leave/aura_enter诊断能力。
独立比较十二人的HP、ATK、DEF、RES、攻击间隔、block、deploy cost、mass与规范化模型端点，
均相等。这里确认固定配置数据保留，不宣称规范化rounding已经通过客户端校准。

每个 selected_skill_ability都实际属于对应正式单位；六人 attack patches和六人 support patches
分别真正进入初始Buff、能力、规则、layers、deck及token依赖。Compiler解析全部实际引用，
没有靠 metadata中的技能名称代替所有权。

- 陈/雷蛇携带 `sp:attack_or_damage`，未加time_sp；十名时间型所选技能携带time_sp，使用
  support_time_sp和sp_recovery层，保留原SP容量/初始/周期/owner gate/freeze配置。
- Ptilopsis/Lisa的SP aura在正式单位上具有正确来源和职业tag；收件人新规则/layers实际接入，
  不是仅留在独立fixture中。敌人接入sluggish/fragility属性层和规则闭包。
- Ptilopsis/Nightingale普通自动攻击条件为mode0，持续技能治疗条件为mode1；Exu/Bagpipe/Eyja
  同样保留普通/技能模式互斥。独立遍历每单位mode0/1的实际 activation条件，普通自动clock
  每模式最多一条；陈明确replacement另列，不被当成重复普通攻击。
- Eyja旧名称含probe的能力已是automatic/auto_only随机模型；名称不能被误读为仍可玩家强发，
  也不能掩盖native first signal/max target绑定未验证的pending。
- Owned summons要求显式部署payload，无旧固定坐标/朝向。水炮、Mon3tr、鸟笼分别认领对应
  实际DP付款；三实体的来源、生命周期与已知callback/version缺口保留。

十二名单位均 `complete_operator=false`，`all_talents_complete=false`、
`native_attack_clock_verified=false`，squad `complete_operator_count=0`。
旧技能来源的partial证据与新talent/source pending一起保留；编译成功没有清掉native缺口。

## 实际检查与状态

三个 builder `--check`成功：control、squad、mainline model。
内存中的独立对照断言确认35次时点/key/route/checkpoint/flags、117格、12单位端点/所有权/模式。
最终 Compiler通过，**230 definitions、65 rules**，program fingerprint：
`34590db1a3b69d957c61b9b41389e8ac62c68e66db618669464e15c9281e8cd6`。
DP5/DP10的Mon3tr用例均用真实Compiler/Engine和现有模型执行，没有另写测试或fake handler。
本轮没有执行完整0-10胜利/全事件回放，所以仍保留 independent_full_stage_review_and_execution。

读取 `validation/campaign/progress.json` 时：targets36、decoded36、core_reference_verified36、
partial_model_files_present1，**accepted0、client_verified0、model_passed_pending_review0**。
可执行partial模型和正式0/36是不同状态。

| 最终复核内容 | SHA256 |
| --- | --- |
| `tools/build_mainline_control_model.py` | `e84aed42cb2f41696054321e294cb89b04522605ce75797c8fffd0a543239b5d` |
| `tools/build_mainline_model.py` | `f215650f70e6715dda8b30aadbd611e6ba83be5dbcc7e3c90560bb4289091fa5` |
| `tools/build_campaign_squad.py` | `933bff907f0f55f0ad27aee65ed33dfc9d76420b63031bd6f2cc51376490c312` |
| `packages/campaign/controls.00_10.model.json` | `a3ca777cc428bb439cd83e4f2e08154e2dc240a64345e255cafc8f776832f219` |
| `packages/campaign/squad.integrated.json` | `8b7d03266357f34e1842b24959aec6565cd296add5b83ebe99f6893ce74666c5` |
| `packages/campaign/mainline_models/level_main_00-10.json` | `6a0971d198ca89046ecb77387d9f2adc6786aea8b80c3fb8bd87ac9d7b667ee4` |

任何后续内容改动应采用新的package身份；不得将修正前短测重标为这些SHA通过。
