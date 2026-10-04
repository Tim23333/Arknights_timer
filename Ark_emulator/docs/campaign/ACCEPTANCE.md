# 十二人 / 三十六关验收质量门与独立复核

2026-10-03当前门以用户最新要求为准：固定12人、基地99999（单位真实HP不改），先按此前参考网站／固定表／资产完成完整仿真，用户交付后统一实机反馈。模型/参考一致性与客户端对照分别记录；未知native方法体不单独阻断开发，但缺必需实现、错误字段、真实同帧漏洞、未完成36关过程仍不通过。以下开篇目录与失败数是首次历史复核；实际最新候选、修复范围与运行状态见[CURRENT_STATUS.md](CURRENT_STATUS.md)，不能按旧摘要把现已实现机制重新列为全部缺失。

首次独立复核于 2026-10-02 完成。本复核读取 V2 和 mainline_catalog 产物，
使用真实 `Compiler`、`Engine`、调度器与结算路径运行独立预期，未调用 V1，未使用空 handler。
首次只读复核没有修改 `ark_sim`。首次新增测试暴露阻断：
`tests_v2/test_campaign_acceptance.py` **15 failed、2 passed，0.86 秒**。
这些测试保持正常失败，未用 xfail 或跳过掩盖；后续定向修复结果见文末，历史失败保留为发现证据。

目录现有十八章、每章最后两关，共三十六关，选择状态均为 not_imported / not_validated。
全部三十六关仍有原始路线几何/运动模式缺口，尚不能作为章节闭环执行输入。
目录中可用来源和依赖摘要是导入准备证据，不是完整关卡模型。
本轮未复核由同一复核者编写的 roster 工具，队伍构建测试不充当独立运行验收。

每个机制和每一关分别记录以下证据，不允许由 victory 推导其他栏通过：

| 证据层 | 合格证据 | 当前解释 |
|---|---|---|
| 声明 | 内容 ID、原始依赖、能力/规则契约及来源身份 | 契约存在或技能名称只说明需求存在 |
| 实现 | 实际编译绑定与执行路径，缺失/未知内容明确拒绝 | 无空 handler、无降级、无静默剥离 |
| 事件见证 | 运行产生目标明确、时刻明确的关键事件 | 不能以一条 ability.started 代替命中、控制或资源结算 |
| 独立预期 | 不从被测实现计算出的数值/状态/顺序断言 | 手算伤害、SP次数、路径/目标集合、失效与恢复边界 |
| 模型回放 | 同一实现/内容/规则/RNG 身份下连续、检查点恢复、输入回放精确一致 | 确定性不证明游戏语义正确；仍须独立预期 |
| 客户端证据 | 对应固定配置的逐帧对照及差异记录 | 模型通过不能提升客户端状态 |

首批阻断与复现如下。测试名是可直接 `pytest -k` 选择的实际用例。

| 优先级 | 发现与实测结果 | 独立复现 | 需要修改的位置 |
|---|---|---|---|
| P1 | 行为计划不进入运行决策。player_combat 的 move=False 已直接读取确认，但跑30tick后从 col=0 移至≈1；ground_melee 的 attack=False 已确认，但自动攻击使靶子HP100→90 | `test_behavior_move_false_prevents_route_progress` / `test_behavior_attack_false_prevents_automatic_attack` | `ark_sim/domains/behavior.py:25`、`:34`，`ark_sim/domains/abilities.py:231`，`ark_sim/domains/movement.py:114` |
| P1 | `recovery_per_attack=1` 实际按 damage 目标/段数回SP。一次攻击两个目标回2SP，两段两个目标回4SP，独立预期均为一次攻击回1SP | `test_attack_recovery_occurs_once_per_attack_not_per_target_or_hit[1/2]` | `ark_sim/domains/effects.py:44`；攻击生命周期/施放身份需承担一次触发边界 |
| P1 | FLY/E_NUM 原生 motionMode 被编译接受，却未进入路径或阻挡算法。路径提供器只有地面GridTopology；blocking不检查飞行。未知checkpoint999、WAIT_CURRENT_FRAGMENT_TIME(3)、DISAPPEAR(5)、APPEAR_AT_POS(6)也不拒绝 | `test_unimplemented_native_route_semantics_fail_before_execution` 六组参数 | `ark_sim/content/schemas.py:28`、`:305`，`ark_sim/domains/movement.py:128`、`:140`，`ark_sim/presets/providers.py:147`、`:152` |
| P1 | 未实现和未知特殊瓦片静默按passableMask参与普通地面路径。unknown、healing、defup、volcano、telin五种tileKey均被编译接受 | `test_unknown_or_unimplemented_tile_mechanic_is_rejected_instead_of_becoming_floor` 五组参数 | `ark_sim/content/schemas.py` map/route嵌套预检，`ark_sim/domains/spatial.py:52`，特殊瓦片领域处理与能力声明 |

