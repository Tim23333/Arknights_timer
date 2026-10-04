# M20 source-isolation independent review

新独立候选 `campaign_m20_dormant_source_candidate` 的 core 为 `b506ee18e7137c3658f1fe8ce77b4b612bf48bceb9b02446f2dfcb7d91abbf0d`。本页是 bounded review，没有 promotion 或完整阶段/native receipt；旧 db6134、其已完成 baseline、initial失败证据和旧helper字节不改。

实际输入 `packages/campaign/chapter01_stage_models/m20_source/level_main_01-11.dormant.partial.json` SHA `52a7432cc87e3806afd6d63c7a1fd2f06782caf34bdebde4cbc176b9ea7c7111`。工具先读bytes/核SHA，再JSON解码，assert实际import来自新候选且implementation_digest==b506；没有仅凭metadata判断新路径已执行。

`tools/experiments/m20_peer/source_revision_review.py` SHA `22dbf426e565c347ef25078fc95553854dfe3dbe82ea3f8184fc2bc67ce21acd`，13个fresh独立cases通过。新报告 `validation/campaign/m20_source_peer/final.json` SHA `19e884e69e8b0d7c998f1c7d4fd2f5893ded766dc6ca2f8d4a126214656094e6`，core/source/package/helper/raw资产/catalog/preset开始与结束一致。

新wrapper没有改旧helper文件。它在新的进程内明确适配旧probe的bootstrap runtimeRoot，以及capacity case的输入builder/OUT到新source package；其余behavior expectations逐字保留。适配前的实际helper bytes SHA、逐项字符串替换与内存adapter SHA记录在report.helper_adapters。真实NPC source仍读取实际Character reference/Asset Typetree；普通generic cases维持原独立fixture。

每次make都把具体fixture写入独立 `.input.json`，读实际bytes并hash后解码，再传给Compiler/Engine；13份逐case输入路径/完整SHA/program/runtime及实际module路径在report.fixture_inputs，文件位于 `validation/campaign/m20_source_peer/fixtures/`。不是只锁模板包而遗漏fixture变化。

复核原九项全部通过：inactive目标SP/behavior/freeze旁路修复、alias与registry分离、激活起算lifetime、公开付费double activation回滚、directBehaviorAPI、晚激活emission snapshot、七类target effects隔离、实际NPC容量source1及CP/replay。

新增三个原source反例同独立数值预期通过：never-activated dormant source的SP effect保持active目标SP10、physical ATK20/DEF0不伤active目标HP50、random不消耗imp且无battle random branch。公开effects在求值condition/selector/random/calculation前拒绝此来源。管理路径的emit/activate/retire/remove策略保留，不扩大为所有inactive/dead来源均禁止。

强正对照仍通过：公开命令activate→t1真实发射speed10/距离2→t2source退场dead/activeFalse→t7已发packet造成20，HP50→30，CP与recorded-command replay精确相等。没有伪造已发packet元数据来绕过门。

旧M20文档摘要已纠正：真实 `m20_dormant_peer_db6134.json` 的 source_start/end是 `335ca3e...`，capacity fixture program `199bf951...`。此前写成0fd8是报告摘要错误，旧JSON字节不改。capacity case虽包含当时SNIPER/SP定义修订，仍没有Ptilopsis aura1.3独立数值断言；那项保持Root另两例范围，不能借本review扩大。

本批没有实跑完整1-11、Training card/UI、native callback/refund/壁钟语义。Registered revive和Dormant不执行death规则是新source实现字段，本13项未另造独立专门反例，不把作者验证迁作本review通过。
