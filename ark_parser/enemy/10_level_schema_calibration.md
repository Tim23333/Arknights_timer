# 10 LevelData 嵌套 schema 校准（2026-08-05）

> 结论分级：【确认】= 与 CN 官方参考 JSON（ArknightsAssets/ArknightsGamedata
> cn/gamedata/levels/obt/main/level_main_01-01.json）逐字段比对一致；
> 【推断】= 由 dump.cs 字段顺序 + 二进制形态推出，需更多关卡样本复核。

## 1. 根表 LevelData（【确认】）

FB 字段索引 = C# 声明顺序（dump.cs:172591）：

| idx | 字段 | 解析状态 |
|---|---|---|
| 0 | options | 【确认】schema 解析 |
| 1 | levelId | 大部分文件**缺省**（游戏用资产名补），少数沙盒关写 `[dev]test/level_training` |
| 2 | mapId | 通常缺省 |
| 3 | bgmEvent | 【确认】字符串 |
| 4 | environmentSe | 字符串 |
| 5 | mapData | 【确认】紧凑解析（tiles/blockEdges/tags/layerRects） |
| 6 | tilesDisallowToLocate | 网格坐标列表 |
| 7 | runes | 【确认】difficultyMask/key/professionMask/buildableMask/blackboard |
| 8 | optionalRunes | 未展开（一般缺省） |
| 9 | globalBuffs | prefabKey + blackboard |
| 10 | routes | 【确认】见 §4 |
| 11 | extraRoutes | 同 routes |
| 12 | enemies | 【确认】复用 parse_enemy_data（关卡内覆盖敌人） |
| 13 | enemyDbRefs | 【确认】{useDb, id, level, overwrittenData} |
| 14 | waves | 【确认】见 §3 |
| 15 | branches | 未展开（一般缺省） |
| 16/17 | predefines/hardPredefines | 计数摘要（characterInsts/tokenInsts/characterCards/tokenCards） |
| 18 | excludeCharIdList | 字符串列表 |
| 19 | randomSeed | 【确认】整数（level_main_01-01 = 978975386 与官方一致） |
| 20/21 | operaConfig/cameraPlugin | 字符串 |

## 2. Options / Runes / EnemyDbRefs（【确认】）

Options 字段序：characterLimit, maxLifePoint, initialCost, maxCost,
costIncreaseTime(f), moveMultiplier(f), steeringEnabled(b), isTrainingLevel(b),
isHardTrainingLevel(b), isPredefinedCardsSelectable(b), displayRestTime(b),
maxPlayTime(f), functionDisableMask, configBlackBoard(blackboard),
enemyTauntLevelPow, deployCostPostDelta, deployCostPostDeltaMinCost。
level_main_01-01 实测：8/10/10/99/1.0/0.5/true/…/-1.0 与官方一致。

Rune 字段序：difficultyMask(Difficulty 枚举：2=FOUR_STAR), key,
professionMask(位掩码), buildableMask(BuildableType 掩码：3=ALL),
blackboard（value 已按 i2f 转 float + value_raw）。

EnemyDbRefs 元素：useDb(bool), id(string), level(int，缺省按 0),
overwrittenData(EnemyData 表，可空)。level_main_01-01 的 6 条引用
（enemy_1000_gopro / _2 / enemy_1027_mob / 1028_mocock / 1007_slime_2 /
1030_wteeth，level=0）与官方一致。

## 3. Waves -> Fragments -> Actions（【确认】核心 + 【推断】位域）

WaveData：preDelay(0), postDelay(1), maxTimeWaitingForNextWave(2, 常见 -1.0),
fragments(3), advancedWaveTag(4)。
FragmentData：preDelay(0), actions(1)。

**ActionData 二进制布局（实测 level_main_01-01 19 个 action 与官方逐条对照）：**

| 二进制字段 | 内容 | 证据 |
|---|---|---|
| 0 | actionType（枚举，SPAWN=0 时**字段整体省略**） | DISPLAY_ENEMY_INFO=5 / STORY=2 出现时 field0 存在 |
| 1 | managedByScheduler（**1 字节 bool**，恒 true） | 所有 action 首字节 0x01；i32 读出 0x80000001 等是**相邻字段泄漏**（见 §6） |
| 2 | key（string 偏移） | 与官方 key 一致 |
| 3 | count（int） | 1/2/3/4 与官方一致 |
| 4 | preDelay（float，i2f） | 与官方一致 |
| 5 | interval（float，i2f） | 与官方一致 |
| 6 | routeIndex（int，缺省 0 时省略） | field6=1..18 与官方 routeIndex 逐一吻合 |
| 8 | autoPreviewRoute（**1 字节 bool**，true 才出现） | 19 个 action 中 field8 存在 ⟺ 官方 autoPreviewRoute=true（100% 吻合） |

ActionType 枚举：SPAWN=0, PREVIEW_CURSOR=1, STORY=2, TUTORIAL=3, PLAY_BGM=4,
DISPLAY_ENEMY_INFO=5, ACTIVATE_PREDEFINED=6, PLAY_OPERA=7,
TRIGGER_PREDEFINED=8, BATTLE_EVENTS=9, WITHDRAW_PREDEFINED=10, DIALOG=11,
SHOW_ALL_HIDDEN_CARDS=12, EMPTY=13, E_NUM=14。

