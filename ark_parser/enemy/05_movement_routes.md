# 05 敌人移动系统：移动模式 / 路线与检查点 / 寻路 / 阻挡 / 进蓝门

> 来源：`Ark_data/dump.cs`（Il2CppDumper 空壳 dump，方法体不可见），结论分级【确认】（字段/枚举/常量/签名直接可读）与【推断】（由命名、签名、常量组合推得）。行号均为 dump.cs 行号。
>
> 本文目标是支撑「行为级战斗模拟器」：给定 stage 数据（routes/waves/enemies）+ 敌人属性，逐 tick 复现敌人位置、罚站、阻挡、进门扣血。

---

## 0. 总体架构与逻辑帧率

移动系统的分层（括号内为关键类）：

```
数据层  LevelData.routes[] (RouteData) ── MapData.tiles[] (TileData.passableMask)
            │ 战斗初始化 Map.InitRouteAndPassableMap
运行时  Route (持有 IPathFinding) ──► 每个检查点一张全场 nextMap (Route.Node[,])
            │ Enemy.Spawn(route)
游标层  BasicCursor ──► DirectionCursor (逐检查点推进, 输出移动方向)
            │ Enemy.States.MoveState.OnTick 每 tick 调用
执行层  Enemy._MoveByRoute ─► _MoveByCursor ─► MoveController.CalculateMoveDelta
            │ (steering/避障/分离力修正)
表现层  Transform 位移 + 移动动画速度缩放 + 朝向切换
```

- 【确认】逻辑帧率：`GlobalConsts.TIME_ROUGH_LOGIC_RATE = 30`（1441464），`GlobalConsts.FIXED_DELTA_TIME_FP` / `HALF_FIXED_DELTA_TIME_FP`（1441459-60，static readonly，由 .cctor 赋值）。所有 `OnTick(FP deltaTime)` 按固定步长驱动。
- 【推断】固定步长 = 1/30 s，即 **1 秒 = 30 tick**；模拟器以 30 tick/s 步进即可与客户端逻辑一致（与现网内存实测 realPlayTime 步进一致）。

---

## 1. MotionMode 全表（地面 / 飞行）

`MotionMode`（1442309-1442316）与 `MotionMask`（1442319-1442327）【确认】：

| MotionMode | 值 | 说明 |
|---|---|---|
| `WALK` | 0 | 地面行走 |
| `FLY` | 1 | 飞行 |
| `E_NUM` | 2 | 模式总数（`SharedConsts.MOTION_MODE_NUM = 2`，1442673） |

| MotionMask | 值 | 说明 |
|---|---|---|
| `NONE` | 0 | 不可通行/不可选 |
| `WALK_ONLY` | 1 | 仅地面 |
| `FLY_ONLY` | 2 | 仅飞行 |
| `ALL` | 3 | 两者皆可 |

要点：

- **没有独立的"遁地/潜水"模式**。遁地、近地悬浮等表现为 buff/abnormal + 高度（`Enemy.HeightController`，443598；`levitateImmune`/`groundBoundImmune` 等免疫位，168967/168979），寻路与阻挡层面仍归 WALK/FLY 两类。【确认：枚举仅两项；推断：遁地由高度+buff 实现】
- **通行差异**：每格 `TileData.passableMask`（MotionMask，172788）决定该格允许哪种模式进入；格与格之间的边可被 `MapData.Edge.blockMask`（MotionMask，172805-172810）定向封锁。FLY 格通常 passableMask=ALL 或走空中专用路径。
- **出生点差异**：红门地砖 `tile_start`（地面）与 `tile_flystart`（飞行）是不同 tile key（1442689-90）。【确认】
- **阻挡差异**：敌人侧 `_CheckMotionModeBlockable(Character blocker)`（444719）；干员侧有序列化字段 `_motionMode@0x2C8`（自身模式）、`_blockMode@0x2CC`（可阻挡的模式）、`_ignoreBlockMode@0x2D0`、运行时 `m_changableBlockMode@0x524`（440401-440405, 440500）。【确认字段存在；推断：常规地面干员 blockMode=WALK 只挡地面敌人，飞行敌人只能被 blockMode=FLY/ALL 的单位（部分召唤物/装置）阻挡】
- **寻路差异**：`PathRequest.motionMode`（407326）是 SPFA 输入之一，两种模式各自缓存 nextMap（`SPFA.m_cacheMap[]` 数组按模式分桶，407368）。【确认】
- **可停格/所在格**：敌人每 5 tick 刷新所在格（`UPDATE_POS_TICK = 5`，443695；`m_updatePosTicker@0x3A0`），写入 `m_currentTile@0x350` / `m_oldTile@0x358`（`UpdateCurrentTile(bool force)`，444920）；Tile 侧维护 `m_enemies` 双缓冲列表（409283）与 `HasWalkEnemy()`。飞行敌人同样记账在 Tile 上（区分 motionMode，`OnEnemyMotionModeChanged` 409409）。【确认】

