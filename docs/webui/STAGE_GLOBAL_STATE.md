# 关卡全局状态

本工作区汇总当前战局的时间、运行状态、波次、地图和当前实体布局；不接入战斗模拟器，不写游戏内存。字段格式与枚举以 `backend/app/contracts/stage_global.schema.json` 为唯一权威。

## 三个可独立订阅的主题

| 主题 | 数据 | 默认频率 / 可协商范围 |
|---|---|---|
| `stage_global` | 主时钟引用、关卡身份、运行状态、模式、波次及等待 | 20 Hz / 0.2–60 Hz |
| `stage_map` | 完整配置底图与当帧地块类型/游戏缓存选项 | 1 Hz / 0.2–60 Hz |
| `stage_units` | 当前实际在场的敌人与我方布局 | 10 Hz / 1–60 Hz |

```json
{"type":"subscribe","requestId":"stage-demo","topics":{"stage_global":{"rateHz":20},"stage_map":{"rateHz":1},"stage_units":{"rateHz":10}}}
```

沿用现有 v2 信封，消息类型为 `<主题>.updated`，字段位于 `data`。订阅频率是发送上限，不触发额外扫描，不保证每个游戏逻辑帧都送达。关闭 WS 服务不影响本地展示。这里只说明新增主题；连接地址和通用命令见程序右上角「接口说明」。

## 数据字段

| 策略 ID（前缀 `stage_global.`） | 路径 | 含义 |
|---|---|---|
| `gameTime` / `fixedFrame` | `clock.gameTime` / `clock.fixedFrame` | 已接受主时钟的秒数和逻辑帧，不新建一条时钟读取链 |
| `stageName` | `identity.stageName` / `identity.stageId` / `identity.levelId` | 同局已读取的名字及身份；三个路径共同遵守关卡身份开关，不从本地数据表猜填 |
| `mapId` | `identity.mapId` | 游戏当前提供的地图标识，不用关卡 ID 顶替 |
| `state` | `runtime.state` / `runtime.stateCode` | 运行状态名称及原始编号；一个开关共同控制这两个路径 |
| `isPaused` | `runtime.isPaused` | 暂停键集合的实际状态，不靠时钟不变猜测 |
| `speedLevel` | `runtime.speedLevel` | 游戏配置速度档位 |
| `timeScale` | `runtime.timeScale` | 实际 Unity 引擎倍率，覆盖已验证的暂停/慢动作/1 倍/2 倍，不用暂停保存值替代 |
| `mode` | `mode` | 只读模式/handler 类型及支持状态；未知布局不套用候选偏移 |
| `currentWave` | `waves.current` | 当前活动波次索引、序号、当前配置总数及配置等待值 |
| `nextWave` | `waves.next` / `waves.nextSelection` | 已确定下一波，或 `known / pending / none / unknown`；共同受一个开关控制 |
| `nextWaveEnemies` | `waves.nextEnemies` | 配置生成项及数量、片段/行动/路线索引、间隔和选择条件，不是已实例化敌人的列表 |
| `waveGate` | `waves.gate` | 活动调度阶段、管理列表与模式条件，不把管理列表为空解释成地图敌人已清空 |
| `waveWait` | `waves.wait` | 当前活动等待及计数/时基，不代表整个下一波一定还有这些秒数 |
| `map` | `map` | 完整配置二维底图，包括装饰格/禁止格 |
| `mapRuntime` | `mapRuntime` | 同轮读取的当前地块类型与缓存选项，失败不从底图补成实时值 |
| `enemyLayout` | `enemyLayout` | 当前敌人实例及坐标/游戏行动状态，不包含离场历史与尚未实例化预设 |
| `allyLayout` | `allyLayout` | 当前干员/召唤物/装置实例，格子与可信朝向，不用携带编队/地图机关配置补当前实体 |

配置底图和运行时图均使用 `tiles[row][col]`，左下角为零点，`x=col / y=row`，向右/向上递增。配置顶部首行只转换一次；前端展示从上往下是视图转换，不改变公开坐标。未知原始 `tileKey` 保留，不裁边、不把出界实体夹回边缘。

朝向来源 `character.direction` 使用 0 上、1 右、2 下、3 左。未成功读取不能把 Python 默认 0 当作“上”。敌人的 `stateName=MOVE` 只表示游戏行动状态，不证明一定发生物理位移；等待/传送等仍保留当帧实际值。

## 空值、来源帧与失败

`0`、`false`、`[]` 都是有效值。空值必须和 `fieldStates[字段ID]` 一起解释：

