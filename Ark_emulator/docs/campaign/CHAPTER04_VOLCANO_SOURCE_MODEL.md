# 4-9 热泵地块参考模块

当前主目录运行M68；本模块在冻结M73环境候选中消费。独立复核已发现M73的同次场触发在全部目标结算后才运行排队的受伤回调，修订M75正在实现逐包调度。因此这里的源短测不能签回调链、第四章全关或客户端准确性。

源模块是 `packages/campaign/chapter04_environment/volcano.reference_module.json`，SHA `91e2f39a2e6c492bc0da90fcb65a21e0f951bdb3abdb3306d1d48d15193c1033`。构建入口 `tools/build_chapter04_volcano_module.py` 支持 `--check`，锁定环境源SHA `148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8`。

| 原始字段 | 实际模型消费 | 验证范围 |
|---|---|---|
| 八地块黑板 damage700.0 / cd_min13.0 / cd_max19.0 | expected_blackboard完全绑定；fixed_amount700.0；纯clock读取黑板13+6u | 真实8格组装；每格HP10000→9300 |
| UniformRandomTrigger preDelay-1 / defaultInterval1 | initial sampled；单次命名stream样本传入可替换field.trigger | 两轮16个clock计算严格核对样本与公式；原生首抽语义待核对 |
| NoSourceDamage PURE / attackTypeNONE | no_source_damage / true / NONE；damage.pipeline图 | DEF9999 / RES100仍损失700；无attack.accepted |
| ignoreForSpFalse / damageWithoutModifyFalse | 显式请求开关 | 通用M72受击SP与target hooks另有测试；本八格不包含SP资源 |
| node isEnvDamageFalse / injectEnvDmgFlag int1 | node_is_env_damageFalse / env_blackboard_injectedTrue | 与参考environmentalTrue分别保存，不能混同 |
| targetSide3 / motion1 / category1 / advanced ignoreTargetFree0 | field.members明确掩码及target-free过滤 | 当前cell参考资格；真正Collider重叠待核对 |
| castMaxCnt-1 / actionsOnTrigger与actionsToSlot为空 | 无限周期；不存在静默跳过的额外动作 | builder拒绝次数限制、新动作与未消费PPtr引用 |

根Collider半径1.710000038与extra Collider半径0.709999979保存在模块原始几何数据中。当前提供器采用half-up格投影，本格及四个正交邻格；邻格只接收处于阻挡或攻击中的敌人。该规则是明确模型政策，不能由两个原生半径或 `onlyCombatEnemyInExtraRange` 字段名推导为已证明的游戏正文。可替换 `field.members` 规则以改变体积、范围和战斗判定。

当前另明确声明以下政策：场使用独立命名stream `field/volcano`；无actor可用性使用side2默认projection；显隐排除flag9/17；environmentalTrue用于参考环境归类。原生stream调用顺序、量化、targetSide及隐身组合仍保留来源语义待核对项。PRTS [地形参数说明](https://prts.wiki/w/%E7%89%B9%E6%AE%8A%E5%9C%B0%E5%BD%A2/trapper/tilesformat.json)作为补充参考，实际数值以已锁定表和提取的动作节点为准。

实际源测试 `tools/experiments/m73_environment/verify_volcano.py` 已通过2项，600tick内触发全部8格一次，有序checkpoint真实存盘并按SHA重载、完整snapshot、从开局replay一致。起止核心、全部Python源码、contracts、builder、来源计划、模块和CP helper均守恒，报告 `validation/campaign/m73_environment/volcano_source_tests.json`。

初次观察夹具错误使用payload.contract筛计算事件，实际字段为calculation_id；失败记录和旧模块、旧报告保存于该验证目录。修正只改夹具，冻结M73核心未变。

下一阶段必须在修订M75上重新生成其实际版本证据，并覆盖事件反应对后续包的影响。4-9全关还需要其49次原生出生、其余敌人能力、固定12人公开操作、完整生命周期、磁盘续跑与开局回放。八格短测不代替这些验收。
