# 01 character_table 字段映射与结构

> 字段 id 与 C# `CharacterData`（dump.cs:165178）声明顺序一致；
> 用阿米娅/凯尔希/凛御银灰/克洛丝/德克萨斯在二进制上逐字段验证。

## 1. 顶层字段映射（36 字段）

| id | 字段 | 类型 | 验证 |
|---|---|---|---|
| 0 | name | string | 阿米娅 |
| 1 | description | string | 攻击造成法术伤害… |
| 2 | sortIndex | int | 各干员不同（539/194/16…） |
| 3 | spTargetType | int | 特殊干员 |
| 4 | spTargetId | string | 特殊干员 |
| 5 | canUseGeneralPotentialItem | bool | 阿米娅缺省(false)，其他 true |
| 6 | canUseActivityPotentialItem | bool | 活动干员 |
| 7 | potentialItemId | string | p_char_002_amiya |
| 8 | activityPotentialItemId | string | 活动干员 |
| 9 | classicPotentialItemId | string | classic_…（老干员） |
| 10 | nationId | string | rhodes/lungmen/kjera… |
| 11 | groupId | string | penguin（企鹅物流） |
| 12 | teamId | string | reserve（行动预备组） |
| 13 | mainPower | table | PowerData 结构 |
| 14 | subPower | vector | PowerData[] |
| 15 | displayNumber | string | R001/B003/KJ01 |
| 16 | appellation | string | Amiya/Kal'tsit… |
| 17 | position | int | 1=MELEE, 2=RANGED |
| 18 | tagList | string[] | 标签 |
| 19 | itemUsage | string | 获取用途 |
| 20 | itemDesc | string | 干员简介 |
| 21 | itemObtainApproach | string | 招募寻访… |
| 22 | isNotObtainable | bool | |
| 23 | isSpChar | bool | 特殊干员标记 |
| 24 | maxPotentialLevel | int | 恒为 5 |
| 25 | rarity | int | 0..5（TIER_1..6） |
| 26 | profession | int | ProfessionCategory |
| 27 | subProfessionId | string | corecaster/fastsupport/pioneer… |
| 28 | trait | TraitDataBundle | candidates[] |
| 29 | phases | PhaseData[] | 2-3 个精英阶段 |
| 30 | skills | MainSkill[] | 技能引用 |
| 31 | displayTokenDict | dict | 干员→Token 显示 |
| 32 | talents | TalentDataBundle[] | 天赋组 |
| 33 | potentialRanks | PotentialRank[] | 5 条潜能 |
| 34 | favorKeyFrames | KeyFrames | 信赖加成 |
| 35 | allSkillLvlup | SkillLevelCost[] | 技能升级消耗 |

注意：FlatBuffers 里字段值分两类——字符串/表/向量是**槽位相对偏移**；
int/float/bool 是**内联标量**（可能恰好像合法偏移，必须按类型直读）。

## 2. PhaseData（dump.cs:165027）

`{characterPrefabKey, rangeId, maxLevel, attributesKeyFrames, evolveCost}`。
`attributesKeyFrames` 是 KeyFrame 向量：`{level, data{AttributesData}}`
（KeyFrames.KeyFrame，dump.cs:166401）。示例（阿米娅 P0）：
`{level:1, data:{maxHp:699, atk:276, def:48, magicResistance:10.0, cost:18,
blockCnt:1, moveSpeed:1.0, attackSpeed:100.0, baseAttackTime:1.6,
respawnTime:70, spRecoveryPerSec:1.0, maxDeployCount:1}}`。

### AttributesData（我方，dump.cs:162213）

| id | 字段 | | id | 字段 |
|---|---|---|---|---|
| 0 | maxHp | | 16 | baseForceLevel |
| 1 | atk | | 17 | epDamageResistance |
| 2 | def | | 18 | epResistance |
| 3 | magicResistance | | 19 | damageHitratePhysical |
| 4 | cost | | 20 | damageHitrateMagical |
| 5 | blockCnt | | 28 | maxEp |
| 6 | moveSpeed | | 29 | epRecoveryPerSec |
| 7 | attackSpeed | | 30 | spRecoverRatio |
| 8 | baseAttackTime | | 31 | epBreakRecoverSpeed |
| 9 | respawnTime | | 32 | slowDown |
| 10-12 | hpRecoveryPerSec/spRecoveryPerSec/maxDeployCount | | | |
| 13-15 | maxDeckStackCnt/tauntLevel/massLevel | | | |

## 3. 天赋（TalentData，dump.cs:191011）

`{unlockCondition{phase,level}, requiredPotentialRank, prefabKey, name,
description, rangeId, blackboard, tokenKey, isHideTalent}`。
天赋参数在 `blackboard`（key/value 对，value 为十进制 float，另存 value_raw）。

## 4. 潜能（PotentialRank，dump.cs:165090）

`{type(0=BUFF/1=CUSTOM), description, buff, equivalentCost}`。
示例（阿米娅潜能 1）：description 形如“部署费用-1”，buff 为 ExternalBuff
（dump.cs:169581，属性修正）。

## 5. 特性（TraitData，dump.cs:164936）

`{unlockCondition, requiredPotentialRank, blackboard, overrideDescripton,
prefabKey, rangeId}`；参数在 blackboard（如 `atk_scale`）。

## 6. 使用示例（读取干员 P2 满级数值）

```python
import json
c = json.load(open('data/characters.json'))['char_002_amiya']
p2 = c['phases'][2]                      # 精英二
frames = p2['attributesKeyFrames']       # [{level, data{...}}]
last = max(frames, key=lambda f: f['level'])['data']  # 满级属性
```