- `mapId=null` 且成功记录的理由为 `not_provided`：游戏未提供地图 ID。
- 下一波为 null，`nextSelection=none`、理由 `no_next_wave`：普通顺序调度已无后续配置。
- 下一波为 null，`nextSelection=pending`、理由 `selection_pending`：模式尚未确定下一波，不能当作最终波。
- `remainingSeconds=null`、`secondsBasis=unknown`：秒数换算未验证，展示实际恢复次数；不把该次数直接除以 30 当作秒数。
- `collectionState=unavailable`：读取/绑定/版本/守卫等未通过；`not_collected`：采集已关闭。这两者都不能算自检收到有效值。

`fieldStates` 保留 `sourceFrame / acceptedFrame / latestKnownFrame / generation / collectionState / reason`。主时钟、运行采样、静态配置各自保留来源；组合数据没有一个真实共同帧时，根 `meta.sourceFrame=null`，运行采样参考 `meta.runtimeFrame`，逐字段记录才是判断依据。落后不统一丢弃，静态配置与动态字段按各自性质解释，不把旧帧重标为新帧。

顶部来源区分别展示“运行采样帧”和“时钟来源帧”，数值使用固定宽度位置。
主时钟更新只刷新自己的帧号，不触发棋盘、表格或完整 JSON 的重绘；不将两条来源合成为虚构的共同帧。

动态链失败时只使相关字段不可用，独立主时钟和同局有效底图可继续可见。前端保留上一次有效显示并持续标“旧”，包括地图、敌我布局和下一波配置表；不再因超过 500 ms 而清除，仍保留原来源帧。完整 JSON 与 WS 始终使用后端原始状态，不将展示副本作为当前样本发布。合法空数组和已确认的空值立即覆盖旧显示；关闭采集、换局、切设备、重新扫描、共享停止或策略代际变化仍立即清除旧值。

`meta.sessionId` 区分战局；`sessionOrigin` 是后端进程内服务实例的随机身份，`sessionOrdinal` 是该实例从 0 开始递增的换局序号，不是游戏逻辑帧。两者由服务写入，挂钩不能覆盖。浏览器据此拒绝首次连接时另一条 SSE 通道迟到的旧局回放，也允许真正的新局与重启后的新实例。任一全局/地图/布局/主时钟主题先收到新局时，旧局其他槽位立即清除，不等待三个主题同时到齐；同局不同来源帧仍可展示，明确标注混合来源。

## 三层开关与验证边界

### 地块 blackboard（兼容新增）

`stage_map.map.tiles[row][col]` 和 `mapRuntime.tiles[row][col]` 增加：

- `blackboard`: `[{key: string, value: number, valueStr: string|null}] | null`。
  value 为解码后的有限浮点数，不是原始位模式；不推断单位。
- `blackboardMeta.state`: `available`（包含合法空数组）、`absent`（确认空指针）、
  `unavailable`（读取失败）。失败原因见 `reason`，无失败时为空字符串。
- `blackboardMeta.source`: `initial_configuration` 或 `runtime_parameters`。
  后者表示来自当前 Tile 对象，不宣称参数随游戏变化，也不等同于当前地块模式。

初始链为 LevelData → MapData → TileData.blackboard；运行时链为 Map → Tiles2D →
Tile.m_blackboard。复用现有内存通道与运行帧守卫，批量读取并校验类型、容量、版本、
字符串和有限数值。失败只使参数未知，不拿初始配置代替运行值，不使基础地块整批丢失。
初始参数按战局配置缓存，运行时参数每轮读取；关闭对应 map/mapRuntime 采集即停止其读取。
发布继续沿用这两个已有字段的策略和来源帧，没有新增独立 WS 主题或改变旧字段。

采集、展示、WS 发布均为开/关。关闭采集停止该字段解析/派生/合成并撤销独占读取需求，共享基础块仍可被其他字段读取。关闭来源字段时，其布局/状态副本也遵守来源开关，不能从另一主题绕过。修改有硬依赖冲突时显示具体原因，不自动打开源字段。

Android 2.7.81 普通模式的活动协程成员归属已现场验证，生产读取启用逐轮成员、所有者及结构校验；不等于已验证所有模式。模式专用安卓布局、恢复次数时基未经核验时，以合同理由显示未知/不可用，不用数值“看起来合理”宣称验证成功。实机验证结果与尚未覆盖场景记录在测试证据中；自动样例不等于真实游戏已覆盖全部模式。
