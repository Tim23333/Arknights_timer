# 标准主线回归关卡选择与证据

目录由 `tools/mainline_catalog.py` 离线生成，输出 `packages/campaign/mainline_catalog.json`。
工具只用标准库读取 JSON，不导入 V1 或 V2 实现。目录是任务矩阵，尚未成为 V2 内容包；
`dependency_status=not_imported` 和 `v2_status=not_validated` 不能解释成模拟器通过。

从 `Ark_emulator` 运行：

```powershell
..\.venv\Scripts\python.exe tools/mainline_catalog.py
..\.venv\Scripts\python.exe -m pytest tests_v2\test_mainline_catalog.py -q
```

有完整原始 LevelData JSON 时，可传 `--rawlevel-root <目录>`。只接受真实目录，
没有输入或 JSON 损坏会直接报错；不会造数据。`.bytes` 仅在它实际存储 JSON 时可读，
不把二进制改后缀视为 JSON。多个同名来源保留歧义，不自动决定版本覆盖。

## 来源与选关规则

必需来源位于 `../ark_parser/enemy/data/`：

- `stage_sim_bundle.json` 的 `stages` 提供原生 stage ID、显示 code、level ID 和 difficulty。
- `levels_index.json` 交叉核对 stage ID 与 level ID 的映射和游戏逻辑路径。
- `level_data_index.json` 核对抽取条目是否存在。
- `levels/<levelId>.json` 提供敌人引用、原始波次动作、路线和预放置数据概况。

目录记录全部输入文件 SHA256、每关解析 JSON SHA256，以及选中关卡现存原始 `.dat`
的路径和 SHA256。`../data/tables/stage_table*.bin` 仅作为现存二进制表清单记录 SHA，
本工具没有解析它们，不以该清单证明抽取表与 JSON 完全一致。
历史 `ark_emulator/data_level_assets_index.json` 只读取索引，不执行 V1 loader。

只选择完整匹配 `main_<chapter>-<sequence>` 且 `difficulty=1` 的条目，
按两个原生编号的整数排序，每章取最后两关，执行顺序为倒数第二关、最后一关。
显示 code 是展示信息，不能用它推导 level ID；例如 `main_06-15` 对应 `6-17`。

此规则排除 `tr_` 训练、`sub_` 支线、`st_` / `spst_` 纯剧情、活动 stage 和 `hard_` H 关。
`main_...#f#` 突袭与 `main_...#s` difficulty=8 变体不会成为标准条目。
含剧情控制动作的实际战斗关仍保留，不能仅因出现 STORY / DIALOG / PLAY_OPERA 就排除。
由于 bundle 的 `stageType` 缺失，目录逐关记录该歧义；本规则依赖原生 ID 分类，
不能称为已重建官方解锁图。

第 8 章的 R8、M8、JT8 路线交错，按 `main_08-NN` 的原生战斗序列处理，
不会按字母、显示数字或凭记忆排序。本地末两关为 `main_08-16` → JT8-2、
`main_08-17` → JT8-3。M8-1 等纯剧情 stage ID 仍由 `st_` 排除。

第 9 章起按同一 `(chapter, native_sequence)` 汇总 easy/main/tough 和后缀变体，
保留每个变体的原生 ID、level ID、显示 code、difficulty；仅无后缀 main 是标准回归目标。
本地第 9 章未出现 tough 条目，不能补造磨难版；10–14 章出现 easy/main/tough，
15–17 章出现 `#s` difficulty=8，保留数字而不猜该模式语义。

## 当前尾关矩阵

本地数据共 268 个标准战斗条目，0–17 章每章两关，共 36 个回归目标。
以下显示 code 经过本地 JSON 检查，独立写入测试作为预期，测试不会从选择器生成预期。