**尚未解码（【推断】/遗留）：** blockFragment、autoDisplayEnemyInfo、
isUnharmfulAndAlwaysCountAsKilled、useExtraRoute、dontBlockWave、
forceBlockWaveInBranch、isValid、notCountInTotal 等 bool 的二进制字段位，
以及 hiddenGroup/randomSpawnGroup*/weight/randomType/refreshType 的位置——
需要“这些字段非默认值”的关卡样本（当前样本全是默认值所以字段被省略）。

## 4. Routes -> Checkpoints（【确认】核心 + 【推断】位域）

RouteData：motionMode(0, MotionMode: 0=WALK/1=FLY/2=E_NUM), startPosition(1),
endPosition(2), spawnRandomRange(3, Vector2), spawnOffset(4, Vector2),
checkpoints(5), allowDiagonalMove(6, 1 字节 bool，byte0=0x01=true),
visitEveryTileCenter(7), visitEveryNodeCenter(8), visitEveryCheckPoint(9)。
GridPosition = {row(0), col(1)}；Vector2 = {x(0), y(1)} float。

CheckpointData：type(0, CheckpointType：0=MOVE,1=WAIT_FOR_SECONDS,
2=WAIT_FOR_PLAY_TIME,3=WAIT_CURRENT_FRAGMENT_TIME,4=WAIT_CURRENT_WAVE_TIME,
5=DISAPPEAR,6=APPEAR_AT_POS,7=ALERT,8=PATROL_MOVE,9=WAIT_BOSSRUSH_WAVE,
10=MAP_OFFSET_MOVE,11=INVALID), time(1,f), position(2,GridPosition),
reachOffset(3,Vector2), randomizeReachOffset(4,bool), reachDistance(5,f)。

## 5. MapData / TileData

MapData：map(0, short[,]——当前只保留 mapCellCount，尺寸待解),
tiles(1), blockEdges(2), tags(3), effects(4), layerRects(5)。
TileData：tileKey(0), heightType(1, 0=LOWLAND/1=HIGHLAND),
buildableType(2), passableMask(3, MotionMask: 1=WALK_ONLY/2=FLY_ONLY/3=ALL),
playerSideMask(4), advancedBuildableMask(5), blackboard(6), effects(7)。

## 6. 重要坑：布尔字段是 1 字节内联，i32 读取会泄漏相邻字节

例：level_main_01-01 action0，vtable 给出 f1 @ 0x55B 处字节 `01 00 00 80`：
byte0=0x01 即 managedByScheduler=true；随后 3 字节 `00 00 80` 是 interval
(1.0=0x3F800000) 的尾字节。按 i32 读会得到 0x80000001（无意义大数）。
因此位域“值”不能直接当整数用；正确做法是**按字段位置读单字节**。
同理 routeFlags(4097=0x1001) 的 byte0=0x01=allowDiagonalMove=true，
高字节是相邻数据。extract_level_data.py 目前保留原始 i32（flags1/flags2/
routeFlags）供后续按字节解码。

## 7. 待办（已大幅收窄，2026-08-05 用 14 个 CN 官方参考关卡校准）

已完成：
- ActionData 全部字段位确认（§3 已更新）：二进制顺序 = C# 顺序去掉
  useExtraRoute（该字段在二进制 schema 中不存在）；bool 为 1 字节内联、
  为 true 才出现：blockFragment=7、autoPreviewRoute=8、autoDisplayEnemyInfo=9、
  isUnharmfulAndAlwaysCountAsKilled=10、hiddenGroup=11、randomSpawnGroupKey=12、
  randomSpawnGroupPackKey=13、randomType=14、refreshType=15、weight=16、
  dontBlockWave=17、forceBlockWaveInBranch=18、notCountInTotal=20。
  7038 项比对仅 3 处“空字符串 vs 缺省”表示差异。
- RouteData 标志：allowDiagonalMove=6、visitEveryTileCenter=7、
  visitEveryNodeCenter=8、visitEveryCheckPoint=9（1 字节 bool）。
- MapData.map 布局：{rows, cols, cells[u16 行主序]}（level_main_01-01=7x9=63）。
- extraMeta 结论：14 个参考关卡 660+ action 全为 null —— SPAWN 的敌人等级/词条
  来自 enemyDbRefs/enemies，extraMeta 在本版本数据中未被使用（遗留 union 在 f21）。
- 热更补充：PersistentData/Bundles 的 593 个 level 资产与基线 anon 完全重合
  （0 个新关卡），当前客户端未含更多关卡。

剩余待办：
- ~~branches/optionalRunes~~ 已补齐（2026-08-05）：branches=dict key ->
  {phases:[{preDelay, actions[]}]}，optionalRunes=dict key -> rune[]；
  已用 level_rogue2_b-7/sandbox1_20/main_17-05 与官方参考校验一致。
- 若需精确 schema 生成：DNFBDmp（Arknights-RE）或 OpenArknightsFBS。