---

## 2. 路线数据结构（Route / RouteData / 检查点）

### 2.1 数据层（关卡 JSON ↔ C# 类）

`LevelData`（172591-172626）【确认】，关卡数据根：

| 字段 | offset | 内容 |
|---|---|---|
| `mapData` | 0x38 | 地图（`MapData`：tiles/blockedEdges） |
| `routes` | 0x60 | `RouteData[]` 主路线表（敌人按 `routeIndex` 引用） |
| `extraRoutes` | 0x68 | `RouteData[]` 扩展路线（`ActionData.useExtraRoute` 时引用） |
| `waves` | 0x80 | `WaveData[]` 波次 |
| `enemies` / `enemyDbRefs` | 0x70/0x78 | 本关敌人数据 |

`RouteData`（171955-171976）【确认】——一条路线：

| 字段 | offset | 含义 |
|---|---|---|
| `motionMode` | 0x10 | 该路线的移动模式（WALK/FLY） |
| `startPosition` | 0x14 | 出生格 `GridPosition{row,col}`（124581-82） |
| `endPosition` | 0x1C | 终点格（蓝门） |
| `spawnRandomRange` | 0x24 | 出生点随机抖动范围 |
| `spawnOffset` | 0x2C | 出生点固定偏移 |
| `checkpoints` | 0x38 | `CheckpointData[]` 检查点序列 |
| `allowDiagonalMove` | 0x40 | 允许斜向寻路 |
| `visitEveryTileCenter` | 0x41 | 强制经过每格中心（否则可切角） |
| `visitEveryNodeCenter` | 0x42 | 强制经过每个路径节点中心 |
| `visitEveryCheckPoint` | 0x43 | 强制逐点到达每个检查点 |

`RouteData.CheckpointData`（171934-171951）【确认】——单个检查点（**罚站点就在这里**）：

| 字段 | offset | 含义 |
|---|---|---|
| `type` | 0x10 | `CheckpointType`（见下表） |
| `time` | 0x14 | 时间参数（秒；语义随 type 变化） |
| `position` | 0x18 | 目标格 `GridPosition` |
| `reachOffset` | 0x20 | 到达点偏移 `Vector2`（不必精确到格中心） |
| `randomizeReachOffset` | 0x28 | 是否随机化 reachOffset |
| `reachDistance` | 0x2C | 到达判定距离（进入该半径即算到达） |

`CheckpointType`（172702-172718）【确认枚举值；语义列为推断】：

| 值 | 名称 | 运行态类（dump.cs 行号） | 语义 |
|---|---|---|---|
| 0 | `MOVE` | `BasicCursor.MoveCheckpoint`（406568） | 朝 position 移动，进入 reachDistance+reachOffset 范围即过点 |
| 1 | `WAIT_FOR_SECONDS` | `WaitForSecondsCheckpoint`（406696，含 `m_time`/`Skip()`） | **罚站**：原地停 time 秒 |
| 2 | `WAIT_FOR_PLAY_TIME` | `WaitForPlayTimeCheckpoint`（406735） | 等到全局 playTime ≥ time |
| 3 | `WAIT_CURRENT_FRAGMENT_TIME` | `WaitCurrentFragmentTimeCheckpoint`（406789） | 等到当前 fragment 已进行 time 秒 |
| 4 | `WAIT_CURRENT_WAVE_TIME` | `WaitCurrentWaveTimeCheckpoint`（406762） | 等到当前 wave 已进行 time 秒 |
| 5 | `DISAPPEAR` | `DisappearCheckpoint`（406634） | 隐身消失（传送门入口，`tile_telin`） |
| 6 | `APPEAR_AT_POS` | `AppearAtPosCheckpoint`（406658，`needUpdateLocationAfterReached=true`） | 在 position 重现（传送门出口，`tile_telout`）——DISAPPEAR+APPEAR_AT_POS 即成对隧道 |
| 7 | `ALERT` | `AlertCheckpoint`（406816，覆写 OnBegin） | 警觉点（哨兵类敌人驻停警戒） |
| 8 | `PATROL_MOVE` | `PatrolMoveCheckpoint`（406612，`LOOP_MAX = 50`，覆写 `NextCursor`） | 巡逻：到达后跳回此前某 MOVE 点循环，上限 50 圈 |
| 9 | `WAIT_BOSSRUSH_WAVE` | `WaitBossrushWaveCheckPoint`（406840） | BossRush 模式：等指定波次 |
| 10 | `MAP_OFFSET_MOVE` | `MapOffsetMoveCheckpoint`（406874，继承 PatrolMoveCheckpoint） | 按全图偏移移动（配合 `Route.AddMapOffsetMoveCkReachOffset`，407616） |
| 11 | `INVALID` | — | 非法 |