| 章 | 倒数第二关 | 最后一关 |
|---|---|---|
| 0 | 0-10 | 0-11 |
| 1 | 1-11 | 1-12 |
| 2 | 2-9 | 2-10 |
| 3 | 3-7 | 3-8 |
| 4 | 4-9 | 4-10 |
| 5 | 5-9 | 5-10 |
| 6 | 6-16 | 6-17 |
| 7 | 7-17 | 7-18 |
| 8 | JT8-2 | JT8-3 |
| 9 | 9-18 | 9-19 |
| 10 | 10-16 | 10-17 |
| 11 | 11-19 | 11-20 |
| 12 | 12-19 | 12-20 |
| 13 | 13-20 | 13-21 |
| 14 | 14-21 | 14-22 |
| 15 | 15-19 | 15-20 |
| 16 | 16-17 | 16-18 |
| 17 | 17-17 | 17-18 |

## 原始路线缺口与首两章依赖

36 个选中目标目前都标记 `source_available_with_geometry_gaps`。
解析 JSON 的部分路线 motionMode 为 E_NUM 或缺失，需要重新校准原始字段及默认值。
目录不会将这些路线归一化成 WALK 或 FLY，也不会造起点、终点或路径。
现存 checkpoints 仍原样保存于来源 JSON；不能以存在 checkpoints 证明路线已正确解析。

V1 索引中的 `unpack_work/level_assets_full/.../*.bytes` 应按
`Arknights_timer` 项目根目录解析，该目录当前不存在。现存
`../unpack_work/release_20260831/base_raw/level_main_*.dat` 是原始二进制线索，
并不是本工具可直接使用的原始 JSON。目录逐个记录可用路径，不宣称已完成解析。

| 关 | 声明 SPAWN 总数量 | 波次 | 主路线数 | E_NUM/缺失 motion 路线 | checkpoints | 控制动作条目 |
|---|---:|---:|---:|---:|---:|---|
| 0-10 | 35 | 1 | 19 | 18 | 66 | STORY 1、DISPLAY_ENEMY_INFO 1 |
| 0-11 | 37 | 3 | 22 | 22 | 59 | STORY 1、DISPLAY_ENEMY_INFO 1 |
| 1-11 | 45 | 1 | 21 | 21 | 55 | STORY 2、PREVIEW_CURSOR 1、ACTIVATE_PREDEFINED 1、DISPLAY_ENEMY_INFO 1 |
| 1-12 | 30 | 1 | 30 | 30 | 216 | STORY 1、DISPLAY_ENEMY_INFO 2 |

SPAWN 总数是原始动作 count 之和，未执行分支或随机条件，不能等同客户端总击杀数。
control_action_counts 是动作条目数，与重复 count 分开。完整 routeIndex 列表见目录。

四关 `enemyDbRefs` 均为 level=0：

- 0-10：enemy_1007_slime、enemy_1027_mob、enemy_1030_wteeth、enemy_1000_gopro、enemy_1005_yokai。
- 0-11：enemy_1007_slime、enemy_1007_slime_2、enemy_1000_gopro、enemy_1002_nsabr、enemy_1030_wteeth、enemy_1029_shdsbr。
- 1-11：enemy_1000_gopro、enemy_1000_gopro_2、enemy_1504_cqbw、enemy_1027_mob、enemy_1002_nsabr、enemy_1028_mocock、enemy_1014_rogue。
- 1-12：enemy_1504_cqbw、enemy_1014_rogue、enemy_1028_mocock_2、enemy_1030_wteeth、enemy_1000_gopro_2、enemy_1029_shdsbr。

1-11 的现有 predefines 仅保存 characterInsts=1、characterCards=12 等计数，
1-12 保存 tokenInsts=1；真实预放置实体内容同样需要原始数据恢复。
这些计数不能替代固定 12 人部署与控制动作处理。

下一步导入可直接读取 `stages` 中 `selected=true` 的记录，优先检查 geometry、
enemy_refs、predefines、control_action_counts，再生成 V2 内容与场景。
固定 0-1 的 smoke artifact 只能证明管线能运行，不能替代本矩阵的实际尾关证据。
