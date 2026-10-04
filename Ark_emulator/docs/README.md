# ArkSim 文档索引

当前运行与开发入口是独立 V2 包 `ark_sim`。单位、技能、Buff 与状态图由内容组合，数值和算法由可替换规则集执行。明日方舟预设接入同一底座；首个官方基线为 0-1，内容覆盖按关卡推进。

先阅读实际运行和作者指南，再查阅架构与需求。设计中的契约清单与历史实现覆盖记录都不能单独证明运行能力或游戏准确性。模型验证和真实客户端对照分别记录。

## 实际运行与内容创作

| 文档或内容 | 用途 |
|---|---|
| [项目 README](../README.md) | V2 主入口、CLI 编译、运行、回放和 Python API |
| [SIMULATION_LOGS.md](SIMULATION_LOGS.md) | 固定 E 盘日志目录、清理脚本、完成后自动清理及摘要保留政策 |
| [V2_IMPLEMENTATION.md](V2_IMPLEMENTATION.md) | 实际模块边界、运行接口、原子性、回放、调试轨迹与当前限制 |
| [V2_AUTHORING.md](V2_AUTHORING.md) | 实际内容字段、局部规则、周期恢复、技能、Buff、状态图、计算图、提供器、Builder 与 CLI |
| [campaign/GOAL.md](campaign/GOAL.md) | 当前持续目标：固定12人覆盖模块，第0–17章末两关共36个目标，阶段与验收条件 |
| [campaign/CURRENT_STATUS.md](campaign/CURRENT_STATUS.md) | 当前生产/候选身份、真实完成与进行中运行、canonical见证及下一章执行范围 |
| [campaign/CHAPTER09_LINKED_PACKETS.md](campaign/CHAPTER09_LINKED_PACKETS.md) | 持续连接的独立生命/元素包、移动与命中两时钟及候选验证范围 |
| [campaign/CHAPTER09_BATCH_PROGRESS.md](campaign/CHAPTER09_BATCH_PROGRESS.md) | 第9章必需机制的实际证据、隔离候选和完整关卡剩余依赖 |
| [campaign/CHAPTER09_PILLAR_PAYLOAD.md](campaign/CHAPTER09_PILLAR_PAYLOAD.md) | 四方向倒塌、HP100碎石及真实柱伤跳过石像鬼复生的验证范围 |
| [campaign/CHAPTER09_FLAME_CLOCKS.md](campaign/CHAPTER09_FLAME_CLOCKS.md) | 可替换能力冷却／中断动作及焚毁者10.6／6／10秒施法时钟原型 |
| [campaign/CHAPTER08_FOUNDATION_V5.md](campaign/CHAPTER08_FOUNDATION_V5.md) | 通用事务副本、波次追踪与原子反应联合底座，JT8-2／JT8-3新整关输入和独立证据 |
| [campaign/CHAPTER07_FOUNDATION.md](campaign/CHAPTER07_FOUNDATION.md) | 第七章所需地形资格、共享光环与复活等待动作的隔离候选接口和验证边界 |
| [campaign/CHAPTER07_PREDEFINES.md](campaign/CHAPTER07_PREDEFINES.md) | 源石祭坛、地雷库存／费用及教程控制的局部消费者与待核对参考规则 |
| [campaign/FINISH_TIMELINE_WAVE_DESIGN.md](campaign/FINISH_TIMELINE_WAVE_DESIGN.md) | 保留实际演员、出生和延迟的显式当前波次完成请求原型 |
| [campaign/SCENARIO_CARDS_AND_AREA_PROJECTION.md](campaign/SCENARIO_CARDS_AND_AREA_PROJECTION.md) | 固定编队之外的有限装置卡片、自定义范围当前状态输入及动态运动同步候选 |
| [campaign/CHAPTER07_EXECUTION.md](campaign/CHAPTER07_EXECUTION.md) | 7-17与7-18原始输入、固定12轮换、真实装置卡片、生命覆盖和全程验证任务 |
| [campaign/CHAPTER08_EXECUTION.md](campaign/CHAPTER08_EXECUTION.md) | JT8-2／JT8-3原始源闭包、普通敌人／Boss消费者分派、环境与控制准入门 |
| [campaign/CHAPTER06_EXIT_ACCOUNTING.md](campaign/CHAPTER06_EXIT_ACCOUNTING.md) | 第六章特殊出生选项、真实退出与战斗死亡分开记账、可替换规则及隔离验证范围 |
| [custom/buff_application_example.json](../packages/custom/buff_application_example.json) | 可运行自定义技能／Buff／时长表达式例子，参数改动不需要内核专用分支 |
| [campaign/REFERENCE_FIRST_DELIVERY.md](campaign/REFERENCE_FIRST_DELIVERY.md) | 当前先按参考网站/固定数据完成仿真，用户交付后实机反馈，开发缺口与反馈项分列 |
| [campaign/CHAPTER02_STAGE_COMPOSITION.md](campaign/CHAPTER02_STAGE_COMPOSITION.md) | 第二章精确敌人/地形/控制闭包、完整输入与真实失败及修订身份 |
| [campaign/EXTENSION_AUTHORING.md](campaign/EXTENSION_AUTHORING.md) | 新候选可替换请求、地形接触/field和模块组装入口，实际支持版本说明 |
| [campaign/M47_REENTRY_INTEGRATION.md](campaign/M47_REENTRY_INTEGRATION.md) | 光环回调重入修复的新组合、187检查/独立peer/首关基线与2-9执行身份 |
| [campaign/INTERMEDIATE_ACCURACY.md](campaign/INTERMEDIATE_ACCURACY.md) | 基地99999目标的实际中途数据比较、版本/时间/字段覆盖与未验证边界 |
| [campaign/M26_DECISION_ELIGIBILITY_INTEGRATION.md](campaign/M26_DECISION_ELIGIBILITY_INTEGRATION.md) | 敌人决策和目标资格合并、真实测试与候选身份 |
| [campaign/M2_PROGRESS.md](campaign/M2_PROGRESS.md) | 标准单位输入、首个技能原型、事件资源、飞行与最新基础回归 |
| [campaign/PRIMITIVES_PROGRESS.md](campaign/PRIMITIVES_PROGRESS.md) | 五份partial技能组合、同步启动/控制契约及0-10未完成依赖草稿 |
| [campaign/BASE_UNITS.md](campaign/BASE_UNITS.md) | 十二人真实养成基础模型、九份普攻、动态目标上限及三项缺失证据 |
| [campaign/ENEMY_ATTACKS.md](campaign/ENEMY_ATTACKS.md) | 0-10四种敌人的原生combat攻击转换与被动飞行单位 |
| [campaign/AURA_UNITS_PROGRESS.md](campaign/AURA_UNITS_PROGRESS.md) | 十份partial选技、连续光环、基础单位与首关敌方攻击的当前进展 |
| [campaign/SQUAD_INTEGRATION.md](campaign/SQUAD_INTEGRATION.md) | 当前12份选技与实际编队、召唤、范围弹道、位移真伤、资源持有者与时间曲线整合 |
| [campaign/M6_PROGRESS.md](campaign/M6_PROGRESS.md) | 当前十二人两侧天赋、默认召唤资源、通用随机/伤害/部署/控制接口和0-10 partial模型 |
| [campaign/M7_PROGRESS.md](campaign/M7_PROGRESS.md) | 新空间采样/路径/转向、资源容量策略、方向转换与首章全程；0-11明确等待新时钟机制 |
| [campaign/M8_PROGRESS.md](campaign/M8_PROGRESS.md) | 动态wave/fragment、deadline等待、trace共享、1002项回归与首章长程验证 |
| [campaign/M8_DAMAGE_AND_ROSTER_REPAIRS.md](campaign/M8_DAMAGE_AND_ROSTER_REPAIRS.md) | 当前canonical伤害绑定修复、两层防御SP、输入版本与新整合见证 |
| [campaign/M8_ENEMY_TARGETING.md](campaign/M8_ENEMY_TARGETING.md) | 敌方生产score接入Bird嘲讽、被阻挡优先、独立反例与动态属性边界 |
| [campaign/CANONICAL_TRIO_WITNESSES.md](campaign/CANONICAL_TRIO_WITNESSES.md) | 陈/雷蛇/铃兰21个canonical配置机制见证、源字段与明确未闭合策略 |
| [campaign/CANONICAL_SUMMON_WITNESSES.md](campaign/CANONICAL_SUMMON_WITNESSES.md) | 夜莺13/温蒂10独立机制及M10资源原失败复核、凯尔希剩余范围 |
| [campaign/CHAPTER01_EXECUTION_PLAN.md](campaign/CHAPTER01_EXECUTION_PLAN.md) | 下一章实际出生/预定义/Boss/路线/EMP依赖的具体组合和执行顺序 |
| [campaign/CHAPTER01_STAGE_COMPOSITION.md](campaign/CHAPTER01_STAGE_COMPOSITION.md) | 第1章源保留组装、1-11开场CP/回放、1-12传送格明确拒绝与剩余依赖 |
| [campaign/M16_TERRAIN_OVERLAY.md](campaign/M16_TERRAIN_OVERLAY.md) | 装置拥有的地形层、部署/寻路/退场接口、候选与独立补充检查 |
| [campaign/M20_DORMANT_IMPLEMENTATION.md](campaign/M20_DORMANT_IMPLEMENTATION.md) | 持久休眠实例、同ID激活、目标/来源隔离与真实NPC容量/SP消费 |
| [campaign/M21_INTEGRATION.md](campaign/M21_INTEGRATION.md) | 地形/传送/投射物/休眠组合、跨模块反例与当前验证状态 |
| [campaign/M22_RANGED_PROJECTILES.md](campaign/M22_RANGED_PROJECTILES.md) | 投掷者与NPC弩箭的实际源、持续追踪、命中时采样和独立回放 |
| [campaign/M23_ROSTER_BOUNDARY.md](campaign/M23_ROSTER_BOUNDARY.md) | 原生教学卡部署控制、固定12显式覆盖、公开部署成员约束与独立预期 |
| [campaign/RUNTHROUGH_99999.md](campaign/RUNTHROUGH_99999.md) | 最新全程/基地99999目标、单位HP不改、允许漏怪与实际准确性门 |
| [campaign/CHAPTER01_PORTAL_SOURCE_AUDIT.md](campaign/CHAPTER01_PORTAL_SOURCE_AUDIT.md) | 四传送格与八实际路线/九隐藏出现对的源审计、声明策略边界 |
| [campaign/CHAPTER02_DEPENDENCY_PREVIEW.md](campaign/CHAPTER02_DEPENDENCY_PREVIEW.md) | 第2章52/36次出生与无人机/术师/碎骨的源依赖预览 |
| [campaign/FIRST_MODEL_ACCEPTANCE_SCOPE.md](campaign/FIRST_MODEL_ACCEPTANCE_SCOPE.md) | 首关七门、历史标签/实际模型缺口/客户端待核对分类、未部署六人见证要求 |
| [campaign/C0_FIRST_MODEL_ACCEPTANCE_MATRIX.md](campaign/C0_FIRST_MODEL_ACCEPTANCE_MATRIX.md) | 当前c0/M10逐角色与源链独立审查、两个真实数学缺口及首关收据最小余项 |
| [campaign/CHAPTER01_SOURCE_AUDIT.md](campaign/CHAPTER01_SOURCE_AUDIT.md) | 1-11/1-12真实依赖、W/EMP/剧情/预定义/路线源闭包 |
| [campaign/CHAPTER01_ATTACK_MODELS.md](campaign/CHAPTER01_ATTACK_MODELS.md) | 潜行者分伤与两个投掷者的显式可替换模型、26项独立反例 |
| [campaign/CHAPTER01_W_MODEL.md](campaign/CHAPTER01_W_MODEL.md) | 历史W模式/C4子集；后续普通攻击组合及剩余回调边界见W_COMBAT |
| [campaign/CHAPTER01_W_COMBAT.md](campaign/CHAPTER01_W_COMBAT.md) | W普通攻击＋HP/C4子集、两种发包profile、退场与回放；附着回调仍待闭合 |
| [campaign/CHAPTER01_PREDEFINES.md](campaign/CHAPTER01_PREDEFINES.md) | 原生E0LV20安德切尔的源、真实属性/普通攻击、卡组与激活依赖 |
| [campaign/CHAPTER02_SOURCE_AUDIT.md](campaign/CHAPTER02_SOURCE_AUDIT.md) | 第2章16variant/9简单攻击源审计及光环/碰撞/碎骨冲突 |
| [M6完整V2测试](../validation/campaign/m6_final_tests_20261002.json) | 历史885项全过、核心与测试身份稳定；后续内容修复另外定向验证 |
| [M7完整V2测试](../validation/campaign/m7_postcompat_final_tests_20261002.json) | M7兼容修复后948项全部通过，原17失败日志独立保留 |
| [M8完整V2测试](../validation/campaign/m8_final_tests_20261002.json) | 历史M8冻结1002项全部通过，当前M10主路径完整回归另验 |
| [当前M10主目录完整V2测试](../validation/campaign/m10_primary_full_tests_20261002.json) | 当前c0源码1132项全部通过，固定新内容输入与实现身份独立记录 |
| [当前M10主目录基线](../validation/campaign/m10_primary_baseline_20261002.json) | 同身份0-1清场、CP/命令回放、自定义850/60规则全部通过 |
| [后续首关内容检查](../validation/campaign/m6_post_review_stage_checks_20261002.json) | 新3项源/成本反例与受影响套件共13项通过，不重标完整测试次数 |
| [M6的0-1回归证据](../validation/campaign/m6_final_baseline_20261002.json) | 历史核心11击杀零漏怪，检查点/回放181,638事件一致 |
| [M7的0-1回归证据](../validation/campaign/m7_postcompat_final_baseline_20261002.json) | M7身份11击杀零漏怪，检查点/回放181,808事件一致 |
| [M8的0-1回归证据](../validation/campaign/m8_final_baseline_20261002.json) | M8身份11击杀零漏怪，检查点/回放181,808事件一致 |
| [M6的0-10短程证据](../validation/campaign/m6_final_00_10_probe_20261002.json) | 历史20秒2击杀零漏怪、3命令接受、出生守恒、66,066事件检查点/回放一致 |
| [M8原0-11全程探索](../validation/campaign/m8_00_11_full_exploratory_20261002.json) | 原内容37出生/37击杀/零漏怪/12命令接受；no-replay探索，修订内容另验 |
| [M8测试审核格式](../validation/campaign/m8_final_tests_review_format_20261002.json) | 重验原1002项执行日志与61原测试模块身份后导出兼容证据；不是转换批准，不包含后来新测试 |
| [M5历史782例覆盖证据](../validation/campaign/m5_final_tests_20261002.json) | 历史全套781通过/1过期断言失败，修正后的8例依赖复核通过；保留原非零日志与旧身份 |
| [前一阶段665项检查证据](../validation/campaign/m4_boundary_final_tests_20261002.json) | 保留其原核心身份的历史阶段证据，不代表最新运行版本 |
| [campaign/ACCEPTANCE.md](campaign/ACCEPTANCE.md) | 源、独立预期、事件见证、模型与客户端证据的分层质量门 |
| [主线进度](../validation/campaign/progress.json) | 解码、参考验证、内容转换与运行状态分别统计，历史结果独立保存 |
| [可运行自定义内容包](../packages/custom/custom_guard.json) | 同一单位和技能采用标准或自定义规则集的合成场景 |
| [0-1 V2 内容包](../packages/ark_content/level_main_00_01.json) | 固定提取数据转换后的首关输入；验收和校准状态需结合证据 |
| [0-1 固定部署操作](../scenarios/level_main_00_01/commands.json) | 部署时序、位置、朝向和实例别名 |
| [运行时计算契约](../ark_sim/rules/contracts.json) | 随运行时保存的类型与计算接口；具体必需能力由编译预检判断 |
| [V2 模型验收记录](../ark_sim/validation/reports/v2_baseline_20261002.json) | 0-1 清场、检查点续跑、完整事件回放及两套自定义数值规则 |
| [V2 测试证据](../ark_sim/validation/reports/v2_tests_20261002.json) | 2026-10-02 的 332 项 V2 测试、运行日志与源码摘要 |

