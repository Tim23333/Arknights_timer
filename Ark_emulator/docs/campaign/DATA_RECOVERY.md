# 主线原始二进制数据恢复

`tools/extract_campaign_levels.py` 是独立离线提取器，只读取现存 LevelData `.dat`，
通过 `ark_parser/enemy` 的 FB 研究辅助代码解码；不导入 V1/V2 战斗、地图或波次执行器。
原始输入、共享 parser 和先前目录均保持原样。

```powershell
..\.venv\Scripts\python.exe tools/extract_campaign_levels.py
..\.venv\Scripts\python.exe tools/fetch_campaign_reference.py
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_reference.py tests_v2/test_campaign_levels.py tests_v2/test_mainline_catalog.py -q
```

默认读取 `../unpack_work/release_20260831/base_raw/`，使用现有目录 selected 的 36 个关卡。
原生形状 JSON 输出到 `packages/campaign/recovered_levels/`，批次报告输出到
`validation/campaign/data_recovery.json`。可通过 `--level`、`--source-dir`、
`--output-dir`、`--reference-dir`、`--report` 修改范围和目的地。

当前实际结果：36/36 解码，0 个硬失败，36/36 核心字段精确参考验证。
全部输出 `status=partial`、`v2_status=not_validated`，因为完整根 schema 与 V2 运行尚未验收。
36 关均为 `core_status=reference_verified`、`core_exact_equal=true`、differences=[]、issues=[]；
这只证明六个已声明核心域与固定参考吻合，不能作为客户端战斗验证。

## 已证明的核心修复

最初四个对照关卡为 0-10、0-11、1-11、1-12，随后扩展到全部 36 个目标。公开参考下载自
`ArknightsAssets/ArknightsGamedata`，固定 commit
`56aee3d6c5a29c3a0d192456d70d14252cbb0804`（2026-09-29）。
本工具不联网，逐个记录本地参考 JSON SHA256，参考文件不会填充提取结果。
`reference_commit` 是参考下载方提供的出处标签；文件内容身份由 SHA256 独立确定。

本地 TextAsset `.dat` 包含 `[u32 nameLength][ASCII asset name][4B alignment]`，
随后是 132 字节签名/版本包络，再进入 FlatBuffers。四关 payloadOffset 均为 152。
只尝试剥离固定 128 字节会错误解析；工具先校验资产名与文件名，严格计算 payload 位置。

RouteData 的 WALK=0 与 checkpoint MOVE=0 会由 FlatBuffers 省略字段；
坐标表里单个 row/col=0 字段也会省略，但坐标表本身必须真实存在。
工具将这些已校准的字段默认值还原，坐标表缺失时直接失败，不能补 `(0,0)`。
route0 的 E_NUM 是真实占位，保留其索引和内容，仅对实际 SPAWN 引用的路线检查可用性。

Map 的格子向量是 `u16`，长度边界应使用 `count * 2`；旧辅助 `is_vector`
按 `count * 4` 判断会在部分位于文件末段的格子向量上误判。该修复解决 6-17 的恢复失败。
原生 map 行顺序原样输出；不在离线恢复阶段翻转游戏坐标。

布尔值严格读取单字节并验证值为 0/1，避免相邻浮点/整数污染。
浮点数按 IEEE754 解码为十进制数，拒绝 NaN/Infinity。

PredefinedCharacter 的位置和方向在继承字段之前；其余依次为
hidden、alias、uniEquipIds、showSpIllust、masterInfos、inst、skillIndex、
mainSkillLvl、skinId、tmplId、overrideSkillBlackboard、overrideTalents。
普通卡没有位置方向前缀。TokenCard 的派生 initialCnt 在 field0，继承字段整体后移一位。
这一点最初由 dump.cs 继承关系、现存二进制 field 位和元数据表一致性支持，
随后由固定参考中的非空 tokenCards 完整内容精确对照校准。

本地 legacy TileData 的 field5=blackboard、field6=effects，当前 dump.cs 在它们之前
插入 advancedBuildableMask；不能将新版声明直接套入旧资产。工具独立解析 legacy schema，
直接读取 DataPair 的 key/value/valueStr，而不是把 blackboard 偏移误读为数值 mask。
预放置 overrideSkillBlackboard 使用同一严格 DataPair 解码器，map.tags 按字符串向量解码。
这些校准将初次完整参考对照的 17/36 提升到实际 36/36，未使用参考 JSON 填充本地数据。

首四关恢复后的核心：

- 0-10：9×13 真实格子；route1 为 WALK，起点 `(4,0)`、终点 `(4,12)`，
  checkpoints 为 `(4,8)`、`(3,8)`、`(3,10)`、`(4,10)`。
