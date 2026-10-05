# 第九章战场废墟

当前内容使用 `packages/campaign/chapter09_consumers/ruin/module.v2.json`，运行内核固定为
`2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0`。
该内容修正旧支柱模块中的废墟阵营映射、攻击标签、被动免疫和阻挡半径，不修改内核。

源配置位于 `chapter09_source_prepare/duruin.transitive.source.v1.json`。
`MapDependentTrap` 继承的 `_sideType` 是 `SideType` 位掩码：ALLY=1；
V2 `selection_state.side` 是 `SideTypeIndex`：ALLY=0。旧模块直接复制1造成敌方判型。
新内容明确映射为0，保留障碍物类别4、HP100、阻挡3和重写地块字段。
`player`/`ground` 标签使实际被阻挡的敌人取得我方障碍物；移除敌人标签使装置不参与原生波次计数。
这一判型也与 [PRTS 战场废墟](https://prts.wiki/w/%E6%88%98%E5%9C%BA%E5%BA%9F%E5%A2%9F) 的我方障碍物描述一致。

原生被动 `duruin_abnormalimmunes` 带异常免疫0/16/12、组合免疫0，
`immu_environment_damage` 对环境伤害的比例为0。该被动现通过现有 Buff/伤害管线实现。
阻挡规则使用源平方半径 `0.30000001192092896`，采用距离严格小于半径的参考边界。
撤退返还比例保留原生0.5。视觉 spawned Buff 仅切换渲染器，没有伪造废墟存活期限。

旧内容反例使用真实源猎犬：推进100帧，废墟HP100且敌人一直受阻，没有实际攻击。
新版使用同一源猎犬，实际命中帧18，300攻击对剩余100HP造成100有效生命扣减，
废墟死亡后解除阻挡、恢复路线，原生敌人击杀数仍为0。CP10续跑到120与从头回放完整一致。
另外，环境 NoSource19造成0伤害，普通 NoSource19造成19伤害，HP100变81；
CP4续跑到8与回放完整一致，未排除状态、调度、随机数、事件、缓存或计算字段。
实际收据为 `validation/campaign/chapter09_ruin_v2/final.v2.json`。

旧 v1 表达式阻挡实现被契约拒绝，其实际失败收据保留；v2改用纯提供器。
早期验证误把有效扣血量预期为300，实际事件是过量伤害受剩余HP限制后的100；
该失败及事件探针收据保留，后续更正的是测试预期，模块和内核未变。

原生 `MeleeAttack._selectTargetSource=2` 对应 INPUT_TARGET；
原生 AttackWrapper 派发方法体尚未取得。实际阻挡者作为输入目标是当前明确参考策略，
机制验证不等于客户端方法体或全关准确性验证。独立复核及新版9-18整关验证分别记录。

新版9-18输入为 `level_main_09-16.native_draft.v4.life99999.json`：
场景、34个源出生、路线、12人队伍、DP12、部署上限8、基地99999和单位源HP保持不变；
内容只替换废墟定义，增加它的三个依赖定义，并重新绑定完整Buff表供爆破位移查询。
`finite_run_v1` 覆盖层仅增加运行验收元数据，不改变战斗输入。
所有大捕获均在 `E:\ArkSimLogs\runs` 执行期间使用，结束后自动清理，精简收据继续保留。
