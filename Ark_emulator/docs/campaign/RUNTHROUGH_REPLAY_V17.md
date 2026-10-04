# V17 旧核心完整重放证明

工具 `tools/finish_pending_runthrough_v17.py` 专用于已有真正完整正向终局、
已有实际检查点续跑一致、但公开命令从开局重放未通过的旧核心记录。
工具不修改旧核心，也不将旧结果迁移到新核心；原失败报告保留为逐字节存档。

启动前核对运行模块目录、implementation digest、原正向报告、输入字节、
完整 JSONL 日志 SHA、已通过续跑的磁盘检查点 SHA、旧续跑 source guards、
重编译 program fingerprint 以及 replay 的 until/seed/runtime 身份。

工具先实际执行一个 bounded 小样例：在原 program 上保存并重新加载检查点，
复现公有命令在非零 submitted_at 的提交顺序，分别调用原 replay 与分段 replay，
比较 snapshot/events/event_count/continuation_state。它还实际比较旧 snapshot
展开路径与流式观察快照 SHA。小样例不通过时不得开始大重放。

完整重放从开局 `Engine.create` 开始，按 record order 和 submitted_at 提交所有命令。
用公开 `Session.advance` 每段最多200 ticks推进；返回 clock，避免
`Simulation.advance` 自动构造完整 snapshot。event journal 保持全部记录，
最后只通过旧来源固定的 `campaign_streaming_evidence.observations`
对 immutable event references 做有界 JSON 编码；没有丢弃、过滤或 thaw 全部历史。

新 proof report 只有在全部原 observations 完全一致、source guards 和旧核心
identity 前后保持一致时才 `passed=true`。`actual_helper_exit` 记录工具真实退出选择。
它复用的大检查点通过证据附路径与 SHA，保留的原完整正向报告和完整日志也附 SHA。
执行或哈希失败时记录真实异常、阶段和 traceback，原失败与原报告都保持可审查。

该证明只补齐模型重放证据，不改变独立 review、客户端精度或完整机制消费结论。