- 0-11：真实 WALK/FLY 路线与 3 波原始波次保持路线索引；合法占位路由保留。
- 1-11：恢复预放置 `char_211_adnach`，位置 `(3,6)`、RIGHT、hidden=true、level20，
  以及完整 12 张原生预定义卡。
- 1-12：恢复 `trap_002_emp`，位置 `(2,5)`、UP、level10，原生预放置 token 保留。

`tests_v2/test_campaign_levels.py` 的 15 个测试包含独立固定坐标、checkpoint 序列、
真实预放置与卡数，以及全部 36 关核心内容的精确 canonical equality。
canonical 只统一空数组/空字典/null 的导出形式，省略研究计数与缺省的额外字段；
不删除非默认坐标、枚举或列表元素。测试还验证资产名错误、截断、坐标表缺失会失败，
以及没有参考输入仍能直接从二进制恢复相同坐标。

## 报告接口与证据边界

批次报告顶层：

```json
{
  "schema": "ark_sim.campaign_data_recovery.v1",
  "offline_only": true,
  "reference_repository": "ArknightsAssets/ArknightsGamedata",
  "reference_commit": "56aee3d6c5a29c3a0d192456d70d14252cbb0804",
  "core_fields": ["mapData", "routes", "extraRoutes", "waves", "predefines", "hardPredefines"],
  "counts": {"attempted": 36, "decoded": 36, "failed": 0, "core_reference_verified": 36},
  "levels": []
}
```

`levels` 每条按 `level_id` 与目录连接。成功条目记录 source_path/source_sha256、
payload_offset、helper_sha256、fb_helper_sha256、extractor_sha256、output_path/output_sha256，
以及 core_status、issues、unverified_root_fields、spawn_route_indices、v2_status。
有参考时附 reference_path/reference_sha256、differences 和 core_exact_equal。
路径相对 `Ark_emulator`，可以直接与其目录拼接读取。

core_status 的含义：

| 值 | 可证明的范围 |
|---|---|
| reference_verified | 六个核心域与该本地参考逐字段相符，无已报告核心未解析字段 |
| decoded_unverified | 二进制解码通过，尚无参考对照 |
| decoded_partial | 二进制解码有结果，但存在未校准/未展开字段 |
| reference_mismatch_or_partial | 有参考，但存在差异或已知部分字段缺口 |

硬失败条目 `status=failed`，保留 error、source_path/source_sha256；不生成虚构关卡。
后续 runner 可用该报告覆盖旧 catalog 的来源准备度，但必须保留旧来源 SHA 与失败身份，
不能把旧错误提取文件的 status 改写成已验证，也不能用来源恢复证明战斗模型通过。

若遇到尚未校准的非空 overrideTalents/装备或不同版本 schema，会记录 issues 或硬失败。
本次 36 个核心对照目标没有剩余差异，但全局 rune、enemyDbRefs 数值覆盖、options、branches 等根字段
仍来自旧研究 parser，列于 unverified_root_fields，不在本次核心证明范围。
原始引用路径与 SHA 可以供下阶段继续校准。首四关的原生预定义阵容是游戏数据，
固定 12 人实验阵容如何处理这些预定义内容由场景策略决定，不能在数据恢复阶段替换。

## 固定参考下载与缓存门

`tools/fetch_campaign_reference.py` 使用 curl.exe，TLS 证书验证保持开启，下载与重定向
只允许 HTTPS。它根据已选中的 36 个 level ID 构造固定 commit 的 cn/gamedata/levels/obt/main URL；
拒绝非法 ID、路径穿越、后缀、查询参数和任何 manifest URL/commit 偏移。
原生文件及 `reference.manifest.json` 保存于 `packages/campaign/native_reference/`。
manifest 只存来源仓库、commit、URL、SHA256、size、cache identity 和资产 ID 绑定，
不调用 GitHub API、不保存账户或个人资料。

下载先进入同目录临时文件，成功 HTTP 请求、UTF-8 JSON、原生 LevelData schema 与 ID 验证
全部通过后才执行原子 replace。原生标准关卡的内部 levelId 通常为 null；保持这个真实值，
以固定资产 URL 和文件名绑定身份，不伪造内部 levelId。出现非 null 且与请求不同的 ID 时拒绝。

已有 manifest 锁定的缓存必须匹配 SHA256、size、来源和 cache identity；不匹配明确失败，
不会自动下载覆盖。只有显式 `--refresh` 才允许修复缓存，而且刷新仍须通过完整校验。
没有 manifest 的旧文件先与固定 URL 重新下载的字节比对，一致才建立锁；不同则拒绝。
网络或 JSON 失败保留旧文件，清理临时文件，不留下半份成功内容。

已实际批取 36/36，重新执行下载器得到 36/36 verified_cache；本次三套独立测试合计
37 passed，涵盖校验失败保留旧内容、显式刷新、ID 注入、锁定 SHA、TLS 参数与完整本地manifest。
