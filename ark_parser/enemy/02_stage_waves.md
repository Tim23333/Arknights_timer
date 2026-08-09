# 02 关卡与波次数据：stage_table / level 资产 / 生成时序

> 目标：给定关卡，还原“什么时间在哪个路线生成多少只什么敌人”。
> 结论分级【确认】（dump.cs 字段/枚举/实测）与【推断】。

## 1. 现状：stage_table 只有关卡元数据，关卡内容在独立 level 资产

`data/tables/stage_table9f5b77.bin` 根表 31 个字段，field0 = 3467 个关卡字典
`stageId -> StageData`。StageData 表有 61 个字段（比 dump.cs:189408 的旧版多，
新版扩展了若干字段），本仓库已按字段名解析到 `data/stage_enemy_usage.json`：

| id | 字段（实测字符串验证） | 示例 main_01-01 |
|---|---|---|
| 5 | stageId | main_01-01 |
| 6 | levelId | Obt/Main/level_main_01-01 |
| 7 | zoneId | main_1 |
| 8 | code | 1-1 |
| 9 | name | 孤岛 |
| 13 | dangerLevel | LV.5 |
| 1 | difficulty | 1（NORMAL） |

**关卡真正的 waves/routes/enemies 不在 stage_table 内**，而在独立 TextAsset：
`level_*`（如 `level_main_01-01`、`level_act5d0_*`、`level_rogue*`）。
全量索引见 `data/levels_index.json`（6021 个，按前缀：main 1014、memory 302、
rogue5 185、sandbox2 184、act*side 大量、st 86、hard 53、sub 48…）。

### 1.1 关卡资产现状：Only Sign，已解密（2026-08-05 端到端验证）

关卡 TextAsset 格式实测为 **Only Sign**（`CrypticConverter_WithSign`，
dump.cs:238649）：`[128B 签名头][明文 FlatBuffers LevelData]`——**没有**
Cryptic A 的 AES 或 Cryptic B 的流式加密，剥掉 128 字节头即可解析。
这与 Arknights-RE（djpadbit）README 的表一致（Level data = Only Sign）。

解密体系背景（dump.cs:238498-238700，供对照）：
- `CrypticConverter_A`（238579）：`KEY_LENGTH=16, IV_LENGTH=16`、`m_token`
  派生 AES（表数据部分旧资产用，非 level）。
- `CrypticConverter_B`（238602）：`MOD=2147483647`、`SEED_HASH_STR="0.577215"`、
  `FastRandom` + `_Crypt(word, key)` 流式加密、seed 由 set_seed 注入。
- `CrypticConverter_WithSign`（238649）：`SIGN_HEADER_LENGTH=128`，
  `_BaseDecodeInternalToDecrypt` 剥头；`EnableCodeOpts()` 决定 SIGN/CRYPTO 组合。
- `FlatBufferSignedConverter`（238722）：FlatBuffers 表的 PreprocessText 入口。

**已落地的提取管线**（`extract_level_data.py`）：
1. AB 解包：`ArknightsStudioCLI.exe <game>/StreamingAssets/AB/Windows/anon \
   -t textAsset --filter-by-name "level_" -g none -o unpack_work/level_assets_all`
   （anon 的 AB 是 UnityFS + LZHAM，需 AssetStudio-Arknights 分支；本机已编译
   `AssetStudio-ArknightsStudio/AssetStudioCLI/bin/Release/net8.0/win-x64/`）。
2. 剥头：每文件裁掉前 128 字节（`signHeader=128` 记录在 `_meta`）。
3. 解析：`extract_level_data.py` 用共享 FB 读取器 + 有界 schema 解析
   （节点预算防递归爆炸），输出 `data/levels/<levelId>.json`（2854 个，
   主线 00-17 全章节、memory 全、rogue/sandbox/camp/hard 等）+
   `data/level_data_index.json`（汇总索引）。
4. 正确性：`options/runes/enemyDbRefs/randomSeed/waves` 与 CN 官方数据
   （ArknightsAssets/ArknightsGamedata `cn/gamedata/levels/obt/main/*.json`）
   逐字段比对一致（level_main_01-01：characterLimit=8、maxLifePoint=10、
   maxCost=99、randomSeed=978975386 等）。
5. 数据源位置：关卡 TextAsset 分布在 `anon/*.bin`（118 个）中；
   `PersistentData/Bundles/anon`（13 个热更 bin）已检查：593 个 level
   资产与基线完全重合，无新增关卡。

## 2. LevelData 结构（解密后为根表，dump.cs:172591）

| id | 字段 | 说明 |
|---|---|---|
| 0 | options | LevelData.Options：characterLimit/maxLifePoint/initialCost/maxCost/costIncreaseTime/moveMultiplier/maxPlayTime/configBlackBoard/enemyTauntLevelPow…（dump.cs:172015） |
| 1 | levelId | 关卡 id |
| 2 | mapId | 地图 id |
| 5 | mapData | 地图（tiles/blockedEdges，见 05 文档） |
| 7 | runes | LegacyInLevelRuneData[] 词条（见 §5） |
| 9 | globalBuffs | 全局 buff（prefabKey+blackboard） |
| 10 | routes | RouteData[] 主线路线（见 05 文档） |
| 11 | extraRoutes | RouteData[] 扩展路线 |
| 12 | enemies | 关卡内联敌人数据 |
| 13 | enemyDbRefs | **EnemyDataDbReference[]：{useDb, id, level, overwrittenData}**（dump.cs:172139）→ 决定实际用 enemy_database 的哪个 id+等级 |
| 14 | waves | WaveData[] 波次（见 §3） |
| 15 | branches | 分支波次（BranchData{phases[]}，条件刷怪） |
| 16-17 | predefines/hardPredefines | 预置干员/卡牌 |
| 19 | randomSeed | 关卡随机种子 |

