# 固定十二人参考队伍

这份队伍是主线逐章回归的固定输入选择，当前状态为 **`source_frozen_only`**。
它不是可交给 Compiler 的内容包。十二人尚未完成 V2 导入、机制模型验收或客户端对照，
因此参考包中的 `runnable`、`v2_imported`、`model_validated`、`client_validated` 均为 false。
选人兼顾常见机制和推进主线的输出、阻挡、费用、治疗，但不会把选出强力队伍当作通关证据。

所有章节保持同一养成和技能：精英二阶段、70 级、潜能一（原始 `potential_rank=0`）、
信赖 100%、技能七级加专精三（skills.levels 零基索引 9）、无模组（equipment_id=null）。
桃金娘精二等级上限正是 70，其他十一人也允许此等级。
构建工具按真实 phases.maxLevel、initialUnlockCond 和 specializeLevelUpData.unlockCond 验证等级与技能解锁；
信赖的属性映射、有效属性成长和实际普攻还需要 V2 转换后的独立数值验收。

| 顺序 | 干员与真实 ID | 固定技能 ID | 来源支持的机制需求、通关用途 |
|---|---|---|---|
| 1 | 桃金娘 `char_151_myrtle` | `skchr_myrtle_2` | 周期 DP、周期单体治疗、技能停止攻击/阻挡变化；启动费用 |
| 2 | 风笛 `char_222_bpipe` | `skchr_bpipe_3` | 物伤三连击、击杀 DP、撤退返初始费用、编队先锋初始 SP、概率额外目标；早期输出 |
| 3 | 陈 `char_010_chen` | `skchr_chen_1` | 攻击回复 SP、自动下次攻击、眩晕、双击普攻、周期授予攻击/受击 SP、物闪；接敌控制 |
| 4 | 雷蛇 `char_107_liskam` | `skchr_liskam_1` | 受击回复 SP、一次挡伤、受击给随机邻友 SP；阻挡与充电 |
| 5 | 塞雷娅 `char_202_demkni` | `skchr_demkni_3` | 周期范围治疗、法伤增幅、减速、治疗授予 SP、驻场属性叠层；阻挡和法术爆发配合 |
| 6 | 白面鸮 `char_128_plosis` | `skchr_plosis_2` | 三目标普攻治疗、攻击间隔、扩范围、自然 SP 速率光环；稳定治疗 |
| 7 | 能天使 `char_103_angel` | `skchr_angel_3` | 自动开启、五连射、对空优先、部署随机友方属性增益；物理和对空输出 |
| 8 | 艾雅法拉 `char_180_amgoat` | `skchr_amgoat_3` | 法伤、至多六个随机目标、扩范围、部署随机初始 SP、职业攻击光环；范围爆发 |
| 9 | 凯尔希 `char_003_kalts` | `skchr_kalts_3` | Mon3tr 召唤/治疗优先、绑定技能、真实伤害、随时间衰减、未击杀生命流失、死亡触发；真伤和地面承压 |
| 10 | 铃兰 `char_358_lisa` | `skchr_lisa_3` | 全范围停顿/脆弱、生命回复、停止攻击、辅助 SP 光环及同类取最高；增伤和范围控制 |
| 11 | 温蒂 `char_400_weedy` | `skchr_weedy_3` | 位移、群体法伤、移动距离真伤、炮台召唤、邻近炮台联动/授予 SP、弹道；力学与空间边界 |
| 12 | 夜莺 `char_179_cgbird` | `skchr_cgbird_3` | 三目标治疗、范围扩大、法抗增益、概率法闪、诱饵召唤/生命流失；法术压力关保护 |

表中的机制是 **待实现和待验收需求**。依据来自冻结 character description/trait、
所选技能专三 description/blackboard、当前潜能与阶段可用的天赋候选，和对应 skill prefab。
技能 SP 类型的原始值覆盖 1、2、4；技能类型同时覆盖原始值 1、2。
没有从名称构造 ID 或公式，也没有把 float 的原始位模式整数作为展示数值。
数值 blackboard 使用源 JSON 中已解析的 `value`；缺失值不默认当作 0。

原始依赖封存在 [roster.reference.json](../../packages/campaign/roster.reference.json)。
六份输入为 `../ark_parser/character/data/` 中 characters、skills、battle_equip、uniequip、
operator_skill_prefab_summary 和 skill_prefab_catalog_operator JSON。
每份记录完整文件字节数与 SHA-256，`frozen_sha256` 对规范排序后的冻结子集计算。
保留十二人的完整 character 行、所选技能完整等级行、解锁天赋、实际 token 原始行及其技能、
对应技能 prefab 摘要和完整组件，以及 CAB 内 `m_FileID=0` 的组件引用闭包。
装备候选按 uniequip 实际原始字段 `10` 指向的 character ID 收集，保留来源，**不解释成可装备配置**。

召唤体 ID 来自可信 `talents.candidates.tokenKey`，已核对源表存在：

- `token_10002_kalts_mon3tr`
- `token_10003_cgbird_bird`
- `token_10009_weedy_cannon`（技能 `sktok_weedy_token`）

凯尔希 trait 的 `char_id.valueStr` 还明确引用 `char_4179_monstr`，也封存其原始行和技能；
这个引用的语义仍是 gap，不能用它替换 Mon3tr token。
天赋 `prefabKey=1/2` 是角色上下文中的键，不能用技能 catalog 全局同名项猜配。
characters.displayTokenDict 中存在串读和偏移整数（凯尔希含其他角色幻影描述），因此不作为关联依据。
battle_equip/uniequip 保留很多数字字段而未规范化，不能推断装备解锁条件或模组公式。
技能 prefab 类名是字段签名启发式标签，精确 scriptPathID 仍须映射；闭包引用存在不等于行为已实现。
普攻/角色 prefab、天赋原生组件、范围坐标、动作生效帧和弹道实体还需要补齐来源。
参考包 `data_gaps` 按角色记录缺失 blackboard 值、天赋 prefab 范围、异常 token 字典和 trait 引用等缺口。

固定队伍无法覆盖全部 V2 模块或全部游戏机制。覆盖必须分开计数：

- **固定队伍主线回归**：逐章选定普通标准主线最后一关和倒数第二关，在相同队伍配置下实际运行；
  需要关卡引用、部署输入、能力预检、结果及 checkpoint/replay 证据。某章敌方特殊机制只计该关实际触发并验证的行为。
- **独立原语/契约场景**：装备配置/属性/天赋替换、资源边界、规则与提供器替换、事务回滚、继承、
  编译拒绝、检查点恢复和回放等不可能由十二人组成自动覆盖，保留独立断言和技术证据。
- **敌方或补充机制场景**：冻结、睡眠、恐惧、元素损伤、复活/转阶段、无敌/隐匿、免疫、
  拉拽、坑洞碰撞、无限持续和充能技能等，在固定技能选择下没有完整覆盖。
  即使十二人拥有未选择的技能，也不能把那些技能计入固定回归覆盖。

运行离线构建与验证（没有导入 V1 或 V2 战斗运行时）：

```powershell
..\.venv\Scripts\python.exe tools/build_campaign_roster.py
..\.venv\Scripts\python.exe tools/build_campaign_roster.py --check
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_roster.py -q
```

构建不会生成动态时间戳，队伍顺序固定，不依赖源字典插入顺序。
`--check` 比较完整重新构建内容，任何来源字节、配置、队伍、子集或状态漂移都会拒绝。
本文件与工具只建立后续导入的可追溯输入；需要依次完成规范化、V2 转换、实际引用编译、
独立机制模型断言、固定队伍章节执行和客户端对照才能分别提升相应状态。
