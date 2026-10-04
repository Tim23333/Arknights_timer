# 模拟日志与自动清理

固定日志根目录为 `E:\ArkSimLogs`，配置文件是 `tools/simulation_log_policy.json`。
清理实现为 `tools/cleanup_simulation_logs_v2.py`，PowerShell 入口为 `Clean-SimulationLogs.ps1`。
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

立即清理所有已结束日志，包括工具目录、历史候选与备份中复制的运行捕获：

```powershell
.\Clean-SimulationLogs.ps1 -AllCompleted -Apply
```

`-AllCompleted` 将历史目录纳入扫描并取消十五分钟等待；不带 `-Apply` 时仅预览。
该选项仍保护活跃进程和打开文件，不能与 `-RunDirectory` 同用。
历史候选与备份中的源码、来源 JSON 和输入继续保留。
历史备份仅扫描 `unpack_work/*/ark_sim/validation` 和再嵌套一层身份目录的同类路径，
避免遍历游戏资源解包目录。

仅清理固定目录下的已结束日志：

```powershell
.\Clean-SimulationLogs.ps1 -Apply
```

立即清理一个已结束的指定运行目录（仍保留活进程保护）：

```powershell
.\Clean-SimulationLogs.ps1 -RunDirectory E:/ArkSimLogs/runs/manual -Apply
```

脚本只删除配置目录内逐个核对过的日志与运行捕获，不递归删除目录。
保留源码、关卡输入、操作脚本、来源资料和小验证结果。
正在运行进程的输出目录、打开的文件和最近十五分钟文件自动排除。
指定 `-AllCompleted` 或 `-RunDirectory` 时不按文件年龄排除，其他保护仍生效。
文件在预览后变化或被打开时拒绝删除。
历史完整逐事件证据删除后不可继续读取原日志恢复；对应小收据明确标记归档状态。

后续整关使用 `tools/run_campaign_disk_runthrough_v20.py`，参数与 V18 相同。
`--output` 指定保留的精简结果；实际日志自动转到固定 `runs` 子目录。
完成原仿真、检查点续跑和从头重放后，V20 保存小结果并调用清理脚本。
失败执行也保存精简退出信息，然后清理大日志，不累计失败捕获。
原 V18、V19 和已经启动的任务源码保持冻结；它们结束后由任务负责者用最新脚本补清。
清理结束会再次检查剩余文件，完成摘要记录实际删除结果；错误或仍有受保护日志时明确报告。

自定义机制场景、测试捕获与新的工具执行也必须将临时文件写入此目录。
源与验证摘要继续放入 `packages` 或 `validation`，大捕获禁止写入这些目录。
验证完成后调用同一清理脚本；需要人工暂留一次运行时，可在配置中添加明确保护目录，
完成审计后移除保护。

自定义命令可以使用通用自动清理入口。每次需要新的 `runs` 子目录；
命令参数中的 `{run_dir}` 会替换为实际目录，子进程同时获得 `ARKSIM_RUN_DIR`、`TMP`、`TEMP`。
标准输出和错误输出也写入这个目录，命令退出后保存完成摘要并清理。
例子中的短程运行只用于演示清理；需要续跑、数值核对和回放的任务应在同一受控命令中完成验证后再退出。

```powershell
$runDir = "E:/ArkSimLogs/runs/manual_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
..\.venv\Scripts\python.exe tools/run_with_log_cleanup.py --run-dir $runDir -- ..\.venv\Scripts\python.exe -m ark_sim run packages/custom/custom_guard.json --ticks 30 --output "{run_dir}/result.json"
```

成功与失败运行都执行清理；完成摘要保存真实子进程退出码和清理结果。
源码与输入不作为运行日志删除，打开文件、活跃运行 lease 和显式保护目录继续保留。

十五个已验证整关的小收据在
`validation/campaign/runthrough/archived_logs.receipts.v4.json`。
清理后进度入口最新为 `tools/campaign_runthrough_progress_v9.py`，
保持已完成历史身份并明确原始日志已删除，不伪称当前重新核对原日志。

中断恢复记录也按相同保留政策处理：原正向与检查点续跑已完成时，先认证其源码、输入、程序、
运行时及日志身份，只补缺失的从头重放证明。新版恢复工具会保存实际head检查点与外部命令游标，
不得将正向检查点伪装为中断head的检查点。
不同 JSON 编码的对象键序可能使 raw SHA不同；接受前仍要求源绑定的完整数值、状态、任务、
随机状态和事件序列一致，收据会注明比较格式，不将 raw文件缺失或摘要不同默认为通过。
