# 03 模组系统数据（battle_equip / uniequip）

> 数据：`data/battle_equip.json`（504 包）、`data/uniequip.json`（898 条）。
> 结构依据 dump.cs:169520-169578。

## 1. battle_equip_table（战斗模组数据）

`BattleEquipPack{phases: BattleEquipPerLevelPack[]}`（dump.cs:169569）；
每级包（dump.cs:169554）：

| 字段 | 含义 |
|---|---|
| equipLevel | 模组等级（1/2/3） |
| parts | BattleUniEquipData[]（见下） |
| attributeBlackboard | 干员属性加成（黑板上限，如 `max_hp`/`atk`/`def`） |
| tokenAttributeBlackboard | 召唤物属性加成（按 token id） |

`BattleUniEquipData`（dump.cs:169535）：

| 字段 | 含义 |
|---|---|
| resKey | 模组资源键 |
| target | UniEquipTarget 枚举 |
| isToken | 是否作用于召唤物 |
| validInGameTag / validInMapTag | 生效标签 |
| addOrOverrideTalentDataBundle | 新增/覆盖天赋 |
| overrideTraitDataBundle | 覆盖特性 |

`UniEquipTarget`（dump.cs:169520）：NONE=0/TRAIT=1/TRAIT_DATA_ONLY=2/TALENT=3/
TALENT_DATA_ONLY=4/DISPLAY=5/OVERWRITE_BATTLE_DATA=6。

## 2. uniequip_table（模组本体）

898 条按 uniequip id 索引；包含模组图标/名称/阶段/属性加成黑板上限/故事等。
当前 JSON 为通用索引解析，字段名可对照 `UniEquipData` 类精化（后续工作）。

## 3. 模拟器使用

干员满潜 + 模组后的最终数值 = 基础属性（phase 满级帧） + 信赖（favorKeyFrames）
 + 潜能（potentialRanks buff） + 模组（attributeBlackboard）。
模组天赋/特性覆盖遵循 `target` 枚举决定作用于干员本体还是 Token。