在模拟器目录运行：

```powershell
..\.venv\Scripts\python.exe -m ark_sim validate packages/custom/custom_guard.json
..\.venv\Scripts\python.exe -m ark_sim explain packages/custom/custom_guard.json --output dependencies.json
..\.venv\Scripts\python.exe -m ark_sim run packages/custom/custom_guard.json --seconds 1 --output snapshot.json --replay-output replay.json
..\.venv\Scripts\python.exe -m ark_sim replay packages/custom/custom_guard.json --record replay.json --output replayed.json
```

CLI 的实际子命令为 `validate`、`explain`、`preview`、`run`、`replay`。`--replay-output` 导出记录，`replay --record` 按锁定的程序身份、种子、时间与操作重放。Python API 同样提供 `ark_sim.tools.replay.replay()`。

## 当前需求与架构

| 文档 | 内容 |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | 自定义内容、可替换规则、全量底层重构与当前验收要求 |
| [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) | 独立内核、通用领域、规则运行时、内容编译与扩展边界 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构入口与历史设计存档 |
| [LEVEL_00_01_PLAN.md](LEVEL_00_01_PLAN.md) | 0-1 基线、内容与操作范围、实施及验收计划 |
| [V2_RULE_CATALOG.json](V2_RULE_CATALOG.json) | 设计时的计算与策略清单；运行状态以当前实现为准 |
| [V2_DEV_INTERFACES.md](V2_DEV_INTERFACES.md) | 并行开发阶段的共享接口约定 |
| [CUSTOM_CONTENT_V2.md](CUSTOM_CONTENT_V2.md) | 初始创作设计说明；实际字段与用法以作者指南为准 |
| [初始内容设计样例](v2_examples/custom_guard.json) | 架构设计时的机器可读样例；可运行维护版位于 packages/custom |
| [REFERENCES.md](REFERENCES.md) | 用户提供的数据、工具与机制参考入口 |