SP用例将一次施放的timeline声明为一次攻击，重复entry为该攻击的多段命中。
如果新内容需要“每段回复”或“每目标回复”，应该另外显式命名触发语义，不能让
`recovery_per_attack` 随目标数变化。十二人中的陈和其他SP相关机制必须分别验证
攻击开始/实际命中、受击、治疗、周期授予、自然回复、满值和施放冻结的具体触发边界。

行为修复必须同时让 move/attack 生效；只在AbilitySystem增加一个判断而不更新行为决策或
让MovementSystem仍忽略决策，不能通过两项独立用例。计划应被当前绑定提供器产生，
并保持事件顺序与检查点恢复一致。不要把测试伪造的runtime.behavior_decision当作完整实现。

原生运动/控制/瓦片用例的当前合理要求是**导入/编译前明确拒绝尚未实现内容**。
本轮没有要求用简化直线运动假装支持飞行，也没有把传送检查点降为普通坐标。
后续如果这些机制有完整实现，可以将相应拒绝用例替换为独立位置、可见性、目标资格、
阻挡、生命与时序断言，同时保留未知枚举的拒绝用例。

本地三十六关依赖说明这些门是实际需求：motionMode出现 FLY 88 条、E_NUM 105 条、缺失977条；
checkpoint出现 WAIT_FOR_SECONDS 635 条、WAIT_CURRENT_FRAGMENT_TIME 70 条、DISAPPEAR与APPEAR_AT_POS各64条。
特殊瓦片首次出现的目录例子为：1-12传送入口/出口、2-9坑洞、2-10治疗地板、3-8防御地板、
4-9火山、JT8-2感染瓦片、9-18强推力地板、11-19约束围栏、15-20特殊敌人出生瓦片。
这些是本地解析输入的统计，解析缺口未修复前不能当作准确客户端路线数。
控制动作还包含 ACTIVATE_PREDEFINED、BATTLE_EVENTS、DIALOG、STORY 等，必须逐项分配
导入语义或明确的经审核“不影响战斗”理由；不能因为不是SPAWN就丢弃。

两项当前通过的独立门：

- `test_multitarget_damage_has_two_independent_settlement_witnesses`：两目标HP各100→90，
  并恰有两条目标集合正确的 `damage.accepted`。这只证明这个合成场景的双目标真伤结算。
- `test_selected_catalog_does_not_claim_execution_or_client_evidence`：三十六关跨十八章，
  保持未导入/未验证状态并保留运动模式缺口。它只检查诚实状态，没有运行关卡。

复现命令：

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_acceptance.py -q --tb=short
```

后续每关记录应至少含 source/config/program/runtime/rules/RNG 身份、依赖门状态、
固定队伍与实际命令、波次和控制动作消费计数、未知/拒绝列表、击杀/漏怪/结局、
被验证机制对应事件范围、独立预期和回放比较。未运行的关卡保持待导入或阻断，
不能用0-1旧证据、合成场景通过数或一场胜利填满三十六关机制矩阵。

## 定向修复后的质量门

2026-10-02 root派发空间预检修复后，复核者只修改
`ark_sim/content/schemas.py` 并新增 `ark_sim/content/spatial_validation.py`。
root同时修复行为与SP运行路径。原有独立预期没有放宽；新增十六项用例覆盖
五种实际route入口、未引用scenario.routes库存、四种WAIT枚举实际执行、名称和值矛盾、
错误位置/地图边界、负等待时间和布尔等待时间。

空间预检当前支持WALK=0、MOVE=0与WAIT_FOR_SECONDS=1，兼容基础输入省略/null默认值；
合法WAIT字符串或仅名称对象在编译器的复制内容上规范为整数，真实运行产生同一movement.wait事件。
FLY、E_NUM、未知检查点和未实现原生控制检查点明确拒绝；不把FLY伪装成地面运动。
验证entity.spatial.route、initialEntities.route、waves.route以及instance components override中的route。
未引用scenario.routes可以保留原始placeholder，不能据此声称它已执行。
基础瓦片允许floor/road/wall/forbidden/start/end/empty，未知和未实现特殊瓦片拒绝。
没有新增可以把原生特殊瓦片声明为普通几何的绕过字段。

定向验证：acceptance、既有content、spatial、ark_import测试合计 **151 passed，2.28秒**。
`python -m ark_sim validate packages/ark_content/level_main_00_01.json` 成功，69个定义、40条规则。
这确认现有0-1仍可编译，不是新实现的0-1回放/客户端通过证据。
源码改变后旧模型报告的runtime身份不再代表当前实现；root需要重新生成0-1验证与回放身份。