另有 `CheckpointTypeMask`（172722，Flags，不含后三种）供按类型过滤。

### 2.2 波次/出怪（罚站检查的时序载体）

- `LevelData.WaveData`（172312）：`preDelay`/`postDelay`/`maxTimeWaitingForNextWave`/`fragments[]`/`advancedWaveTag`。
- `LevelData.WaveData.FragmentData`（172274）：`preDelay` + `actions[]`。
- `LevelData.WaveData.FragmentData.ActionData`（172201-172249）【确认】：`actionType`（`SPAWN=0`、PREVIEW_CURSOR=1、STORY=2…共 14 种，172154-172173）、`key`（敌人 key）、`count`、`preDelay`、`interval`（同组多只间隔）、`routeIndex`、`useExtraRoute`、`blockFragment`（阻塞 fragment 推进）、`dontBlockWave`、`isUnharmfulAndAlwaysCountAsKilled`、`randomSpawnGroupKey` 等。
- 出怪链路【推断】：Scheduler（418644）按 wave→fragment→action 时序触发，`SPAWN` action → 取 `routes[routeIndex]`（或 extraRoutes）→ `Enemy.Spawn(data, handbook, snapshot, route, options)`（444683）→ 出生位置 = `Route.GetSpawnPosition()`（startPosition + spawnOffset ± spawnRandomRange 随机，407589-92）。
- `Enemy.Options`（441862）含 `unharmful`/`alwaysCountAsKilled`/`actionData` 回引等，进门结算时用到（见 §5）。

### 2.3 运行时层（Route / nextMap / 游标）

- `Route`（407531-407647）【确认】：包装 RouteData，持有 `m_pathFinder`（IPathFinding）、`m_targetNextMap`（朝向终点的全场导航表）、`m_checkpointsNextMap`（**每个 MOVE 类检查点各一张 nextMap**，`GetCheckpointNextMap(index)` 407622）。`Route.Node`（407482）：`pos`/`tile`/`nextTurn`(Vector2 转向)/`nextNode`/`distance`/`distToFinal`/`isInOpenList`。
- `BasicCursor`（406895）：游标基类，持有 `m_checkpoints[]`（由 `_CreateCheckpoint(data, nextMap)` 按 type 实例化上表运行态类，407021）、`m_cursor`（当前检查点索引）、`visitEveryTileCenter`/`visitEveryNodeCenter`/`ignoreAllButMoveCp`（只走 MOVE 点，用于预测等）。
- `DirectionCursor : BasicCursor`（407031-407177）【确认核心 API】：
  - `GetNextDirection()` / `_GetNextTarget()` / `GetNextTurn(moveDir)`：输出本 tick 移动方向；
  - `CheckReached()` / `PredictReached(stepDistance, out direction, out nextPos)`：到达判定与跨点预测（本 tick 步长越过目标点时直接落到下一目标方向，防止抖动）；
  - `OnTick(FP deltaTime, bool checkReached)`：推进 WAIT 类检查点计时；
  - `distToExit` / `distToExitPrecise` / `totalDist`：沿剩余路径到出口的距离（`Route.GetDistToFinal` 支撑）；
  - `TryGetNextAppearCheckpoint` / `TryGetDistanceToNextCheckpoint` / `PredictFuturePosition(predictDist, updateCursor, skipDisappearCheckpoint)`：供技能/AI 查询前方路线。
- `TracePositionCursor : DirectionCursor`（407200）：追击型敌人用，目标点可被 `MarkReached()`/`ResetReachedOffset(offset, randomize)` 动态重置，`alwaysUsing` 开关。敌人字段 `m_traceTargetCursor@0x380` + `m_traceTargetAbility@0x378`（443780-81），`usingTraceCursor`（444632）切换。
- 游标推进：`SkipNextCheckPoint(skipWait)`/`SkipCheckPoint()`/`_MoveNext()`（407015-407027），`Enemy._CursorNeedCheckReached(CursorType)`（444929）。

---

## 3. 移动帧级实现

调用链【确认签名，流程推断】：

```
Enemy.OnTick(FP fixedDeltaTime)                        445016
 └─ Enemy.States.MoveState.OnTick(FP)                  442148（MOVE=1，状态表见 §8）
     ├─ 被阻挡 → _MoveToBlockPosition(mapPos)          444968（见 §4）
     ├─ 恐惧中 → _MoveInFearArea → _MoveByCursor(fearCursor)     444890/444899
     ├─ 引诱中 → _MoveInAttractArea → _MoveByCursor(attractCursor) 444893
     └─ 常规  → _MoveByRoute → _MoveByCursor(m_cursor)  444887/444899
          ├─ cursor.GetNextDirection() / CheckReached() / PredictReached(step)
          └─ MoveController.CalculateMoveDelta(direction, deltaTime, out isHanging)  411408
               = direction·moveSpeed·dt + steering + 避障 + 分离力（见下）
```

