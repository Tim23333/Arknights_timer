# ArknightsTimeline v3.5.6

v3.5.6 修复 v3.5.5 中 RNG 扫描服务完成所有权转移后仍引用已删除 Qt Signal 的问题。

## 核心修复

- `RngService` 新增线程安全的状态监听器替换接口。
- RNG 初次扫描完成后，运行期状态通知从短生命周期 `RngScanWorker.log` 转移到主窗口持有的 `rngRuntimeStatus` Signal。
- 停止或丢弃 RNG 服务时主动解绑状态监听器，避免关闭期间残留窗口回调。
- 状态监听器异常被隔离在展示边界，不能再终止 `ak-rng-poll` 后台线程。
- 新一局检测、RNG 对象看门狗、延迟重扫与历史/预测更新不再受已删除 Qt 对象影响。

## 回归测试

- 使用 Shiboken 真实删除 `RngScanWorker` 后触发运行期状态通知，确认服务不再持有旧 worker。
- 从独立线程模拟新一局 RNG 对象更换，确认状态经 Qt Signal 返回主线程。
- 让监听器主动抛出 `RuntimeError`，确认真实 polling thread 保持存活并可正常停止。
- 完整后端测试、RNG 测试、静态编译及离屏关闭测试均通过。

## 发布文件

- `ArknightsTimeline_v3.5.6.exe`
  - 大小：86,575,729 字节（82.57 MiB）
  - SHA-256：`8E13D7608A9ADC8D345AD83FD761663B891397F3294804B716F2996AB7DB02FF`
- `ArknightsTimeline_v3.5.6_Test.exe`
  - 大小：86,574,391 字节（82.56 MiB）
  - SHA-256：`1798242E1F607F973F26E739EDC3442310B142E530BB01339E599F4070430C3D`
