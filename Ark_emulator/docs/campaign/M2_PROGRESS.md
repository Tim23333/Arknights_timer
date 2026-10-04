# M2 当前实现与证据

本阶段继续固定十二人/36关目标，没有缩小整体范围。当前完成单位标准输入规范化、首个选定技能原型、事件资源和通用飞行；正式主线转换与验收仍待推进。

## 标准输入

十二人已从同一固定参考版本的标准 character/skill 表规范化，包含实际成长与信赖关键帧、所选技能、SP参数、解锁人才、trait和依赖角色。
此前本地解析的 favorKeyFrames=None 不再被当成零信赖加成。整数取整与信赖映射采用明确的模型 profile，客户端公式校准仍为 false。
产物见 [operators.normalized.json](../../packages/campaign/operators.normalized.json) 与 [规范化说明](OPERATOR_NORMALIZATION.md)。

## 已执行原语

- 桃金娘 S2 使用通用能力/效果/Buff/选择器组合：支付24SP、初始10SP、1–16秒16DP、每秒重选一个受伤友军治疗0.5倍攻击、停攻/零阻挡、结束恢复与SP暂停。
- 该技能的独立场景使用合成atk100，保持 `partially_implemented`，没有将原型当成完整官方干员。治疗preDelay和周期来自原生charpack；16秒费用与到期的客户端同刻排序仍pending。
- 资源新增 `event` 驱动，通过显式 resource.recovery 规则按一次攻击、每次受击或其他事件增减资源。冻结条件在发出事件时采样，避免同帧finish造成恢复穿透。legacy和event重复恢复会在编译时拒绝。
- 飞行沿当前声明路径点直线运动，越过地面墙且不占地面阻挡容量；地面仍使用原BFS，MOVE/WAIT与连续WAIT保留。对空资格由内容selector/tag声明，客户端steering仍待校准。

## 首个正式目标的依赖计划

[0-10依赖计划](../../packages/campaign/mainline_dependencies/level_main_00-10.json) 已解析35次出生、5种敌人、原生控制动作、地图、路线、options和预定义。
敌数据库的defined/undefined继承和关卡覆盖有独立预期；固定来源锁拒绝被篡改DB。
标准difficulty1适用rune为空，三条突袭rune保留为inactive，没有套用其属性倍率。
计划保持 `dependencies_resolved_not_executable`，其余11个所选技能、完整普攻/人才及控制动作明确pending，没有普通攻击placeholder冒充所选技能。

## 当前回归

本阶段全V2测试 **530项通过**，事件资源独立24项、飞行21项、标准数据23项、桃S2原型10项、首关依赖12项均包含在全套中。
新身份下0-1仍11击杀、零漏怪；连续、检查点恢复与从头回放的状态和 **181,638条事件**精确一致。
证据见 [测试报告](../../validation/campaign/m2_tests_20261002.json) 与 [基础模型](../../validation/campaign/m2_baseline_20261002.json)。

这不提升正式36关通过数，也不证明十二人完整可运行。下一批继续选定技能、通用状态/修饰、召唤与0-10转换，按 [目标](GOAL.md) 和 [验收门](ACCEPTANCE.md) 推进。