- **速度**：敌人移速 = 属性 `AttributeType.MOVE_SPEED = 6`（1442062），数据源 `EnemyDatabase.AttributesData.moveSpeed [Meta(6)]`（168929）。`MoveController.get_moveSpeed()`（411381）透传 `IMovable.moveSpeed`（接口 388830-388858）。另有 `moveSpdTotalScale`（444614）与 `m_frictionFactor`（DEFAULT_FRICTION_FACTOR=1，443839；地砖 `additionalFriction` 409278）做缩放。
- **一格多少帧**：【推断】moveSpeed 单位为 **地图格/秒**（1 格 = 1 地图单位：分离半径 0.25、避障阈值 0.25 等常量均为格内尺度，411329-331）。故 `帧/格 = 30 / moveSpeed`（moveSpeed=0.5 → 60 tick/格；1.9 → ~15.8 tick/格）。每 tick 位移 = `moveSpeed / 30` 格，沿 cursor 方向匀速直线；到拐点由 `Route.Node.nextTurn` 换向。
- **格间是否严格直线**：`visitEveryTileCenter=0` 时 SPFA 会做路径拉直（`_PostprocessAndMakeNextMapSmoothly` + `_RaycastBresenhamLine` Bresenham 射线，407428-34），敌人可切角走斜线；`visitEveryTileCenter/visitEveryNodeCenter=1` 则逐格中心/节点中心走折线。【确认字段与函数存在，效果推断】
- **转向/动画**：
  - 朝向：`_useMoveDirAsFaceDir@0x2E0`（443714）以移动方向为脸朝向；`Enemy.BodyDirectionPolicy`：`DEFAULT_FOUR_WAYS=0`（四方向骨架翻转）/`LEFT_OR_RIGHT=1`（只分左右）（441878）；`_isFixedRotation@0x2D9` 锁定旋转。`SetBodyAndFaceDirection`（444851）、`FaceToCalculateDirection`（444971）、`OnFaceChanged`（444857）。
  - 移动动画速度随移速缩放：`_scaleMoveBySpeed@0x2E1` + `_scaleMoveAnimationRange@0x2E4` + `_keepMoveAnimScale@0x2FA`（443716-28），`MoveState.UpdateMoveAnimation()`（442151）、`PlayMoveAnim()`（444761）。
  - 无转身时间成本：状态机无 TURN 状态，换向即时（动画层面表现）。【推断】
- **MoveController**（411321，挂 Unity MonoBehaviour，每敌人一个，`Enemy.m_moveController@0x388`）：`CalculateMoveDelta` 汇总三种修正力，常量【确认】：
  - 转向力：`_steeringFactor`/`_maxSteeringForce`（`LevelData.Options.steeringEnabled` 172024 全局开关）；
  - 避障：每 3 tick 计算（`OBSTACLE_AVOID_TICK_PERIOD=3`），力系数 1.0，最小影响 0.5，`_halfBodyWidth` 半身宽扫边（`_CalculateObstacleAvoidForce` 411420）——绕开障碍桩类 tile；
  - 敌人间分离：每 3 tick（`SEPARATION_TICK_PERIOD=3`），力系数 3.0，半径 0.25 格（`SEPARATION_RADIUS=0.25`），最小位移 0.05——敌人互相挤开，这就是"怪堆叠时会散开"的来源；
  - 传送带地砖：`_ConveyorMove`/`_CanConveyorEnterGrid`（411432-47）在移动后追加传送带位移并夹取。
  - `isHanging` 输出：计算中检测悬空（`CalculateIsHanging` 411417），供掉落判定（`Enemy.IsHanging()` 444953，`MoveState.isHanging` 442131）。
- **所在格刷新**：每 5 tick（UPDATE_POS_TICK）`_UpdateCurrentTile` 把敌人挂到新格的 `Tile.m_enemies`，驱动地砖效果（如活性源石）。【确认】

---

## 4. 阻挡机制

### 4.1 触发（干员侧主动扫描）【确认签名，判定细节推断】

