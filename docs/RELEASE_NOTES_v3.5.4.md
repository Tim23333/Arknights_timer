# ArknightsTimeline v3.5.4

v3.5.4 是针对 v3.5.3 自动换关刷新闪退的稳定性修复版本。

## 核心修复

- 修复自动刷新中的 Deploy 扫描超时后，旧 `QThread` 尚未退出便被下一轮扫描覆盖，导致 Qt 原生闪退的问题。
- 修复 Deploy 实时轮询只等待 3 秒便释放仍在运行的线程引用的问题。
- Deploy、Enemy、RNG、Guest 四类扫描任务统一改为在 `QThread.finished` 后消费结果和释放引用。
- 自动刷新超时进入 stopping 状态；旧 worker 真正退出前禁止新一轮刷新重入。
- 每次检测到时钟归零后，等待新关卡 `game_time` 与 `frame_count` 连续两次正向增长，再启动 Deploy/Enemy/RNG，避免命中已销毁的旧 `BattleController` 并退化为 1.8GB 全堆扫描。
- 新的关卡归零事件会取消上一局仍在进行的刷新，并通过 generation 只保留最新一局的等待链。
- 程序关闭改为分阶段异步回收所有扫描、轮询和 memory worker，后台任务退出前不会销毁窗口所有者。
- 修复 RNG 服务停止时未等待 polling thread、未完整关闭 TCP/进程句柄和延迟重扫的问题。
- ADB 切换会等待旧 Deploy/RNG 读取完全退出，避免旧设备结果污染新连接。

## 诊断与验证

- 增加自动刷新 reset generation、时钟就绪、步骤启动/超时和 worker finished 生命周期日志。
- 增加真实 Qt 子进程回归测试，覆盖旧版 Windows `0xC0000409` 快速失败路径。
- 增加 Deploy/Enemy/RNG/Guest worker、RNG service、连续归零和分阶段关闭测试。

## 兼容性

- 游戏数据、运行时偏移和前端资源沿用 v3.5.3 已更新内容。
- 用户配置文件格式不变，可直接覆盖升级。

## 发布文件

- `ArknightsTimeline_v3.5.4.exe`
  - 大小：86,536,258 字节（82.53 MiB）
  - SHA-256：`10D17739D905140585DC1BD7B9D00B9CC493E638528EEF84220F29C6809F6A19`
- `ArknightsTimeline_v3.5.4_Test.exe`
  - 大小：86,535,769 字节（82.53 MiB）
  - SHA-256：`9B923EF0836D7A1BC849E96345E67265C33526DB129D885F93741046BD1E166B`
