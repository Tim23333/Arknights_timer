# 实时 Web UI 与字段策略

## 入口与目录

源代码启动（在仓库目录执行）：

```powershell
python backend/desktop_app.py --webui --webui-port 8768
```

主程序继续负责现有寻址、采集与线程生命周期；默认桌面入口保留。新增 `--webui` 将浏览器作为主界面，HTTP 仅监听本机。Windows 原有管理员启动流程仍适用。关闭浏览器标签不会退出后台主程序，需要停止对应 Python 进程或关闭主程序。

- `webui/`：原型落地的独立网页、样式、数据模型与 Node 测试；不需要 npm 安装或额外构建。
- `backend/app/field_policy.py`：注册表、三开关、依赖验证、不可变策略代际、投影及字段状态。
- `backend/app/services/webui_server.py`：受限本机 HTTP 与同源 JSON 命令边界。
- `backend/app/services/webui_runtime.py`：Qt 主线程命令桥、独立本地展示快照与生命周期。
- `backend/app/services/websocket_api.py`：外部 WS 投影与完整批次发布挂钩。
- `backend/app/services/websocket_docs.py`：两个前端共用的实际字段清单和协议说明。
- `frontend/`：原有离线排轴工具，未替换成新实时界面；需要已有前端构建产物。

## 开关语义

每个注册字段只有 `collect / display / publish` 三个布尔值，没有自动模式。注册表包含 193 项：189 项公开策略，4 项不可关闭的内部身份/会话/帧守卫前提。敌人65项、干员62项，详情各11项，计时器13项，RNG15项，质量8项，关卡/操作各2项。清单以运行时注册表为准。

采集关不是停止显示：适配器不解析、不派生、不合成该字段，跳过独占额外读取链；共享基础块可能仍因其他开启字段读取。内部保证身份与帧守卫的读取不能关闭。采集关压过消费者开关：即使显示/发布保留为开，也不会得到该字段的当前值。

采集依赖必须一并调整。修改上游输入、保留下游派生采集会拒绝整笔事务；前端展示具体错误，不自动开启其他字段。单项 UI 操作可先关闭下游再关闭上游；HTTP 支持一次提交多个开关。

策略写盘成功后才接受新代际；采样一轮内持有同一不可变策略。改变采集时清空当前值缓存和旧设备预取计划，下一轮重新读取；不必要地清空所有拓扑不是要求。展示/发布变化重投影已接受数据，不假装重新读过。生产代际、源会话或对象身份不匹配的迟到结果被丢弃。

## 新鲜度

实体保留原始属性类型，另外携带 `fieldStates[字段ID]`。每项说明 `sourceFrame / acceptedFrame / latestKnownFrame / generation / collectionState / reason`。整批还有 `meta`：策略代际、会话、来源/结束帧和时间戳。计时器与敌我整帧来源不混为一谈；battle 的逐字段状态分别记录两类生产来源。

`sourceFrame` 不会被完成时查询的更新帧覆盖；`latestKnownFrame` 不是再读游戏内存，而是非阻塞读取计时器已知帧。来源帧较旧不统一禁发：静态配置、历史操作、异步详情保留实际来源；高频敌我仍执行原有完整帧守卫。失败返回不可用，不回填上次成功值伪装当前帧；合法 0、false、空数组不视作失败。

停止、重扫、换设备、换关卡使当前通道失效。最终战斗缓存只作为明确的存档/导出，不能重新作为实时来源。异步详情有独立通道，检查策略、源会话、实例身份与读前/读后帧，不修改主读取缓存。

## WS 挂钩与版本

新端点为 `/v2/game`、`/v2/ops`，旧 v1 客户端需改路径并适配可缺省字段与状态。默认速率、实际协商范围、逐字段公开路径由两个前端的“接口说明”展示。

已有生产者继续使用领域适配器 `publish_timer / publish_runtime / publish_deploy / publish_rng`。新字段先注册 `FieldSpec` 的路径、依赖和默认开关，再在完成来源校验后调用 `publish_fields(domain, values, source_frame=..., latest_known_frame=..., policy_generation=...)`。该挂钩提交完整接受批次，替换领域快照，不把不同时刻的单字段累加成假完整帧。它处理开关与传输，不承担新游戏偏移识别。

实体域 `enemy / character / enemy_detail / character_detail` 必须传非空字符串 `entity_id`，值位于 `data.items[]`，不是批次根层；例如 `publish_fields('enemy_detail', {'enemy_detail.buffs': []}, entity_id='enemy-1', source_frame=0)`。详情同样执行采集、展示和发布策略；无效帧以空 items 和不可用状态发布，旧策略代际不接受。

首次订阅快照、订阅确认、命令错误及完整操作历史回复使用有界可靠 FIFO，不被实时帧挤掉。实时快照按主题只保留最新待发值；不同主题不互相覆盖。可靠回复待发超过 32 条时仅关闭该过载客户端（状态码 1013），外部程序需重连和重新订阅，不保证断线后的消息送达；序号在实际发送时递增。换局及策略代际仍在发送前校验，旧缓存不会因可靠排队而绕过校验。

网络线程不读取游戏内存或 Qt 控件。WS 关闭不影响本地展示。WS 自检真正建立订阅，逐项检查值与状态，区分没有场上对象、未采集、不可用和连接失败，心跳不能证明游戏字段可达。

## 当前限制与验证

敌人详情中的 talents/dynamicAbilities/equipment/attackRange/effectFrames 是预留来源，没有现成读取值时明确标记 `unsupported_in_source`，不虚构数据。`enemy_detail.skills` 复用同一完整帧的 `enemy.skill` 采样；基础技能不可用时详情同样不可用。异步详情读前、读后逻辑帧不一致时，详情字段标记 `frame_inconsistent`，不作为当前值发布。已离场干员的伤害/治疗历史按字段分别保留来源；关闭某字段的采集立即清除该字段历史，重新开启后只接受新的成功采样。原有暂停检测问题保留，未在本次声称修复。无技能根对象的派生状态采取保守不可用策略，后续可单独验证。

测试覆盖纯策略、真实本机 HTTP、真实 Qt 命令桥、源适配器与真实 WS 订阅；不需要模拟器即可运行回归测试。`backend/test_webui_runtime.py --serve` 是关闭采集线程的界面 QA 入口，不是游戏实测或生产启动方式。GUI 浏览器验证、关卡内性能与最终 exe 打包仍需要单独验收。

实现遵循 Qt 的队列式线程交互与有界传输，参考：[Qt QObject 线程规则](https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-qobject.html)、[websockets 服务端文档](https://websockets.readthedocs.io/en/stable/reference/asyncio/server.html)。HTTP 层只面向本机受控应用，不视为公网生产服务；[Python http.server 的边界说明](https://docs.python.org/3.12/library/http.server.html)。
