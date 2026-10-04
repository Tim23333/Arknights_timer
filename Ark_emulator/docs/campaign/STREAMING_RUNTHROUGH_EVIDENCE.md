# 全程证据流式导出

新工具 `tools/campaign_streaming_evidence.py` 与 `tools/run_campaign_streaming_runthrough.py` 保留完整事件、全部数值与顺序，不删除trace、降采样或关闭计算记录。当前live旧runner继续保持字节，新入口单独使用。

canonical JSON逐节点输出，完整snapshot/events哈希与旧 `contracts.digest` 精确相等；另比较World、future scheduler、完整RNG、反应预算及runtime/program身份形成continuation_state哈希。完整journal按原ID顺序保存UTF-8 JSONL，原始payload全部保留。输出checkpoint、command replay，以及original/CP阶段报告，便于长程发生问题后保留已有证据。

实际11项测试通过：Mutable/Frozen数据哈希相等、Unicode/转义/数字、真实V2全snapshot/events、只读状态、完整JSONL往返、非finite拒绝以及完整3漏怪life99996/CP/commands replay。短场景report `validation/campaign/streaming_evidence/runner_test.json` 保存全日志身份。此检查不等于主线整关或客户端准确性。

5000条synthetic嵌套事件的序列化分配对照：旧完整树峰值16,453,778字节，新流式峰值12,876字节，两个SHA完全相同。实际耗时约1.03秒与6.95秒，流式实现牺牲部分导出速度降低额外峰值。证据 `serialization_allocation.json` 只证明序列化分配，不证明内核事件日志内存已优化；内核存储另由M27独立候选量化/实现。

新1-12资格包的1800刻探索正在使用此runner；完整事件仍在active Simulation保留，退出时流式写出。语义准确性仍需实际游戏原始对照，report不自证批准。

## 实际输入绑定修复

独立peer复现旧streamrunner的读取窗口：计算文件SHA与实际JSON解码分开读取，第二次读取被替换为seed72后，runner仍可用磁盘seed71字节宣称identity stable。完整反例与原始fixtures已封存 `validation/campaign/m26_content_peer/stream_input_identity/counterexample.json`，旧runner/live前缀保持字节，不能作为最终证据门。

新入口 `tools/run_campaign_streaming_runthrough_v2.py` 对package/commands各读取一次，直接计算实际decoded bytes的SHA，再decode；before/report与该SHA绑定，end对照现文件。3漏怪完整CP/replay已通过，独立复核继续。当前1800tick旧runner只用于探索，不提升正式验收。

同类模型trace导出／比较工具已封旧字节到 `validation/campaign/trace_comparison/history_separate_input_reads` 并修为单次actual input read，新增输出文件身份单独保存。中途换包反例现在被拒绝，2项input绑定测试通过；旧工具旧报告保留原身份。

v2入口独立五项已通过：完整2漏怪/99997+CP/回放，全journal；第二读换包、第一decodedseed漂移、commands漂移、helper末尾漂移均identityFalse/passFalse/exit1且完整报告保留。报告 `validation/campaign/m26_content_peer/stream_v2/final.json` SHA `0a5f843e3286276156dc8ac0b11f9d98efd2fb89bb8033870f974e561b70ab6f`。

## 持久化检查点顺序

独立M27peer实际发现canonical排序checkpoint对象键会改变恢复后resource迭代顺序：原hp,z,a资源在下一刻产生z→a事件，JSON排序恢复后变a→z；最终资源值相同但完整因果日志不同。v2使用内存checkpoint续跑，不能据此证明存盘checkpoint恢复。原反例与source保持。

新 `tools/campaign_ordered_checkpoint.py` 保留对象insertion order，`run_campaign_streaming_runthrough_v3.py` 锁实际存盘SHA、立即重读，并在续跑前再次从该字节恢复。Canonical snapshot/events哈希仍只用于数值证据，不改变运行checkpoint。3项测试通过：存盘顺序精确续跑、旧排序真实反例、存盘字节改动拒绝；v3完整3漏怪/99996、durable CP/commands replay实过。独立复核继续，live1-12 v2工具不改。

后续实际失败路径保留：v3二次CP读漂移虽拒绝但最终report缺失；v4捕获CP读取/restore/续跑及replay异常，8独立case通过，另发现末尾helper缺失仍只抛异常。新v5逐项记录completion source/core读取失败，sourceErrors与identityFalse写入最终报告，完整3漏怪/CP/replay已过；独立9case复验继续。每版旧源码/反例单独保留，运行中的v2来源保持冻结。

v5独立九项已实际通过，报告 `validation/campaign/m27_roster_peer/stream_v5/final.json` SHA `cd7243b44c258c037666524dac3e1ea2247c221461d7c3a997ac1e2faedea305`：实际文件恢复保z,a资源事件原序；三CP失败保checkpoint_error、passedFalse/exit1、完整journal及独立replay结果；末尾helper缺失保存None/source_errors并正确拒绝。新1-11qualified完整执行已使用v5。旧M23 runner全树序列化在终局发生MemoryError，作为真实导出失败记录保留，不算全程收据。

V6另锁定只读diagnostic helper，每100刻保存alive敌人的实际HP/位置/路线状态、blocker/casts/timeline与事件数至progress.json，便于识别长程僵持。独立读取前后完整CP相等，完整3漏怪/durableCP/replay通过。不会用诊断文件代替完整状态/事件收据；现有v2/v5live来源不改。
