# 00 我方干员 / 召唤物 / 中立装置数据总览

> 目标：把“我方侧”数据整理成可直接供战斗模拟器消费的 JSON + 结构文档。
> 结论分级【确认】（dump.cs 字段/枚举 + 实测）与【推断】。

## 1. 产物清单

| 文件 | 内容 |
|---|---|
| `data/characters.json` | character_table 全量（**1323** 条：干员 + 召唤物 + 中立装置 + NPC 类） |
| `data/skills.json` | skill_table 全量（**1795** 条技能） |
| `data/devices.json` | `token_trap`（**869** 个职业 TOKEN/TRAP 的装置/召唤物）+ `special_unobtainable`（67 个） |
| `data/battle_equip.json` | 模组战斗数据（504 包） |
| `data/uniequip.json` | 模组外观/属性表（898 条） |
| `extract_character_data.py` | 提取脚本（研究产物，复用 `ark_parser/enemy/extract_enemy_data.py` 的 FB 读取器） |

## 2. 分类判据（【确认】ProfessionCategory 枚举，dump.cs:1442602）

- **普通干员**：`profession` ∈ WARRIOR(1)/SNIPER(2)/TANK(4)/MEDIC(8)/SUPPORT(16)/
  CASTER(32)/SPECIAL(64)/PIONEER(512)。
- **召唤物 Token**：`profession = TOKEN(128)`，id 形如 `token_10002_kalts_mon3tr`（Mon3tr）、
  `token_10009_weedy_cannon`（水炮）等。
- **中立装置/陷阱**：`profession = TRAP(256)`（如障碍物/地雷类）以及 `isNotObtainable`/
  `isSpChar` 标记的特殊单位。
- `position`：MELEE=1（近战位）/ RANGED=2（远程位）（BuildableType，dump.cs:1442162）。
- `rarity`：RarityRank TIER_1..TIER_6 = 0..5（dump.cs:1442533）。

## 3. 统计概览

- character_table 共 **1323** 条：包含全部正式干员、异格、召唤物、中立装置、敌方/NPC 复用角色。
- Token/TRAP 装置 **869** 个（含同干员多召唤物，如麦哲伦 drone1-3）。
- 技能 **1795** 个：`skchr_<代号>_<1|2|3>` 干员技能 + `skcom_*` 通用技能 +
  `sktok_*` Token 技能。
- 模组 battle_equip 504 包 / uniequip 898 条。

## 4. 与敌方侧的对称性

干员与敌人都基于 `Unit`（dump.cs 中 Unit 基类），共用：
- `AttributesData` 数值体系（我方 HP/ATK/DEF/魔抗/费用/阻挡/攻速/baseAttackTime/再部署…）；
- `SpController` + `SpData`（spType/spCost/initSp/increment，dump.cs:188231）；
- `Ability` 施放管线（FamilyGroup ATTACK/COMBAT/SKILL/TALENT/GENERAL，dump.cs:367418）与
  `FinishReason`（NORMAL_EXIT/INTERRUPTED/OWNER_DEAD/TARGET_DEAD/PALSY，dump.cs:367458）。

因此敌方行为模拟器的“帧驱动 + Ability 施放 + 状态机”骨架可直接复用到我方干员。
