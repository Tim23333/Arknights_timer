# 编队、召唤与位移整合进展

以下为M5阶段记录。当前M6已接入两侧天赋与外部默认召唤资源，新增部署、付款和0-10控制模型，
最新状态与来源限制见 [M6_PROGRESS.md](M6_PROGRESS.md)；以下缺口及旧运行身份保留历史语境。

持续目标仍是固定12人和36个标准主线尾关，当前正式关卡验收0/36。
本轮将实际养成基础单位与12份选技模型合成同一可编译模块，并补召唤、范围弹道、
位移路程、时间曲线和资源归属。完整干员数保持0，不能以模型原型替代完整机制审查。

## 来源与整合

`extract_campaign_animation_bindings.py` 恢复实际Animator→Renderer→SkeletonDataAsset→TextAsset引用链，
以受控big-endian float32 reader解析已确认3.8.99/FPS30的Spine字节。
没有改安装库或共享effect_frames表。雷蛇Attack→Attack_Loop、夜莺A/C→Attack的映射由实际字段证明，
凯尔希精确projectile_chr_kalts速度5来自同名GameObject的movement组件。
所有12人的基础攻击现均可执行；雷蛇begin协程、动画缩放、凯尔希hit/reached回调仍独立pending。

`build_campaign_squad.py` 输出 `squad.integrated.json`：

- 12个正式native_id、固定配置、实际HP/ATK/DEF/攻击间隔/费用与选技ownership。
- 保留真实成长和信赖结果，绝不复制原型ATK100或HP10000覆盖实际养成。
- 收集所选技能的真实引用闭包，排除合成对手、测试移动能力与原型场景输入。
- 两种召唤模型使用稳定owner实体ID关联；不把别人的召唤物算入自己的选择器。
- 集成后的召唤部署必须从命令payload指定位置和朝向；原型固定坐标不进入实际编队。
- 全部内容保持 `integrated_partial_roster`、`complete_operator_count=0`、`formal_mainline_approved=false`。

选技模型现在有12份，最后新增温蒂S3/水炮与凯尔希S3/Mon3tr。
前者真实执行单发速度8弹道、半径约1.2的落点AoE、质量差/墙裁剪与实际路程真伤、
EXTEND共享距离实例、水炮归属/联动/3秒SP/20秒寿命/DP5原子支付。
后者依据原始BSON节点执行剩余比例攻击增幅、20秒真伤、击杀标记与无击杀50%最大HP惩罚，
host SP15和valid-token恢复门、失token清SP/中断以及真实模型养成的Mon3tr归属。
Mon3tr缺少真实战斗prefab/Spine，攻击仍是显式signal probe；没有编造原生自动攻击时钟或用char_4179替代。

## 通用接口

- `Buff.on_remove` 同事务同步执行移除效果，`modify_resource.value` 为有边界的幂等赋值。
  技能mode现在在Buff半开到期时还原，修复结束tick无增益技能攻击；时间线末尾费用/治疗等效果继续保留。
- `area` 以source或impact target为中心，在落地时选择存活、标签匹配的当前成员。
  `wait_for_projectiles` 只等待本cast的实际根弹道completion，不把DoT时间当施放通道，嵌套schedule不重复计完成。
- `push` 通过现有 `movement.displacement` / `movement.distance` 合同求计划和分tick步长；
  网格边界和墙体裁剪不穿墙，零计划不产生假路程。当前点体/历史力学曲线明确是可替换模型profile，未宣称客户端校准。
- `Buff.movement_damage` 用World中的实际累计位移和独立cursor采样，将delta交给自定义damage.pipeline；
  到期、移除和refresh/extend前flush尾段，致死递归不重复计费。
- `spawn.owner`、lifetime与max_owned、owned过滤、Manhattan区域及 `trigger_ability` 支持通用召唤关系。
- 技能cost.owner可为source、battle或owner，先规划全部持有者的支付；与on_start召唤同一原子事务。
- `recovery.selector` / empty_value / selector_interval_seconds / interrupt_when_empty 支持有效成员恢复门。
  `respect_recovery_freeze` 使显式回复也遵守施放冻结。
- `ark.attributes.time_layers` 是可替换纯provider，支持linear_remaining与staircase；
  属性快照使用其sampled_at时钟，延迟at_cast不会按hit时间重算曲线。

## 独立发现与边界

独立复核发现并修复alias退场与整数owner比较漏清召唤物，以及整合包携带温蒂原型固定坐标的问题。
对齐技能结束tick的模式交接错误也已由同步on_remove修复；原先记录错误的pending见证改为真实拒绝反例。
源码身份变动期间的回放不匹配保留在中间日志中，最终证据须基于冻结后同一身份重新生成。

完整天赋/随机、原生动画与自动攻击时钟、卡片地形/占位/再部署计时、
部分技能曲线和模板source归属、0-10原生控制、后续Boss/地图/预放置等仍需逐项完成。
正式验收门不会因为内容包存在、能编译、模型获胜或测试数量增长而自行放行。

来源/技能细节见 [ANIMATION_BINDINGS.md](ANIMATION_BINDINGS.md)、[WEEDY_RECIPE.md](WEEDY_RECIPE.md)、
[KALTS_RECIPE.md](KALTS_RECIPE.md)，独立复核见 [M5_REVIEW.md](M5_REVIEW.md)。

## 冻结验证记录

冻结源码全套运行781通过、1失败（335.35秒）。唯一失败为旧依赖审查仍要求
“十一份技能原型未实现”的过期状态断言；当前12份模型已经存在且仍全部partial。
按真实状态更新该审查后，其全部8例重跑通过（0.33秒），保留天赋/原生时钟未完整转换、
native_complete=false、不可运行规划与正式验收未提升的原要求。
当前782例的执行覆盖证据见 [m5_final_tests_20261002.json](../../validation/campaign/m5_final_tests_20261002.json)，
保留原全套非零结果与定向修正结果，不将原日志改写为一次全绿运行。

新实现指纹下0-1在tick2408结束，11击杀零漏怪；连续执行、tick300检查点续跑与从头回放
的状态及181,638事件一致，标准/平衡伤害850/60独立预期也通过。
运行指纹已与当前源码重新创建的Engine核对，见
[m5_final_baseline_20261002.json](../../validation/campaign/m5_final_baseline_20261002.json)。
十二份partial模型的实际编译指纹见
[m5_skill_compilation_20261002.json](../../validation/campaign/m5_skill_compilation_20261002.json)。
第二条独立复核及原始证据伪造拒绝反例见 [M5_ROSTER_REVIEW.md](M5_ROSTER_REVIEW.md)。