## 阶段一与历史审计

V1 与阶段一已标记为历史实现，仅用于离线数据提取和代码、行为样本参考，后续开发统一使用 V2。
下列资料保留已有代码、行为样本、机制推测和历史回归记录。它们不属于新版运行路径，也不能作为当前 `ark_sim` 全游戏内容覆盖或真实数值还原的结论。

| 文档 | 内容 |
|---|---|
| [V1_HISTORY.md](V1_HISTORY.md) | V1 历史目录、数据提取边界与 V2 开发和验收约定 |
| [MODULAR_IMPLEMENTATION.md](MODULAR_IMPLEMENTATION.md) | 阶段一模块化原型的运行与测试说明 |
| [SIMULATION_COMPLETENESS_REVIEW.md](SIMULATION_COMPLETENESS_REVIEW.md) | 2026-10-01 旧代码审查、回归与完整模拟差距评估 |
| [review_evidence_20261001.json](review_evidence_20261001.json) | 当次审查的数量基线、最小复现和失败条目 |
| [MECHANICS.md](MECHANICS.md) | 旧实现的机制记录、证据标记和待实测项 |
| [DELIVERABLES_AUDIT.md](DELIVERABLES_AUDIT.md) | 历史需求与证据审计、改动记录 |
| [TEST_SCOPING.md](TEST_SCOPING.md) | 旧测试的定向回归策略 |

新底座验证运行 `python -m pytest tests_v2 -q`。新增内容应同时保存采用的包、规则、提供器和数值配置，并补独立预期；新增关卡只提升经过相应验收的组合。
