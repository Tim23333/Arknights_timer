# M7 0-10 空间来源审计与可替换 profile 方案

本轮新增 `tools/build_campaign_spatial_profiles.py` 与 `packages/campaign/spatial.profiles.json`，
不修改任何 M6 源码、包、测试或证据，不集成现有 0-10 model，不提供审批收据。
产物 schema 为 `ark-sim/spatial-source-proposals/v1`，是来源与方案记录，**不是已经编译实现的V2包**。
`runtime_integrated=false`、`client_validated=false`、`formal_stage_approved=false`。

## 已确认字段和发生次数

锁源 native `level_main_00-10.json`：35次SPAWN，其中33次引用非零
`spawnRandomRange={x:.2,y:.2}`，route11和17各1次为零；全部 spawnOffset为0。
19条原路线均 `allowDiagonalMove=true`、三个visit flags=false；未引用的0/10是E_NUM占位。
当前 options.steeringEnabled=true，reachableCheckIgnoreStartTile=false，randomSeed=953816614。
所有MOVE/WAIT checkpoint的reachOffset为0、randomizeReachOffset=false、reachDistance=0。
这些是源数据值；reachDistance0的运行默认解释不能通过空声明推导。

新 builder逐项记录全部routes、原始point、行轴转换、引用次数、起终格完整tile记录。
它校验35/33的发生次数；任何相应源变化会明确报错，而不是继续使用本轮预算。

五个enemy的原生 root GameObject附属 MoveController field shape直接从CAB读取，验证M6 enemy
source reference中的CAB SHA，保存root GO/component/script path IDs和精确单精度字段。

| 原生敌人 | steeringFactor | maxSteeringForce | halfBodyWidth |
| --- | --- | --- | --- |
| slime / mob / wteeth / gopro | 8 | 10 | 0.20000000298023224 |
| yokai | 20 | 100 | 0.20000000298023224 |

组件归属来自精确enemy root GO；MoveController类型名称通过字段shape与dump类对应，
不是把全CAB里60个其他enemy的 mover都误认为该角色。上述数值不能代替力的合成公式。
本关tile blackboard/effects为空，不存在能据此恢复steering主体的BSON计算图。

## 方法声明与方法体严格区分

同时检查并锁定 `Ark_data/dump.cs` 与 `Ark_data/Il2CppDumper_current/dump.cs`。
每份记录14个相关类型、62个符号的准确行号、签名、RVA注释、声明类别。
两份版本的行号/RVA不同，不能互换地址。主要证据：

| 关联结构/符号 | 确认到什么 | 不能确认什么 |
| --- | --- | --- |
| RouteData | Vector2 spawnRandomRange/spawnOffset、bool diagonal/visit flags、GridPosition start/end | radius还是full width；两轴分布、轴顺序、zero-axis是否耗样本 |
| Route.GetSpawnPosition / GetSpawnOffset | 两个返回Vector2的方法都存在 | 哪一个包含随机与固定offset；实际加法、clip/retry、使用何种rng |
| Map | m_randomWrapper:IBattleRandom、m_pathFinding、routes及endTiles | wrapper是否与imp/trivial共享对象/seed，具体初始化及调用链 |
| IBattleRandom / BattleRandomWrapper | RandomVector2(Vector2)与RandomVector2(min,max)、Range、NextDouble等接口；wrapper有Random字段 | uniform或其他分布；端点包含性；Random类型实际实现；每调用样本数、算法及hotfix行为 |
| BattleController | s_randomImp/s_randomTrivial；加载方法接收int randomSeed；暴露randomSeed | LevelData.randomSeed是否直接作为实际session seed；GameMode/调用者覆盖；两流初始化关系 |
| PathRequest / SPFA / IPathFinding | allowDiagonalMove为路径请求一部分，SPFA实现类存在 | 4/8邻居权重、corner规则、tie、检查点转向、缓存与路径重建细节 |
| MoveController | steering/obstacle/separation相关状态、常量3/.25/.05/.25及方法声明 | force组合顺序、dt、速度缩放/裁剪、isHanging、身体碰撞边缘与ticker频率 |
| GridPosition / Map变换 | asLocalPosition、FromVectorPosition、MapToWorld/WorldToMap等接口 | 半格偏移、world轴和高度、floor/round规则的真实方法体 |
| Route.CheckReached / GetContDirectionAfterEnd | 多重到达判断和终点后的方向接口存在 | 路线终点、可视蓝门、exit触发和边框越界的精确时机 |

具体方法行以 `{ }` 空壳结束，interface为abstract声明；RVA不是机器指令。
审查输入有签名dump及DummyDll/Cpp2IL_DummyDll目录，**没有恢复并验证这些native方法体**。
没有假装从声明得到了真实调用图：Enemy.Spawn→Route.GetSpawnPosition→RandomVector2只可作为
关联符号与待验证假说，不能标成已证实call edge。Hotfix delegate也意味着以后即使获得binary，
仍需核版本和实际hotfix路径。

已有 `ark_parser/enemy/05_movement_routes.md` 本来就将出生链路、独立随机偏移、力合成和游标算法
标为推断。旧V1 `core/battle.py::spawn_enemy` 有可见Python方法体：非零axis独立 draw、
`(2*u-1)*range`。新artifact使用AST只读保存该函数及SHA，并标
`historical_V1_model_reference_not_native_method_body`；不导入、不执行V1。
旧模型不得成为“native uniform已经证明”的证据。