- 干员每 **3 tick** 扫一次（`FIND_BLOCKEE_TICK = 3`，440392；`m_findBlockeeTicker@0x3C0`；`ResetSearchBlockeeTicker()`/`SearchBlockeeImmediate()` 441279-82 供即时重扫）。
- 扫描：`_SearchBlockee(force)`（441459）→ 逐个 `_CheckBlockable(entity, source, out FP weight, out int volume)`（441462）→ `CheckBlockVolumeNotExceeded(enemy)`（441465）→ `_AddBlockee(enemy)`（441474）→ 敌人 `RegisterBlocker(blocker, offset)`（444725）。
- 阻挡范围：`Character.BlockRadiusManager.GetBlockCircle()` 返回 `TCircle`（440349-63），干员自身 `m_mainTriggerColliderRadius@0x540`（440505），敌人侧 `m_mainTriggerColliderRadius@0x428`（FP，443801）；`CheckInBlockRange(target, shrink)`（441456）做圆相交判定。【推断：敌人主触发圆与干员阻挡圆重叠即进入候选】
- 敌人侧过滤链：`CheckBlockable`（444713）= 范围检查 + `_CheckMotionModeBlockable`（模式匹配，FLY 不被地面干员挡）+ `_CheckSpecialBlockCondition`（444722；条件类型 `BUFF_KEY_PAIR_OR/BUFF_KEY_MATCH_AND/FILTER_TAGS`，443542-50，即"持某 buff 的敌人才能/不能被挡"类机制）。
- **体积制阻挡数**：敌人 `_blockVolume@0x328`（443753）+ 运行时 `m_blockVolumeAddition@0x4A0`（443810）；干员 `blockCnt`（属性 Meta(5)，168927）是**体积上限**而非个数。`Character.BlockedEnemyManager`（440291-346）维护 `m_totalVolume` + `m_blockedEnemies` 列表：`GetRemainingVolume(maxVolume)`/`CheckVolumeNotExceeded`/`TryPickOneToRemoveIfVolumeExceeded`（体积超限时挑一个踢出）。阻挡位满时新敌人直接走过。【确认结构；挑选规则推断（weight 出参参与排序，疑似按 distToExit/仇恨，越接近蓝门越优先，未能从空壳证实）】

### 4.2 被阻挡期间

- 敌人记录 `m_blocker@0x390`（ObjectPtr\<Character\>）与 `m_blockPosition@0x3F8`（443783/443795）。
- `_MoveToBlockPosition(mapPos)`（444968）：用 `m_blockTween@0x3E8`（ITweenHandler）把敌人从当前位置**平滑挤到阻挡位**，时长 `BLOCKING_TWEEN_DURATION = 0.2` 秒（443696）——即视觉上 0.2s 的"被拦停/挤位"过渡，之后钉在 m_blockPosition。阻挡位偏移由干员侧 `BlockeeOffsetPosSet(offset, enemy)`（441582，可被子类重写，如 447028）决定，多个被挡敌人按 offset 错开站位。【确认常量与函数；站位布局推断】
- 被阻期间敌人转入 ATTACK/COMBAT 状态攻击阻挡者（`Enemy.CombatWrapper`/`NextCombatOrExit`，443838/443409），移动挂起（cursor 不推进）。
- 位置记账仍在原格附近：`m_blockPosition` 只是表现层停靠点，逻辑位置（cursor）暂停。【推断】

### 4.3 解除与恢复

- 解除路径：`Character.RemoveBlockee`（441477）/ `ClearAllBlockees`（441468）/ `RevalidateBlockees`（441486，周期性复核）→ 敌人 `UnregisterBlocker`（444728）→ `ReleaseFromBlocker`（444902，复位物理 `_ResetPhysicsStatus` 444905、重开主触发器 `_ReactivateMainTriggerCollider` 444908）。
- 触发时机：阻挡者死亡/撤退、阻挡者 blockCnt 变化（`RecalculateBlockeesTotalVolume` 441480，体积超限踢出）、敌人被推拉离开、敌人进隧道/闪现。
- 恢复：敌人回到 MOVE 状态，cursor 从原进度继续走（`m_cachedCursorIndex@0x370`），无惩罚时间。【推断：无任何"再启动延迟"字段】

---

## 5. 进蓝门（ReachExit 全流程）

终点判定与结算链【确认各环节函数存在，顺序推断】：

1. cursor 推进到最后检查点，`Route.CheckReached(pos)`（407598-604）/游标 `CheckReached()` 成立；
2. `Enemy._CheckEnemyCanExit()`（444917）汇总：
   - 敌人自身 `_canNotExit@0x33A`（序列化默认，443761）与 `m_canNotExit@0x410`（运行时），`SetCanNotExit(bool)`（444770）可动态改；
   - 模式钩子 `GameMode.CheckEnemyCanExit(enemy)`（475171，虚函数，特殊模式可拦截）；