## 3. 波次生成模型（WaveData / FragmentData / ActionData）

`WaveData`（dump.cs:172312）：

| id | 字段 | 含义 |
|---|---|---|
| 0 | preDelay | 波次开始前等待（秒） |
| 1 | postDelay | 波次结束后等待（秒） |
| 2 | maxTimeWaitingForNextWave | 下一波最大等待 |
| 3 | fragments | FragmentData[] |
| 4 | advancedWaveTag | 高级波标记 |

`FragmentData`（dump.cs:172274）：`preDelay` + `actions[]`。

`ActionData`（dump.cs:172201）关键字段：

| id | 字段 | 含义 |
|---|---|---|
| 0 | actionType | 枚举：SPAWN=0/PREVIEW_CURSOR=1/STORY=2/TUTORIAL=3/PLAY_BGM=4/DISPLAY_ENEMY_INFO=5/ACTIVATE_PREDEFINED=6/PLAY_OPERA=7/TRIGGER_PREDEFINED=8/BATTLE_EVENTS=9/WITHDRAW_PREDEFINED=10/DIALOG=11/SHOW_ALL_HIDDEN_CARDS=12/EMPTY=13 |
| 2 | key | SPAWN 时为敌人 key（或 hiddenGroup） |
| 3 | count | 生成数量 |
| 4 | preDelay | 本次 action 前摇 |
| 5 | interval | 同 action 内相邻生成间隔 |
| 6-7 | useExtraRoute / routeIndex | 走扩展路线/路线索引 |
| 8-10 | blockFragment/autoPreviewRoute/autoDisplayEnemyInfo | 调度/预览标记 |
| 12 | hiddenGroup | 隐藏组 |
| 13-14 | randomSpawnGroupKey / randomSpawnGroupPackKey | 随机生成组 |
| 15-16 | randomType / refreshType | 随机策略（ALWAYS/PER_DAY/NEVER/PER_SETTLE_DAY/PER_SEASON） |
| 17 | weight | 权重 |
| 22 | extraMeta | 额外数据（可能含敌人等级/掉落） |
| 23 | actionId | 动作 id |

**生成时间线（推断，基于字段与 05 文档的 30 tick/s）**：
波次 preDelay 到点 → 依次执行 fragment；每个 SPAWN action 在自身 preDelay 后开始，
以 interval 间隔生成 count 只，routeIndex 决定出生点/路线。敌人等级来自
`enemyDbRefs`（level）或 SPAWN extraMeta。

## 4. 敌人等级与数据合并

- 关卡 `enemyDbRefs[]`：`{useDb, id, level, overwrittenData}`；useDb=true 时
  查 `enemy_database.json` 的 (id, level)（EnemyDatabase 内多 level 覆盖，
  `OverwriteEnemyData` 合并基础与等级差异，dump.cs:169037）。
- `enemies[]`：关卡内联敌人（老关卡或活动特例），结构与 EnemyData 相同。
- 词条 Rune 在战前改写技能/属性（见 03 文档 §1.4 的 rune key 表）。

## 5. Rune 词条（dump.cs:182975 / 183034）

`LegacyInLevelRuneData{key, professionMask, buildableMask, blackboard}`；
`RuneData{key, selector, blackboard}`，selector 含 charIdFilter/enemyIdFilter/
enemyLevelTypeFilter/skillIdFilter/tileKeyFilter 等过滤（dump.cs:183000）。
词条黑板的 key 前缀：`enemy_skill_cd_mul`、`enemy_skill_init_cd_add/mul`、
`enemy_skill_sp_cost_add`、`enemy_skill_sp_max_init_add`、`enemy_skill_radius_mul`、
`enemy_skill_blackb_add/mul/assign`、`enemy_skill_attributedata_assign`（见 03 文档）。

## 6. 模拟器接入点

1. `data/stage_sim_bundle.json` 一键接入：`levels[levelId]` 含 options、runes、
   enemyDbRefs（id+level）、enemies（关卡内覆盖）、routes（checkpoints）、
   waveTimeline（SPAWN 事件绝对时间表）与 randomSeed；`enemyRoster` 提供
   敌人 id -> 基础属性/技能；`stages[stageId]` 映射 stage -> levelId。
2. 需要完整原始结构时直接读 `data/levels/<levelId>.json`
   （2854 个：主线 00-17 全章节、memory 全、rogue/sandbox/camp/hard 等）。
3. 逐关覆盖统计见 `data/sim_coverage.json`（3467 个 stage 中 2140 个已有
   已解析关卡；缺失的 act*/新活动关卡在当前客户端中不存在（热更 bin 已检查，
   与基线重合），如需补充需从对应活动数据包/服务端获取后再跑
   `extract_level_data.py`）。
4. `options` 提供费用/生命/移速倍率等全局参数；路由/时间轴细节与假设见
   10_level_schema_calibration.md。

## 7. 不确定点

- ~~level 资产解密未完成~~ —— 已解决（§1.1）：Only Sign，剥 128B 头 + FB 解析；
  `data/levels/*.json` + `data/level_data_index.json` 已产出。
- ~~SPAWN action 的 extraMeta 是否携带敌人等级/词条~~ —— 已答复：14 个参考关卡
  660+ action 的 extraMeta 全为 null，敌人等级来自 enemyDbRefs（10 文档 §3/§7）。
- ~~ActionData 布尔位域与 routeFlags~~ —— 已解码：二进制顺序 = C# 去掉
  useExtraRoute；bool 为 1 字节内联（10 文档 §3/§4）。
- SPAWN action 的 `extraMeta` 是否携带敌人等级/词条需解密后验证。
- StageData 61 字段中第 51-60 字段名未全部映射（新版扩展字段）。
