# ArkSim 开发约定

## 当前底座

后续战斗模拟器工作统一基于 **V2 `ark_sim`**。实际接口见
[V2_IMPLEMENTATION.md](docs/V2_IMPLEMENTATION.md)，内容字段与示例见
[V2_AUTHORING.md](docs/V2_AUTHORING.md)，设计目标见
[ARCHITECTURE_V2.md](docs/ARCHITECTURE_V2.md)。

- 新功能、公式修复、干员、敌人、技能、Buff、状态机和关卡扩展在 V2 中实现。
- 内容放入 `packages/`，操作与场景输入放入 `scenarios/`，当前验证放入 `tests_v2/`。
- 新网页、AI、编辑器和其他集成消费 V2 的 `Compiler` / `Engine` / `Simulation` 接口。
- 内核保持通用；方舟公式和数值算法由规则集、表达式、计算图或提供器定义。
- 按关卡和选定配置收集实际依赖，未实现能力明确报告；分别记录模型验证和客户端对照。

## V1 历史边界

`ark_emulator/`（含阶段一原型）、旧 `Simulator` / `AgentEnv` / 网页、`examples/` 与
`tests/` 为历史实现，仅用于离线数据提取和代码、行为样本参考。目录清单见
[V1_HISTORY.md](docs/V1_HISTORY.md)。不要将其继续用作当前开发、运行或验收底座。

离线提取工具可以读取旧数据及解析辅助代码，输出固定、可追溯的 JSON 内容。
V2 运行时不得导入或委托 V1 的战斗、地图、波次、属性、伤害、技能、Buff 或随机数实现，
也不得在缺失能力时自动切回 V1。历史覆盖数字和扫描结果不能作为 V2 的通过证据。

## 模拟日志保留政策

用户要求大日志只在执行期间保留。所有后续事件、检查点、回放与测试捕获写入
`E:\ArkSimLogs\runs`；源数据、关卡包与精简收据不属于日志。
后续整关统一使用 `tools/run_campaign_disk_runthrough_v20.py`，完成仿真和CP/head验证后自动执行
`tools/cleanup_simulation_logs_v2.py`。其他机制工具通过 `tools/run_with_log_cleanup.py`
执行，或在验证结束后调用同一清理脚本。手工入口为 `Clean-SimulationLogs.ps1`。
已经启动的旧工具保持冻结源码，由任务结束后的同一清理脚本补清。
禁止继续在 packages/validation/unpack_work 写大体量事件捕获；已结束失败场景也保小结果后清理。
历史证据删除是用户授权的保留政策，精简收据保原身份，不能声称原日志仍可读取。
详情见 [SIMULATION_LOGS.md](docs/SIMULATION_LOGS.md)。

## 验证

当前生产底座含 `buff.lifetime_rate`、六项元素契约和复生来源判定，共106项。
旧数量测试仍保留历史 98 契约断言字节，
当前完整回归入口为 `..\.venv\Scripts\python.exe tools/run_primary_v2_suite.py`。
它仅替换该历史测试为精确旧98项加已验证新契约的逐字段及不可变性验证，其余1218项保持不变，
并使用固定E盘运行目录，在完成后自动清理临时日志。
使用原始 `pytest tests_v2 -q` 会执行保留的历史数量断言；不得将其失败与当前完整入口混淆。
内容修改同时使用 `python -m ark_sim validate <内容包>` 检查实际引用。
涉及首关执行语义、规则、调度或回放的变化，运行 `tools/verify_v2_baseline.py` 更新相应证据。
纯文档和历史标记无需重新执行长程模型。

回放与检查点锁定源码、内容和算法身份。修改 V2 实现后不要将旧结果重新标为新版本通过；
保持旧证据的版本身份，并为新实现生成证据。仓库 `.gitattributes` 保留 V2 源码及固定内容的原始字节，
避免 Git 换行转换使已经验证的回放身份变化。提交仅包含本任务改动，保留工作区内无关的解包和打包产物。
