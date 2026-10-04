# 空间与容量模型，首章全程推进

本阶段保持固定十二人与36个主线尾关目标。M6内容/验证产物保留其原始身份；
新首关包为 `packages/campaign/mainline_models/level_main_00-10.m7.json`。
正式验收仍0/36，不能用单元测试或探索终局自证通过。

## 已实现底座

命名契约现为78：新增 `spawn.position`、`resource.capacity_change`、`movement.steering`。
出生采样由Kernel显式stream/轴顺序/零轴策略承担，纯规则决定位置；计算、创建、出生数减少同事务。
Cartesian半幅与独立spawn流、源x/y到top-down坐标、种子绑定均是明示模型选择，原生正文仍待核对。
八邻居使用距离权重与不切角规则，保留逐checkpoint及WAIT；飞行逐段直线，不借地面墙体绕路。
有界速度响应将已读取的mover常量作为声明参数，velocity参与World/检查点，停止与阻挡清速度。
point-body墙裁剪、arrival_radius=.05是可替换模型策略，不假称已恢复原生碰撞或分离力。

容量变化同步发生在Buff apply/remove/expiry/aura离开，且跟踪时间规则与直接属性更改。
资源策略可选择absolute/ratio/missing/fill/birth_full或替换整个 `resource.capacity_change`；
夹界事件与治疗/伤害分开，移除生命增益后的下一击不会错误计入夹界损失。
最小自定义规则集无需新增策略也可通过其原bounds保留绝对值；显式新模式必须声明新绑定。
轮询跳过仅在参数依赖、属性提供器及其有效子规则/聚合器都满足静态条件时采用；未知依赖保守轮询。
provider descriptor与容量签名参与身份/World状态；ctx别名、层顺序及委托时间依赖均有独立反例。

## 编队与方向

新增 `roster.profiles.json` 提供凯尔希无装备的自身/自有Mon3tr优先治疗语义模型，
保持原生enum64不同于36且正文未恢复的边界。部分原型范围固定朝右的问题已在M7整合转换中纠正，
实际部署朝向现在影响相对格子范围。原HP策略选择与鸟笼卡片回补、隐含寿命继续单独记录。
来源见 [我方审计](M7_ROSTER_GAPS.md)、[空间审计](M7_SPATIAL_SOURCE_AUDIT.md)。

## 独立审查与运行

[空间复核](M7_SPATIAL_REVIEW.md) 完成31例及组合checkpoint/replay；
[容量复核](M7_CAPACITY_REVIEW.md) 完成时间依赖、变化策略、回滚与恢复反例，另补最小规则集兼容用例。
全量运行曾929过/17失败：16项是新容量接口对既有上下文/最小ruleset的兼容遗漏，修复后相关172项通过；
最后一项是在修复期间触发实现身份保护，原非零日志 `m7_final_tests_20261002.log` 保留。
新身份完整测试与0-1验证已在 `m7_postcompat_final_*` 完成：完整948项全部通过，573.93秒；0-1仍为11击杀零漏怪，
tick300检查点续跑与从头回放的181,808条事件一致。结束后重新创建Engine核对运行身份一致。
证据为 [完整测试](../../validation/campaign/m7_postcompat_final_tests_20261002.json) 和
[0-1基线](../../validation/campaign/m7_postcompat_final_baseline_20261002.json)，旧17失败记录不重写。

0-10全程固定脚本位于 `scenarios/campaign/00_10_full_model.json`。
首个探索已处理35次出生，终局34击杀/1漏怪，因此未通过零漏怪要求；
报告、输入package/commands快照与旧实现身份保存在 `m7_00_10_exploratory_20261002.*`。
采用冻结空间/转向配置的探索正在 `m7_00_10_frozen_exploratory_20261002.*` 运行；
它禁用回放比较以寻找操作问题，回放字段保持null，不替代完整终局与回放验收。
转向版本的探索也为34击杀/1漏怪；首个漏怪诊断已在当前核心重现，确定为enemy_1000_gopro于tick539退出。
当时桃金娘在(4,8)施放不阻挡，风笛于tick360部署在(4,7)，已经落在该敌人后方。
首次修位(4,9)被真实高台规则拒绝，记录保存在 `m7_00_10_high_tile_rejection_20261002.*`。
核对原生地图后改为同tick部署在合法道路(4,10)，塞雷娅后续改到(4,7)避免占位冲突，
保留费用、地图与养成；旧脚本另存 `00_10_full_model_before_leak_fix.json`。
新前缀验证与后续全程须分别检查，不能因定位问题就宣布修复通关。
合法修位又揭示原型选择器未包含自己的阻挡目标：拐角敌人停在相邻行，阻挡成立而攻击范围不含它。
M7整合层为有阻挡能力的我方敌方目标选择器补上include_blocked，不改变其他目标的范围。
新独立真实角色/敌人反例1项通过：关闭该项敌人被阻挡且HP820不变；开启后真实伤害事件出现。
这项为948全套后新增内容检查，不将旧全套记录重标为949一次全绿。
改位与选择器修复后的20秒前缀实际通过：3命令接受、5出生、1击杀、0漏怪、伤害829.5，
见 `m7_00_10_leakfix_prefix_20261002.json`。它是探索前缀，replay字段为null，仍有30次出生待执行。
修正全程正在 `m7_00_10_corrected_full_20261002.*` 执行；终局、出生守恒和同身份回放尚未完成。

## 0-11接续

`build_mainline_00_11_sources.py` 已读取六个精确prefab/default combat/实际Spine引用：
OnAttack帧为slime10/slime_2独立10/gopro18/nsabr12/wteeth19/shdsbr12。
37次出生、STORY1、DISPLAY2保留；四条原文剧情与实际两个提示事件均有执行证据。

`build_m7_mainline_00_11.py` 已组合同一队伍与来源，但Compiler发现真正的新依赖：
`WAIT_CURRENT_FRAGMENT_TIME`。该包明确拒绝运行，未将其偷换成到达后等待30秒。
接下来审计fragment开始时钟和deadline语义，增加通用时点等待，再执行与复核0-11。
源审计进一步区分了 `blockFragment=false` 与 `dontBlockWave=false`：不能以不阻塞片段推断不阻塞下一波。
0-11包含多个wave，托管敌人集合及下一波推进正文仍未恢复，增加了独立wave completion gating缺口。
当前flat排程模型中片段从54秒开始、其30秒deadline为84秒，只是该模型的结果；
实现托管清场推进后必须在运行时保存真实片段起始S，再以S+30等待，不能固定写84或出生后睡30。

## 性能边界

首个0-10探索峰值RSS约22GB，日志保留的输入快照可能存在重复。
只读30tick审计记录了1655事件及FrozenMapping经compact/clone重新包装的现象；
这不足以单独证明全部22GB来源。下一阶段需在保持数值操作数、事件与回放身份的前提下减少重复存储，
不能通过丢弃关键证据获得更小内存。本阶段未改trace策略。