3. `Enemy.ReachExit()`（444974）→ `FinishWithReachExit(switchState)`（444977，覆写 Entity 虚函数 387749）→ 状态机切 `REACH_EXIT = 7`（441908）；
4. `Enemy.States.ReachExitState`（442335）：播进门动画（`_useSpecificReachExitAnim@0x2FC`，443732），tween 结束 → `Entity.Finish(FinishReason.REACH_EXIT = 1)`（386296）；
5. `GameMode.OnEnemyReachExit(enemy, cacheTile)`（基类虚函数 475147；各模式 override，如 Act7Fun 468091）；
6. 扣生命点：`BattleController.ModifyLifePoint(value, source, side, isReachExit: true)`（377251），value = **−enemy.lifePointReduce**。扣减走 Modifier 管线，带标记 `Modifier.SharedFlagIndex.LIFE_POINT_LOSS_BY_REACH_EXIT = 9`（位掩码 512，410716/410812），肉鸽等模式据此把扣血转为扣护盾等。【确认】
- **lifePointReduce 数据链**：`EnemyDatabase.EnemyData.lifePointReduce`（Undefinable，168881）→ 合并进 `LevelData.EnemyData.lifePointReduce@0x50`（172104）→ 运行时 `Enemy.<lifePointReduce>@0x504`（443826，属性 444157）。普通怪 1、boss 2~3（纯数据配置）。
- 统计：`BattleStats.EnemyStatKey.CounterType.REACH_EXIT = 2` / `DEADLIKE_REACH_EXIT = 4`（389572-74）；buff 事件 `Buff.Event.ON_OWNER_REACH_EXIT = 34`（379669）。
- **不扣血进门**：`Enemy.Options.unharmful`（441865，来自 `ActionData.isUnharmfulAndAlwaysCountAsKilled`，172215）的敌人（刁民类）进门不扣生命点且计为击杀。【推断：结算时按 options 分流】
- 蓝门/终点格：tile key `tile_end`（1442691）；`Map.m_endTiles@0x100`（405585）、`GetNearestEndPointTile()`（405712）。`Enemy.Options.dontCountAsFinished`（441867）控制是否计入"已消灭敌人"计数。

---

## 6. 寻路（SPFA）

- 接口 `IPathFinding`（407342）：`GenerateNextMap(PathRequest, Route.Node[,])`、`CheckReachable`、`TryCalculatePathFindingDistance`、`ClearCache(motionMode)`。
- 实现 `SPFA`（407363-441，Shortest Path Faster Algorithm，队列优化的 Bellman-Ford）：`s_openList: Queue<Route.Node>`（407366）。**从目标格反向洪泛**，为全场每格算出 `nextNode`（下一格）/`nextTurn`（朝向）/`distToFinal`，敌人移动时只需查当前格的 next 指针——典型的流场（flow field）寻路。【确认结构；反向洪泛由 GetDistToFinal/nextMap 命名推断】
- 输入 `PathRequest`（407322）：`targetPos` + `motionMode` + `allowDiagonalMove`（来自 RouteData）。
- **地面敌人 = 固定路线 + 动态绕障**：路线检查点序列是数据写死的，但检查点之间的格级路径由 SPFA 现算；地图变化（障碍桩放置/摧毁、地砖切换）时 `Map.AccumulateDirtyRoutes`/`UpdateRoutes`/`Route.ReconstructNextMap`（407580）重建 nextMap，敌人下一 tick 自动走新路。`CheckObstacleLikeOrInvalid`（407104）让敌人绕开"障碍物类"格；障碍桩格有 `moveCost`（409475）可付费穿过（打桩敌人）。【推断：重建后 cursor 位置不变、方向按新表取】
- **飞行敌人**：同样沿 Route 检查点飞（不是数学直线直奔蓝门），但 passableMask 基本全通，路径近乎检查点间直线。【推断】
- 通行判定合成【确认各因子存在】：
  - `Tile.passableMask`（409460 ← `TileData.passableMask` 172788）：格级模式过滤；
  - `Tile.m_gotoDirectionalPassableMask: int[]`（409286）：每格 4 个方向的走出掩码（`ALL_DIRECTION_PASSABLE_MASK = 15`，1442709），由 `MapData.blockEdges`（`Edge{pos, direction, blockMask}`，172805）初始化——**单向门/空气墙**就是这条；
  - `Tile.isObstacleLike`/`moveCost`（409476/409475）、`heightType`（LOWLAND/HIGHLAND，172759）；
  - 变体钩子 `CheckPassableGoto`（407407）：`LhshipSPFA`（407444，挽歌/船图）、`SandboxV3RanchSPFA`（407463，生息演算牧场）。
