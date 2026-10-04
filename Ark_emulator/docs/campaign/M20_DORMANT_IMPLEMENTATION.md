# 休眠实例注册与激活

本批增加通用的初始休眠实体和持久注册表，仍在候选与组合验收阶段；生产底座及第0章收据身份不变。

初始实体可声明 `active=false` 和唯一 `registration_key`。World 保存真实 actor 与注册表引用，`alias=null` 不产生伪造别名。`alive` 表示生命状态，`active` 控制战斗参与。激活前资源周期/事件回复、初始Buff、编队创建效果、行为初始化、寿命、地形覆盖、选敌、阻挡和部署容量均不参与；激活使用同一ID，在当前逻辑时点开始初始化和计时。

`activate_predefined` 效果显式指向 battle registry，并提供 key。未知key、重复key、错误类型、重复激活或已经退场的实例明确拒绝。初始化过程中规则、Buff或编队效果失败，actor、注册表、任务、资源、随机数和事件一起回滚。注册key与同名实体alias属于两个不同引用空间。

初版独立复核暴露了目标SP写入、Buff回复快照、行为状态写入，以及从未激活的来源向活跃目标写入/伤害/随机的旁路。失败报告与原实现字节保留。修订明确区分从未激活的 dormant 来源和已经激活、发射后退场的来源；后者的合法在途包仍可结算。管理类操作另有明确边界。已激活注册实例在声明生命周期规则复活时重新参与，休眠模板不提前执行死亡规则。

## 真实NPC内容

1-11安德切尔仍使用实际E0L20、技能1、HP677/ATK199/DEF74/RES0。生成器重新读取实际Character资产Typetree，严格核对 `_occupiedRemainingCharacterCnt=1`，将它放入真实 `deployable.capacity=1` 消费者。注册时不占容量，激活后占1，不经普通高台部署门拒绝原生预放置。

原始hidden=true、位置、RIGHT、aliasNone、配置及12张教学卡保持来源。SP类型从实际 `INCREASE_WITH_TIME` 映射至共享时间回复规则，SNIPER标签和基础回复1由来源派生；实际Ptilopsis光环场景验证激活后每周期1.3，激活前0。范围3-1与锁定的公开range表逐格相等。预放置免费、退款paid-cost默认0是明确模型，原生预放置退款基准/隐藏SP与壁钟/初始化回调仍client_pending。

## 身份与证据

- 原目标隔离修订 `db6134...`：15新例与10旧模块合计181项通过；真实NPC两项通过。0-1完整11击杀/0漏怪、300刻检查点/回放181937事件一致、自定义850/60通过，source/core guard结束为exit0。
- 来源隔离修订 `b506ee18e7137c3658f1fe8ce77b4b612bf48bceb9b02446f2dfcb7d91abbf0d` 位于 `unpack_work/campaign_m20_dormant_source_candidate`。独立13项fresh复核通过，具体fixture字节在读前hash并实际Compiler/Engine执行。原db版本与初始反例未覆盖。
- 新输入 `packages/campaign/chapter01_stage_models/m20_source/level_main_01-11.dormant.partial.json` SHA `52a7432cc87e3806afd6d63c7a1fd2f06782caf34bdebde4cbc176b9ea7c7111`，272个定义编译通过。独立范围详见 [来源隔离复核](M20_SOURCE_PEER_REVIEW.md)。

检查不是完整1-11胜利，也未验证教学卡的原生客户端编队、NPC弩箭的原生跟踪或全部原生FSM。完整关卡进度不因这些机制场景增加。
