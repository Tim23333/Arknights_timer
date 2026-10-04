# 第九章持续连接的伤害与元素包

原始 Flame 使用 `LassoProjectile` 和 `HarpoonMovement`，不是一次命中即结束的普通飞弹。
固定敌人数据给出 ATK500、普通伤害比例0.12、元素比例0.06、命中间隔0.5秒；
这两个比例分别得到普通法术包60和原始FIRE积累30，元素量不从结算后的生命伤害反推。
来源为 `packages/campaign/chapter09_source_prepare/enemies.native.v1.json`，
来源解释与尚未恢复的方法体边界保留在 `source.detail.v1.json`。

隔离候选 `campaign_c9_linked_elemental_v2_candidate` 为已有通用 Attachment 增加两项组合：

- 可选 `hit_interval_seconds` 将周期发包与移动采样时钟分开；例如按1/30秒追踪位置，按0.5秒发包。
- `effect` 可以使用已实现的 `elemental_attack`，在同一原子作用域内先结算生命伤害，再按独立规则计算元素损失。

这两项均由内容启用；未声明命中时钟的历史 `damage` 连接保持逐步积分行为。
复合包目前要求 `damage_integral=false`，不将单一积分比例偷偷同时应用到两种数值。
元素爆发期间只锁定新的元素积累，普通生命伤害继续结算。
目标死亡后不再增加元素，源失效或取消施法后结束连接并释放其拥有的Buff与任务。

候选身份为 `5ba742c2868c45eb37a14c720001a307e77e30434da6743ee5e4c98a483c8736`，
相对联合父 `6e43` 仅修改 `domains/attachments.py` 和 `content/schemas.py`。
自有12项机制检查实际通过，含当前属性、移动／命中两时钟、无权限任务、
元素规则异常的生命与发包游标回滚、飞行／连接期间实际磁盘检查点及公开命令从头回放。
失败的开发夹具分别保存，候选尚待独立复核和集成后的完整回归，未推广生产。

可复用的最小内容在 `packages/campaign/chapter09_consumers/linked_elemental/prototype.module.v2.json`。
这份原型不表示完整 `duspfr`：仍需接入10.6秒技能Buff的6／10秒冷却关系、
原生Harpoon的目标位移和结束细节、死亡前3秒的DeadBoom五支动作，以及石柱和碎石地形消费者。
完整关卡不得将这些依赖标成空处理或绕过准入。

所有临时测试捕获写入 `E:/ArkSimLogs/runs`，完成后执行新版清理器，
只在 `validation/campaign/chapter09_linked_elemental` 保留源码身份及精简结果。
