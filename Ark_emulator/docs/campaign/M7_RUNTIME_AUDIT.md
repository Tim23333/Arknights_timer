# M7 全套失败与trace存储只读审计

2026-10-02。本轮没有改生产源码、M6文件或已有测试。只读原日志，新增小型 `tools/audit_m7_trace_storage.py`、新审计JSON与本文档；按root后续派发，仅在已有本轮M7独立容量测试添加两条兼容性预期。

## 已完成全套运行的失败根因

原日志 `validation/campaign/m7_final_tests_20261002.log` 最终为 **17 failed, 929 passed in 571.01s**。没有通过猜名称归因：先用真实collection顺序映射进度F位置，再直接执行两个代表测试，最后读取完成日志核对。

| 类别 | 数量 | 实际根因 | 处理状态 |
|---|---:|---|---|
| test_content最小自定义ruleset | 1 | 新preflight无条件要求resource.capacity_change，原最小battery已有显式capacity/bounds却没有新绑定，编译拒绝。 | root兼容修复，不修改旧测试。未声明新profile/绑定时保留绝对值并经现有bounds夹界；显式profile依然需要新契约。 |
| test_domain_rules资源恢复 | 15 | ResourceSystem.tick先计算capacity_signature，直接调用IsolatedContext不具备的definition_bindings/program；恢复尚未执行就AttributeError。 | root改可选owner bindings及Kernel intents，旧domain测试保留。不是恢复公式数值失败。 |
| Weedy检查点/回放 | 1 | 全套进程启动后生产身份发生变化，真实replay runtime fingerprint拒绝。 | 旧运行保持历史，必须最终冻结身份重新验证，不能削弱身份检查或把旧进程结果重标为新通过。 |

root报告fresh content/domain/capacity组合172项通过4.35s。独立新兼容测试实际通过：无新capacity_change contract的自定义ruleset在maxHP减少后夹界，下一包true1只记伤害1；显式preserve_ratio却缺绑定时编译明确拒绝，不能静默fallback。包含旧policy/dynamic/cp/replay的本M7独立测试完整 **25 passed in 2.09s**。

## 小型存储审计：事实与限制

输入是实际冻结0-10 package/commands snapshot，seed953816614，只执行前30逻辑帧，没有改trace模式、事件处理或调度。结果在 `validation/campaign/m7_trace_storage_audit_20261002.json` 保存输入hash、运行身份、源码hash与RSS。

- 30帧累计1,655个事件，其中calculation1,296、policy91、calculation.cached159。
- calculation序列化约2,762,527 bytes，policy350,438 bytes；这些是JSON体积，不能等同保留的Python堆。
- 两类trace遍历累计51,418个容器，嵌入336份完整实体形状；该prefix尚无技能cast。
- 单进程prefix结束RSS约54MB、private commit约45MB。初始约30MB/23MB；这是小prefix，不能线性外推完整4500帧，更不能据此单独解释22GB。

身份复现probe确认：World提供的实体已经是FrozenMapping，放在两个相同inputs角色里，经 `compact_trace` 后成为两个不同dict，既不保留原实体引用，也不共享彼此。context中的source/target/owner会缩成ID，inputs中的source/target/candidates并不这样缩减。

另作隔离敏感度probe：在该审计进程显式将Myrtle SP设置24并真正启动已选S2，未把这段算进关卡prefix事件统计或进度证据。实际entity由38容器/无cast增至83容器/含1cast（包含捕获视图）；compacted双实体inputs仍有91容器、2份cast、5,510 JSON bytes。快照键会被compact剔除，但cast的其它数据仍随多个输入角色重复复制。这是实际技能状态的形状见证，不是假handler或人造cast dict。

## 存储路径审计

1. `RuleRuntime.evaluate` 的trace包含inputs、parameters、context、stages、raw和value；freeze可以保留可信FrozenMapping引用。
2. `RuntimeContext.compact_trace` 对所有Mapping递归新建dict、对tuple/list新建list；只特判context角色与几类snapshot键。它丢掉了原有冻结输入树可共享的身份。
3. `EventLog.emit` 再调用Kernel clone：`_plain`递归建普通树、JSON dumps/loads校验与复制，然后readonly/freeze再次创建FrozenMapping树。结果是历史事件拥有重复的实体/cast数据和容器，保证隔离但内存成本较高。
4. `verify_mainline_model.run` 在保存检查点及恢复/回放验证时还会保留/复制事件历史。原sim、checkpoint、restored及replay的同时存活可能放大峰值；需要完整运行的分阶段RSS及保留对象测量才能归因。

这是可证实的重复存储因素，不是22GB的完整因果证明。没有开启tracemalloc或抓完整22GB堆，避免影响live baseline和资源占用。

下一阶段可以评估版本化trace策略：输入实体/捕获视图按ID+digest引用、共享不可变操作数、嵌套rule stages避免重复保存同一inputs，以及流式事件/检查点存储。任何策略都要保留伤害与选择的必要输入、因果ID、随机样本和回放比较合同，明确新的trace身份；不应简单删掉证据字段后宣布等价。本轮不据此重新打开已冻结核心，也没有实现这些优化。

```powershell
..\.venv\Scripts\python.exe tools/audit_m7_trace_storage.py --ticks 30
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m7_capacity_review.py -q
```

审计工具限制prefix最多180帧，仅写新的审计输出。后续当前完整suite与baseline的结果归root管理，本文不替代它们或formal0/36状态。
