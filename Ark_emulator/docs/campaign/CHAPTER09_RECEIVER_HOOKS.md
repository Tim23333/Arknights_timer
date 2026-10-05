# 接收者修正前的来源标记

固定 `enemy_dugago_t[attack_by_dupilr]` BSON 要求在接收修正前检查实际柱体来源Buff并创建临时mark，
归零前由实际mark判定跳过复生，完成修正后清mark。原始接口只有source `before`与receiver `after`，
不能表达这个接收者前置顺序；编译拒绝反例保存在 `chapter09_rock_modes_v2/target_before_modifier.counter.json`。

新隔离候选 `77049fb9724675de47f4fb8bb72e5696b64f4737156acf513f1b7963015d9050`
增加显式 `damage_hooks.phase: receiver_request`，继续使用纯 `damage.request`契约，不修改旧契约表。
纯规则返回严格 `accepted / effect / effects`；effect为已解析的有限数值伤害请求，
其attack/defense/resistance操作数不是公开内容effect字段。
写阶段在真正接收者身上同步执行有限apply_buff/remove_buff/emit，不能用此接口启动递归伤害或写别的目标。
声明的 `after_effects` 在修正结算后执行，包括pipeline拒绝后的清理；规则直接拒绝时不会先施加前置标记。
整个请求与同步回调在同一个既有事务内，后续失败回滚HP、任务、事件、RNG、cache及游标。

旧source-before extras仍保持结算后的派发时序，旧receiver-after仍是伤害管线修正，
没有将它们隐式改成新的接收者前置阶段。NoSourceDamage和明确绕过修正的路径未增加该阶段，
不得由这里的actor-source测试推导无来源效果也会运行前置标记。

源消费者提供native_literal和prts_reference数值/运动profile，但mark链采用固定原生同一次修正的create/check/clear。
1秒寿命原值保留；非致命柱击结束后mark已经清理，随后其他来源致死应正常复生。
PRTS描述的持有破碎效果1秒政策作为另一个版本差异保留，没有静默混入原生清除时序。

作者4个源场景和4个接口门、原46领域规则及33个旧钩子回归实际通过；
源码冻结见 [freeze.v2.json](../../validation/campaign/chapter09_receiver_hooks_v2/freeze.v2.json)。
初版将已解析请求错误地送入公开effect字段验证，导致三项源场景失败；
那一版的latefault表面通过也没有到达真正晚故障，局限已经单独标记。
新版本断言实际故障到达声明的missing-resource分支并核对完整回滚，旧失败不改。
独立复核16个有效门及10场景20CPP/head已通过；初批因provider构造错误被提前挡住的六个负向门没有计入证据，修正后全部八个接口门实际重新执行。
整关、全核心回归和客户端对应关系未由本批提升。
