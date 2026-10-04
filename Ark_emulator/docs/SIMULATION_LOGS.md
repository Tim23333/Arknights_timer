# 模拟日志与自动清理

固定日志根目录为 `E:\ArkSimLogs`，配置文件是 `tools/simulation_log_policy.json`。
`runs` 存放执行期间的大体量事件、检查点和回放，`receipts` 保存精简结果，
`cleanup` 保存删除清单、字节数和仍在运行的文件。

在模拟器目录手工预览：

```powershell
.\Clean-SimulationLogs.ps1 -Legacy
```

实际清理历史和当前已结束日志：

```powershell
.\Clean-SimulationLogs.ps1 -Legacy -Apply
```

仅清理固定目录下的已结束日志：

```powershell
.\Clean-SimulationLogs.ps1 -Apply
```

脚本只删除配置目录内逐个核对过的日志与运行捕获，不递归删除目录。
保留源码、关卡输入、操作脚本、来源资料和小验证结果。
正在运行进程的输出目录、打开的文件和最近十五分钟文件自动排除。
文件在预览后变化或被打开时拒绝删除。
历史完整逐事件证据删除后不可继续读取原日志恢复；对应小收据明确标记归档状态。

后续整关使用 `tools/run_campaign_disk_runthrough_v19.py`，参数与 V18 相同。
`--output` 指定保留的精简结果；实际日志自动转到固定 `runs` 子目录。
完成原仿真、检查点续跑和从头重放后，V19 保存小结果并调用清理脚本。
失败执行也保存精简退出信息，然后清理大日志，不累计失败捕获。
原 V18 和已经启动的任务源码不改，避免破坏本次冻结运行身份。
既有任务由 `tools/watch_completed_simulation_logs.py` 在进程退出后清理。

自定义机制场景、测试捕获与新的工具执行也必须将临时文件写入此目录。
源与验证摘要继续放入 `packages` 或 `validation`，大捕获禁止写入这些目录。
验证完成后调用同一清理脚本；需要人工暂留一次运行时，可在配置中添加明确保护目录，
完成审计后移除保护。

十二个已验证整关的小收据在
`validation/campaign/runthrough/archived_logs.receipts.v1.json`。
清理后进度入口为 `tools/campaign_runthrough_progress_v6.py`，
保持已完成历史身份并明确原始日志已删除，不伪称当前重新核对原日志。
