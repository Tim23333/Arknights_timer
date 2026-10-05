# 爆破装置来源消费者

两关卡片保留固定表和原始预定义记录：9-18 对应 `level_main_09-16`，库存2；
9-19 对应 `level_main_09-17`，库存1。模块分别位于
`packages/campaign/chapter09_consumers/demolition/level_main_09-16.module.v1.json` 和同目录09-17版本。
它们保留 HP100、ATK2000、费用5、部署数占用0、从部署时开始的5秒再部署冷却及0退款。

技能表的 SPtype8 是被动；初始0、容量25等表值继续保留，不能将25技力解释成等待25秒。
原生 `triggerability_tick_trigger` 的首次0.5秒与 `MeleeAttack` 的0.649999976秒前摇分别量化，
当前30Hz参考规则下，在部署后第15刻开始爆破，第35刻执行伤害并退场。
该时序和命中格投影是显式可替换参考策略，没有声明为客户端逐帧对照结果。
[PRTS装置说明](https://prts.wiki/w/爆破装置)记录了部署后触发、前方一格、真伤及直接击倒柱体的行为。

攻击在命中时重新选择前方一格的合格地面敌人，保留原生阵营、类别、隐形、迷彩及target-free政策。
普通2000真伤进入可替换 `damage.pipeline`。推力进入 `movement.displacement`：
使用 force1 加当前 `base_force_level`，与目标 `mass_level` 比较。
参考位移表只通过 AST 读取历史常量，没有执行V1战斗代码；原生减速曲线和碰撞校准仍单独记录。
环境伤害免疫按原生 `immu_environment_damage` 的共享环境标记执行，普通伤害不免疫。

柱体分支要求调用者提供四个实际编译的倒塌能力ID，进入正常依赖闭包。
装置按方向调用前方柱体实际拥有的能力，柱体支付10SP并保持原5000HP，随后走真实倒塌载荷。
该分支与普通2000伤害分开建模；缺失能力依赖不能静默退化。

冻结作者证据为8组、16个实际CP/head场景；独立复核为8组、19个实际CP/head场景。
独立门使用不同HP/DEF/RES/质量、tick7部署与不同坐标，覆盖四方向、命中前离开、状态选择、
推力加成、不可移动、库存、再部署、地形、0槽位、真实环境/普通伤害和柱体SP。
完整checkpoint保留state、tasks、RNG、事件、attribute cache、context、value与cause，无字段过滤。
收据见 [作者冻结](../../validation/campaign/chapter09_demolition_v1/freeze.v1.json) 和
[独立结果](../../validation/campaign/chapter09_demolition_peer/peer.result.v1.json)。

这些场景在冻结53ee身份上真实执行；53ee的长回归存在独立领域可选字段缺口，因此本内容证据不表示该核心可推广。
最终整关将使用新验收核心重新执行，旧收据身份不迁移。原生AutoLoadBoxRange边界、精确固定点时钟与位移曲线仍为模型差异。
各轮已完成捕获均清理，只保精简结果、来源和内容。整关与客户端验收仍分别记录。
