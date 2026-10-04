# 固定队伍基础单位转换

`tools/build_campaign_units.py` 将封存的 `operators.normalized.json` 与
`attacks.reference.json` 转为 `units.base.json`。攻击来源的 normalized SHA
必须匹配当前养成来源；输出同时保存两者及离线范围表的 SHA。

十二人均生成精二70、潜能一、信赖100%、指定技能专三、无模组的基础单位。
现在十二人均已有来源支持的可执行普攻模型。攻击包含真实 OnAttack 帧事件；陈两击保留独立时点，
温蒂的目标上限读取有效阻挡数，艾雅法拉与铃兰保留有来源的弹道速度。
数值使用已封存的标准表养成模型，客户端成长舍入和动画缩放/FSM仍未验证。

早期三项来源缺口已经由 [ANIMATION_BINDINGS.md](ANIMATION_BINDINGS.md) 的受控原始证据恢复：

| 单位 | 缺口 | 运行处理 |
|---|---|---|
| 雷蛇 | 实际Animator将Attack映射到Attack_Loop，第1帧事件 | 循环事件已转换，begin协程交接仍pending |
| 夜莺 | 实际Animator将Attack_A/C映射到Attack，第27帧事件 | 三目标普通治疗模型已转换，原生缩放仍pending |
| 凯尔希 | exact projectile_chr_kalts movement.speed=5 | 第13帧发射与模型延迟治疗已转换，hit/reached回调仍pending |

转换时从当前原始资产和受控reader重建整个绑定并比较，核对原始字节和派生结果，
防止两方向同时伪造帧后仅用一个新SHA自证。没有恢复证据时仍严格拒绝缺失攻击，不使用默认帧。

基础模型自身没有将完整技能与天赋挂载到单位，`complete_operator_count=0`；
所选原生技能 ID 和全部待整合项保存在 manifest 的逐人 conversion 中。
选技模型的实际挂载在后续 `squad.integrated.json` 中，见 [SQUAD_INTEGRATION.md](SQUAD_INTEGRATION.md)。
完整范围优先级、免疫、凯尔希召唤优先治疗、温蒂/铃兰普通攻击附加效果等
仍需在整合时逐项验证。因此该包不能作为十二人完整实现、0-10通关或正式主线审查依据。

`tests_v2/test_campaign_base_units.py` 用实际 Compiler/Engine 检查真实配置数值、
陈的独立双击、温蒂可修改的目标数、艾雅法拉发射与落地时差，以及缺失证据的失败门。
执行 `python tools/build_campaign_units.py --check` 可核对生成内容与当前源输入。