- 缓存：`m_cacheMap: Dictionary<PathRequest, Route.Node[,]>[]` 按模式分桶缓存（407368）；地图改动时 `Map.UpdatePassableMap`/`ClearCache` 失效。【确认】
- 距离查询：`Route.GetDistToFinal()`、`DirectionCursor.distToExitPrecise`、`Map.TryCalculatePathFindingDistance`（405677）——游戏内"距蓝门路径长度"全部来自 nextMap 上的 distToFinal 累加，模拟器可直接复用同算法预计算。

---

## 7. 特殊移动

### 7.1 恐惧（FearController，443440-443490）

- 结构：`m_fearBuffDict: ListDict<Buff, List<Tile>>`——每个恐惧 buff 挂一组"恐惧源格"；`MAX_FEAR_MOVE_DISTANCE = 5`（443443，格）。
- 流程：buff 添加 → `AddFearTargetTiles`（443471）→ `UpdateFearCursor`（443477）：`_InitializeFearRouteData`（443480）造一条临时 RouteData（远离恐惧源、≤5 格），`_TryGetFearRouteReachable` 校验可达，`_UpdateFearRoute` 落 `m_fearRoute` + `m_fearCursor`。
- 移动：`_MoveInFearArea`（444890）→ `_MoveByCursor(fearCursor)`，与常规移动同管线（CursorType.FEAR_CURSOR=1，441892）。恐惧结束回主 cursor。免疫位 `fearedImmune`（168971）。【确认结构；远离方向推断】

### 7.2 引诱（AttractController，443493-443538）

- 镜像结构：`m_attractBuffDict: ListDict<ObjectPtr<Buff>, Tile>`——每个引诱 buff 指定一个目标格；`AddTileAttract`/`UpdateAttractCursor`/`_TryGetAttractRouteReachable` 生成朝该格的临时路线（`m_attractRoute`/`m_attractCursor`）。
- 移动：`_MoveInAttractArea`（444893），CursorType.ATTRACT_CURSOR=2。免疫位 `attractImmune`（168975）。

### 7.3 闪现 / 传送（Blink 系列）

- 入口：`Blink(distance, hideTime, blinkUseAnimTime, withoutSwitchToBlinkState, skipDisappearCheckpoint)`（444773）——沿路线向前瞬移 distance 格；`BlinkWithDirection(pos, direction, ...)`（444776）、`Blink(grid, switchState)`（444779，直接到格，传送门类）；无状态切换版本 `BlinkWithoutSwitchToBlinkState`（444788）/`BlinkToGridPositionWithoutSwitchToBlinkState`（444791）。`MIN_BLINK_DISTANCE = 0.01`（443699）。
- 状态：`Enemy.States.BlinkState`（442995）：`BLINK_BEGIN_TIME = 0.25s` 隐匿淡出 + `BLINK_END_TIME = 0.25s` 淡入（442998-99，协程 `_PlayAnimation`），期间属性/abnormal 由状态修饰器接管。参数走状态机黑板：`blinkDistance/blinkHideTime/blinkRow/blinkCol/blinkPos/blinkPosDirectly`（441928-47）。
- 实现要点【推断】：距离闪现沿 cursor 路径前进 distance（等价 `PredictFuturePosition(blinkDistance, updateCursor: true, skipDisappearCheckpoint)`，407137），跨检查点推进 cursor；`skipDisappearCheckpoint` 控制是否跳过途中隧道点。
- 隧道（传送门）不靠 Blink：靠 `DISAPPEAR`+`APPEAR_AT_POS` 检查点对 + `tile_telin`/`tile_telout` 地砖（1442692-93），敌人到 DISAPPEAR 点隐身（DisappearState 442878），在 APPEAR_AT_POS 点重现（`needUpdateLocationAfterReached=true`，406663）。【确认结构】
- 免疫位 `teleportImmune`（168977）。

### 7.4 钩拉 / 击退 / 掉坑

- 拉力：`BeginPull(source, direction, force)`（444740，virtual）→ 持续 `StillPull`（444743）→ `TryEarlyStopPull`（444746）/ `EndPull`（444749）。多源记账 `m_pullSources`/`m_disabledPullSources`（ListSet\<ObjectPtr\<BObject\>\>，443802-03），`DisableCurrentStillPull`（444737，位移技能打断拉）、`_RemoveInvalidPullSources`（444764）。
- 击退：`KnockBack(direction, force, changeFaceByDirection)`（444734）。
- 位移期间走 `_MoveToFixedDirection(direction, FP deltaTime)`（444896）——脱离路线、按固定方向逐帧位移；同时进 `UNBALANCE = 9` 状态（`UnbalanceState` 442593，实现 `IPhysicObject`，失衡抛物）或拉力专用的挣扎（`SetStruggling` 444767，黑板 `isStruggling` 441926）。力度 vs 重量：`massLevel [Meta(23)]` / `baseForceLevel [Meta(24)]`（168943-44）。【确认字段/状态；公式不可见】
- 掉坑：`FallDown(tile, mode)`（444752）→ `FALLDOWN = 10`（`FallDownState` 442734）→ 判定 `CheckReadyToFallDown`（444758），坑格 `tile_hole`（1442694），直接斩杀。
- 贴地：`GroundBoundController`（`m_groundBoundController@0x3E0`，443792），`_groundBoundHeightZOffset` 默认 0.1（443738-39）；`groundBoundImmune`（168979）。