## 原生坐标、portal和边框

当前锁源map为9×13，M6约定model top-down整数cell中心，native route row转换为 `8-native_row`。
原生 GridPosition字段与这项内容转换已可审查；真实Unity world transform仍未从方法体证明。

| 用途 | native route grid | M6 model grid | 该格源tile | 可视portal格（model） |
| --- | --- | --- | --- | --- |
| 大部分WALK出生 | (row4,col0) | (4,0) | tile_empty，passable ALL，buildable NONE | tile_start(4,1) |
| FLY出生 | (row6,col0) | (2,0) | tile_empty，passable FLY_ONLY，buildable NONE | tile_flystart(2,1) |
| 两个零range内部出生 | (row1,col2) | (7,2) | tile_start，passable ALL | 同格 |
| 全部实际spawn终点 | (row4,col12) | (4,12) | tile_empty，passable ALL，buildable NONE | tile_end(4,11) |

因此不能要求route start/end一定等于tile_start/tile_end；不能把tile_empty一律按墙、floor或全通行处理。
同名tile_empty有不同mask，尤其边框通道和其他FLY_ONLY空格必须依源mask区分。
原始 endpoints在数组索引内的外边框，可视portal位于其相邻内格。
本关没有blockEdges；其他关的边必须另按确证结构实现，不能因为本关为空而普遍忽略。

若采用当前整数中心模型，cell0的完整几何域是[-.5,.5)，而不是[0,1)。
uniform样本u_x=0会产生col=-.2，仍可落在同一个合法边框格0；把它clip到0会改变分布。
这个cell归属区间是**模型几何约定**，不是native FromVectorPosition方法体证明。
通用profile应按完整cell envelope及route endpoint许可验证位置，不能为0-10写敌人/关卡ID特判。

## 可审阅通用接口与明确模型选择

建议由Kernel负责sampler和消费日志，由pure calculation负责位置。
`spawn.position` 输入base_position（已声明坐标域）、原生offset/range、明确axis/value samples及
coordinate policy；输出position和独立audit。sample+compute+entity create须在一个outer atomic内，
否则失败会污染combat RNG次序或留下半生成对象。

`cartesian_uniform_halfextent_native_xy_to_topdown_v1` 为可替换**模型选择**：

- 将range解释为非负halfextent，x→col正号、native y→model row负号。range保持幅度，offset与
  sample产生的有符号delta整体按轴翻号，不能把range本身存成负幅度。
- 明确非零axes按x,y顺序各draw一次；零axis不draw。samples必须恰好覆盖active axes且在[0,1)。
- 建议独立stream `spawn`，当前可选Kernel算法 `python-mt19937/sha256-stream-seed-v1`，
  root seed默认取953816614并记录所有caller override。这个stream/算法/seed角色均未被native证明。
- 依上述选择，0-10预算为66个samples；native若zero axes仍抽样、用了其他stream或初始化阶段消耗，
  实际预算与序列会不同。不得把66升为native事实。
- 不引入隐式clip、随机重抽或“不合法则退回中心”fallback。应显式拒绝错误参数；将来需要retry/
  clip必须是另一个具名profile及消费策略。

公式：

```text
col = base.col + offset.x + (2*u_x-1)*range.x
row = base.row - offset.y - (2*u_y-1)*range.y
```

`eight_neighbor_no_corner_cut_v1` 也是模型：WALK根据allowDiagonalMove选择4/8邻居；
cardinal代价1、diagonal sqrt(2)，两侧cardinal及相关edge都可通行才允许corner crossing。
显式稳定tie顺序，不隐藏耗 RNG。FLY仍逐声明checkpoint直线行走，WAIT不能被几何shortcut跳过。
visit flags必须保留；这些代价、corner、tie与原生SPFA路径结果尚未对照。

`none_until_calibrated_v1` 为steering基线：保留steeringEnabled与五个mover参数，继续将native steering
效果标pending；不把8/10当成速度倍率，也不猜“direction*speed + clamp(steeringFactor*...)”。
后续movement.step接口可携带velocity/desired direction/dt/terrain/neighbor/foot/body与source参数，
但force计算应为另一个明示可替换profile；拿到方法体或客户端轨迹后再校准。

## 已执行离线预期与交付范围

新builder的四个固定samples用例实际通过，包括：

| base / offset / range / samples | 模型独立预期 |
| --- | --- |
| base(4,0)、offset0、range(.2,.2)、u(0,0) | (row4.2,col-.2) |
| base(4,0)、offset(.25,.1)、range(.2,.3)、u(.75,.25) | (row4.05,col.35) |
| 两axis range0、无samples | (4,0)，消耗0 |
| 只有y range.2、u_y=.5 | (4,0)，消耗1 |

负range、缺axis样本、样本1、零range却额外提供样本四种非法输入实际拒绝。
这些是纯离线数学/输入合同检查，**没有运行新V2 spatial primitive，也没有客户端轨迹对照**。

执行成功：

```powershell
..\.venv\Scripts\python.exe tools/build_campaign_spatial_profiles.py
..\.venv\Scripts\python.exe tools/build_campaign_spatial_profiles.py --check
```

artifact记录全部输入SHA、两份dump行号和字段、五个原始mover、19条route及portal记录、旧模型AST引用、
proposed接口、profile及预期。Root可审阅后另行实现/集成M7；不得修改M6结果或把本文件当成原生
算法恢复、正式0-10验收或36关完成证据。
