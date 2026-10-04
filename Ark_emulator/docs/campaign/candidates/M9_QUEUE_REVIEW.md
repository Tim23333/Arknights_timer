# 内部队列复制与候选验证

Primary M8 core继续保持 f8 身份，当前长程恢复/回放由同一源码执行。
候选实现、测试和补丁在隔离目录中开发；本文不是primary已更新或正式关卡通过声明。

## 可观察边界

Scheduler schedule/restore已经完整验证并独立拥有任务payload；公开peek/pop/pending/snapshot返回独立只读或plain副本。
存储任务创建后不在原记录上修改。内部 `fork()`复制任务索引、heap与allocator，复用这些已验证的记录，
用于事务及嵌套savepoint；新增任务仍完整JSON验证。公开checkpoint仍完整clone/restore，不接受未校验输入。
`next_task_id`只读allocator，Buff与Ability不再为了读一个整数序列化全部待执行任务。

新fork8项加既有kernel46项实际54pass；别名/资源一致性候选加M8timeline/event资源共57pass，记录各自身份。
fork回归覆盖输入隔离、公开snapshot隔离、cancel/pop/schedule、批次失败、内外嵌套回滚、allocator与同时间顺序。
修改在 `M9_SCHEDULER_FORK.patch`，global alias/source引用一致性在 `M9_ALIAS_RESOURCES.patch`。

## 真实前缀与profile

固定同内容、命令、seed953816614、300tick：primary f8与第一候选39c的 world/tasks/RNG/state hash一致，
事件数均21536。完整原始事件hash不同，记录 `m9_candidate_300tick_equivalence_20261002.json` 的
strict passed=false，不能宣称跨版本逐字节日志相等。
第一实际差异为calculation.trace.runtime_fingerprint（规则版本身份），之后
resource.changed.target从旧`system/battle`字符串alias变为canonical entity1。这些是已声明身份/API修订；
后续仍需分别比较数值与完整新身份回放。未对原始事件删字段或重标hash。

Primary开启cProfile的300tick耗116.47秒，其中scheduler.snapshot累计59.24秒；
同scope候选profile47.45秒，热点已转为属性/规则计算。Primary另一个未开profile运行42.28秒。
这几次有不同profiler及并行系统负载，不能换算成受控倍数或整关性能承诺。
原始profile、semantic与比较JSON均保留。

## 取消任务的保留边界

根审查又实际发现，fork复用heap后丢失旧事务隐式清理：200次未来schedule/cancel，
active tasks均0、nextID均201，primary残留heap1而候选残留200。
这是真实内存边界回归，见 `m9_queue_cancel_retention_probe_20261002.json`。

独立queue-bounds候选（没有修改正在测试的共享candidate）在cancel后无任务时清空heap，
否则超过max(64,2*active)时按相同稳定key重建。任务排序和allocator不变，清理均摊。
新3项与fork/kernel合计57pass / .37秒，补丁 `M9_QUEUE_BOUNDS.patch` 与
`m9_queue_bounds_candidate_20261002.json`记录该独立身份；尚未合入共享候选/primary。

共享候选先完成null兼容、route新接口和全套；再合并该补丁并冻结最终身份重验。
旧39c、null修订cadd及queue-bounds均为不同验证输入，不把旧结果抹去。