### 7.5 路线热切换

`ReassignRoute(route, cursorIndex)`（444803）、`TryReassignRouteAndCacheOrigin`（444671）+ `RestoreCachedRoute`（444668，用 `m_cachedRoute@0x368`/`m_cachedCursorIndex@0x370`）、`ReconstructRoute(endGridPos, checkpoints)`（444806）、`ReconstructRouteWithTargetGridMove`（444809）、`TransportInternal`（444812，传送带/运输）、`ChangePathMotionMode`（444836）+ `OnMotionModeChanged`（444755，模式切换时通知 Tile `OnEnemyMotionModeChanged`）。`Map` 侧支持运行时动态路线：`m_runtimeRoutes`/`m_runtimeTraceRoutes`/`m_runtimeExtraRoutes` + `GenerateRuntimeRoute`（405569-71, 405670-75）。【确认】

---

## 8. 敌人状态机总表（移动的状态语境）

`Enemy.States.State`（441897-441919）【确认】：

| 值 | 状态 | 与移动的关系 |
|---|---|---|
| 0 | DEFAULT | 初始 |
| 1 | MOVE | 常规移动（MoveState，442119） |
| 2 | ATTACK | 攻击阻挡者，移动挂起 |
| 3 | COMBAT | 缠斗（CombatState，442364） |
| 4 | STUN | 眩晕，移动挂起 |
| 5 | DEAD | 死亡 |
| 6 | BORN | 出生（`_delayToBorn@0x310`，443745） |
| 7 | REACH_EXIT | 进蓝门动画 |
| 8 | REBORN | 复活（RebornState，443063） |
| 9 | UNBALANCE | 失衡（击退/拉飞，物理位移） |
| 10 | FALLDOWN | 掉坑 |
| 11 | DISAPPEAR | 消失（隧道/复活前） |
| 12 | BLINK | 闪现 |
| 13 | FROZEN | 冻结（FreezeState 带属性修饰） |
| 14 | LEVITATE | 悬浮（LevitateState 442516） |
| 15 | DIALOG | 剧情锁定 |
| 16 | PALSY | 麻痹（PalsyState 442412，`palsy[stack]` buff） |
| -1 | TERMINAL | 终态 |

状态机实现 `Enemy.States.EnemyStateMachine : HierachyStateMachine`（442024），黑板含 `isHanging`/`isStruggling`/blink 参数（441922）。

---

## 9. 行为模拟器实现要点（落地清单）

1. **tick 循环**：30 tick/s；每 tick 对每个 MOVE 状态敌人：`pos += dir × moveSpeed / 30`；`dir` 由 cursor 给出。
2. **cursor 模拟**：按 checkpoints 顺序推进；MOVE 点 → 查该点 nextMap（开局用 SPFA 从检查点格反向洪泛一次全图，尊重 passableMask/blockEdges/allowDiagonalMove）取 next 方向，步长越点时用 PredictReached 语义截断到目标点并把余量折向下一方向；到点判定 = 距 `position+reachOffset` ≤ `reachDistance`（默认阈值方法体不可见，建议 0.1 格起步调参）。
3. **罚站**：WAIT_FOR_SECONDS 到时推进；WAIT_CURRENT_WAVE/FRAGMENT_TIME 依赖 Scheduler 时序；PATROL_MOVE 回跳（≤50 圈）。
4. **隧道**：DISAPPEAR → 下一 APPEAR_AT_POS 点瞬移（跳过中间路径计费）。
5. **阻挡**：每 3 tick 干员侧扫描；圆相交 + MotionMode 匹配 + SpecialBlockCondition；体积制（ΣblockVolume ≤ blockCnt）；被挡敌人 0.2s tween 到 blockPosition 后钉住，cursor 暂停；解除后原进度继续。
6. **进门**：终点 reached → canNotExit 检查 → lifePointReduce 扣点（unharmful 除外）。
7. **已知盲区**（方法体空壳，需实测或 Ghidra 二次确认）：
   - MOVE 检查点默认 reachDistance 与 PredictReached 的精确截断算法；
   - `_CheckBlockable` 的 weight 计算（阻挡优先级排序规则）；
   - MoveController 三种力的合成公式与 isHanging 判定；
   - FIXED_DELTA_TIME_FP 的精确初始化（1/30 为高置信推断）。
