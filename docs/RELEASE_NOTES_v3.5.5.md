# ArknightsTimeline v3.5.5

v3.5.5 在 v3.5.4 扫描生命周期修复基础上，合并版本化本机 WebSocket 游戏与运维接口，并完成合并审查修复。

## 新增功能

- 新增仅监听 `127.0.0.1:8765` 的版本化 WebSocket 服务。
- 提供 `/v1/game` 游戏实时数据端点和 `/v1/ops` 运维状态端点。
- 支持按主题和频率订阅 battle、stage、enemies、characters、详情、Deploy、RNG 与质量指标。
- 新增独立 WebSocket/NDJSON 监控工具 `backend/ws_capture.py`。
- 更多自定义选项中可独立启用或关闭本机 WebSocket 服务。

## 合并审查修复

- 保留 v3.5.4 的 Guest/Deploy/Enemy/RNG QThread 生命周期、stopping 状态机和分阶段关闭逻辑。
- WebSocket 服务停止超时后保留线程引用，网络线程真正结束后才释放端口和生命周期状态。
- sequence 改为每客户端独立计数，避免多客户端正常消息造成虚假漏包。
- 每次新战斗生成新的 sessionId，并清除上一局公开快照。
- `/v1/ops` 禁止读取 Deploy 等游戏数据；补齐非对象命令、取消订阅和非有限频率校验。
- 高频发布按 topic 合并广播任务，没有订阅者时不创建广播 task。
- `scope: selected` 只采样请求 ID；全场重型详情采样上限为 5Hz，网络仍可发送最新共享缓存。
- 详情按 revision 序列化，避免每个 60Hz 基础帧重复深拷贝完整属性、Buff 和技能数据。
- Deploy 阶段、代理作战静态 journal 和实时操作均可通过 WebSocket 发布。
- 公开协议统一过滤地址/指针字段、地址文本与非有限浮点值。
- 监控工具默认写入 LocalAppData，不再硬编码 D 盘。
- 修复监控工具点击协议流时引用未定义变量导致的 NameError。

## 验证

- 主线完整后端测试：162 项通过。
- WebSocket 实际连接验证：多客户端 sequence、换局 sessionId、端点隔离和端口释放通过。
- WebSocket 运行状态下完整窗口关闭验证通过，无残留网络线程或 memory worker。
- PyInstaller 正式版和测试版构建验证通过，WebSocket 服务模块与 websockets 运行时已正确收集。
