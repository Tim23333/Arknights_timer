# 01 敌方数据层：enemy_database 全量字段解析

> 数据源：`data/tables/enemy_databasea5b667.bin`（2079 个敌人条目）、
> `enemy_handbook_table493349.bin`（图鉴）。
> 结构依据 `Ark_data/dump.cs`（Il2CppDumper 空壳 dump，字段/枚举/签名可确认，
> 方法体不可见）。结论标注【确认】（字段/枚举直接证据）与【推断】（命名推理）。
> 提取脚本：`ark_parser/enemy/extract_enemy_data.py`（研究产物，不改动项目代码）。

## 1. 提取产物

| 文件 | 内容 |
|---|---|
| `data/enemy_database.json` | 全部敌人：`enemyId -> [ {level, data}, ... ]` |
| `data/enemy_handbook.json` | 图鉴条目（通用索引解析，字段名待精化） |
| `data/stage_enemy_usage.json` | 3467 个关卡 StageData（stageId/levelId/code/name/difficulty…） |
| `data/enemy_stats.json` | 统计：标签/运动模式/等级类型/SP 类型/技能 prefabKey/黑板 key 分布 |
| `data/levels_index.json` | 6021 个 `level_*` 关卡资产索引（关卡内容所在处，见 02 文档） |

## 2. 文件格式（Arknights 自定义 FlatBuffers）

```
[u32 name_len][name bytes][pad 4 对齐][128B 混淆头][u32 版本/标记][root uoffset]
表:   i32 soffset -> vtable(vts/objsz/u16 field_offset[])
字符串: u32 len + UTF-8 + NUL
向量:  u32 count + count 个 4B 槽
字典:  向量元素为 2 字段表 {field0=key字符串, field1=value}
```

**Undefinable\<T\> 包装（关键）**：等级覆盖数据允许"未定义"，`Undefinable<T>`
在表内是 2 字段包装表：`field0 = hasValue`（1 字节 bool，未对齐，
按 i32 读会得到垃圾大数）、`field1 = value`（内联标量或偏移）。空表 = 未定义。
解析时必须按字段类型直读，不能走"偏移启发式"（内联标量如 6000 可能恰好
指向文件内合法大向量，导致误解析）。【确认：实测多敌人验证】

## 3. EnemyData 字段映射（dump.cs:168870）

`EnemyDatabase.EnemyData` 的 FlatBuffers 字段 id 与 C# 声明顺序一致（vtable 截断尾部未定义字段）：

| id | 字段 | 类型 | 含义 |
|---|---|---|---|
| 0 | `name` | Undefinable\<string\> | 敌方名 |
| 1 | `description` | Undefinable\<string\> | 描述（含 `<@eb.key>` 富文本） |
| 2 | `prefabKey` | Undefinable\<string\> | 数据键（= 敌人 id，`EnemyDataMeta(AssignName="key")`） |
| 3 | `attributes` | AttributesData | 数值（见 §4） |
| 4 | `applyWay` | Undefinable\<SourceApplyWay\> | 近战/远程来源适用（MELEE=1/RANGED=2/ALL=3，dump.cs:1442298） |
| 5 | `motion` | Undefinable\<MotionMode\> | 移动模式（WALK=0/FLY=1，dump.cs:1442309） |
| 6 | `enemyTags` | Undefinable\<string[]\> | 标签（sarkaz/infection/drone…） |
| 7 | `lifePointReduce` | Undefinable\<int\> | 进蓝门扣生命数 |
| 8 | `levelType` | Undefinable\<EnemyLevelType\> | NORMAL=0/ELITE=1/BOSS=2（dump.cs:169386） |
| 9 | `rangeRadius` | Undefinable\<float\> | 攻击范围半径（格子） |
| 10 | `numOfExtraDrops` | Undefinable\<int\> | 额外掉落次数 |
| 11 | `viewRadius` | Undefinable\<float\> | 索敌视野半径 |
| 12 | `notCountInTotal` | Undefinable\<bool\> | 不计入总数/击杀数 |
| 13 | `talentBlackboard` | Blackboard | 天赋参数（见 §6） |
| 14 | `skills` | ESkillData[] | 技能列表（见 §5） |
| 15 | `spData` | ESpData | SP 配置（见 §5） |

顶层 `EnemyDatabase`（dump.cs:169026）：`enemies = List<KeyValuePair<string, List<EnemyLevel>>>`；
`EnemyLevel{level:int, enemyData:EnemyData}`（dump.cs:168899）。同一敌人 id 可有多个
level（1/2/3 级数据，213 个敌人 2 级、23 个 3 级），运行时按关卡引用等级取对应覆盖。
`EnemyDatabase.GetComputedEnemyData(id, level)`（dump.cs:169040）合并基础+覆盖。

## 4. AttributesData 字段映射（dump.cs:168913，32 字段）

| id | 字段 | 类型 | id | 字段 | 类型 |
|---|---|---|---|---|---|
| 0 | maxHp | int | 16 | epDamageResistance | float |
| 1 | atk | int | 17 | epResistance | float |
| 2 | def | int | 18 | damageHitratePhysical | float |
| 3 | magicResistance | float | 19 | damageHitrateMagical | float |
| 4 | cost | int | 20 | epBreakRecoverSpeed | float |
| 5 | blockCnt | int | 21 | stunImmune | bool |
| 6 | moveSpeed | float | 22 | silenceImmune | bool |
| 7 | attackSpeed | float | 23 | sleepImmune | bool |
| 8 | baseAttackTime | float | 24 | frozenImmune | bool |
| 9 | respawnTime | int | 25 | levitateImmune | bool |
| 10 | hpRecoveryPerSec | float | 26 | disarmedCombatImmune | bool |
| 11 | spRecoveryPerSec | float | 27 | fearedImmune | bool |
| 12 | maxDeployCount | int | 28 | palsyImmune | bool |
| 13 | massLevel | int | 29 | attractImmune | bool |
| 14 | baseForceLevel | int | 30 | teleportImmune | bool |
| 15 | tauntLevel | int | 31 | groundBoundImmune | bool |

要点：【确认】`baseAttackTime`（秒，普攻周期）与 `attackSpeed`（攻速，100 基准）同时存在；
免疫位直接对应异常状态能否作用于该敌人（详见 06 文档）。`moveSpeed` 单位为格/秒。

## 5. 技能与 SP 结构

`ESkillData`（dump.cs:172044，6 字段，非 Undefinable）：

| id | 字段 | 含义 |
|---|---|---|
| 0 | `prefabKey` | 技能 prefab 键（决定具体能力组件，见 03 文档） |
| 1 | `priority` | 选技优先级（m_skills 按此排序） |
| 2 | `cooldown` | 冷却（秒） |
| 3 | `initCooldown` | 首次冷却（秒，null=用 cooldown） |
| 4 | `spCost` | SP 消耗（>0 时走 SP 型释放） |
| 5 | `blackboard` | 技能参数（见 §6） |

`ESpData`（dump.cs:172062）：`spType`（SpType 枚举，dump.cs:1442353：
NONE=0/随时间=1/攻击回复=2/受击回复=4/攻或受=6/全部=7）、`maxSp`、`initSp`、`increment`。
敌方 SP 由 `SpData.CreateFrom(eSpData, blackboard)`（dump.cs:188279）运行时构建。

## 6. Blackboard（数据对）

`Blackboard = List<DataPair>`；DataPair 三字段：`key`(string)、`value`(float，二进制存为 i32)、
`valueStr`(string，可选)。**数值显示规则**：value 按 IEEE754 单精度转十进制
（1065353216 -> 1.0），JSON 中同时保留 `value`（转换后）与 `value_raw`（原始 i32）。

高频技能黑板键（enemy_stats.json 实测）：`atk_scale`(375)、`duration`(235)、
`range_radius`(153)、`stun`(83)、`interval`(67)、`ep_damage_ratio`(67)、
`max_target`(66)、`branch_id`(58)、`enemy_key`(55)、`hp_ratio`(40)、
`projectile_life_time`(43)、`projectile_range`(39)、`sp`(41)、`move_speed`、`attack_speed` 等。
天赋黑板的 key 以 `talent:<天赋>.` 为前缀（如 `talent:Reborn.hp_ratio`、`talent:Trace.view_radius`）。

## 7. 统计概览（实测）

- 敌人总数 **2079**；单等级 1843、双等级 213、三等级 23。
- 运动模式：WALK 默认 2157、FLY 181（motion 未定义即 WALK）。
- 等级类型：NORMAL 默认 1209、ELITE 824、BOSS 305。
- SP 类型：攻击回复 157、随时间 129、受击回复 2。
- 技能：**849 个敌人带技能，共 711 种 prefabKey**；高频：`slapshot`(58)、
  `clearance`(44)、`Produce`(24)、`Boom`(21)、`Blink`(20)、`PowerAttack`(18)、
  `Charge`/`Devour`/`Reborning`/`StunAttack`/`Suicide`/`Revive`/`Summon`/`Lasso`/`AOE`/`Fly` 等。
  prefabKey 决定了实际行为组件（03 文档的 Ability/TargetTrigger 体系），
  具体组件参数在 `data/battle/enm_pfb_*.ab_unpacked` 的敌方 prefab 中。

## 8. 示例条目

### 8.1 enemy_10001_trslim（源石虫，地面杂兵）

```json
{"level": null, "data": {
  "name": "源石虫", "prefabKey": "enemy_10001_trslim",
  "attributes": {"maxHp": 4500, "atk": 200, "def": 50, "magicResistance": null,
    "moveSpeed": 1.0, "attackSpeed": 100.0, "baseAttackTime": 1.7,
    "stunImmune": false, ...},
  "motion": null, "levelType": null,
  "skills": [{"prefabKey": "StartRun", "priority": null, "cooldown": null, ...}]
}}
```

### 8.2 enemy_10137_pycvol（Boss“熔火蜗”示例，含 Pollute 技能）

```json
{"skills": [{"prefabKey": "Pollute", "priority": 1, "cooldown": 20.0,
  "blackboard": [{"key": "max_cnt", "value": 3.0}, {"key": "move_speed", "value": 1.0},
    {"key": "damage_scale", "value": 1.2}, {"key": "range_radius", "value": 3.0}]}]}
```

## 9. 加载建议（给模拟器）

1. 用 `enemy_database.json` 按 `(enemyId, level)` 建索引；`level=null` 视为 0。
2. `attributes` 未定义字段按类型默认值处理（HP/ATK=0、moveSpeed=0、attackSpeed=100、
   baseAttackTime=0、免疫=false）。
3. 技能以 `prefabKey` 为运行时键，`blackboard` 提供参数；`cooldown/initCooldown/spCost/priority`
   驱动释放调度（详见 03/07 文档）。
4. 图鉴 `enemy_handbook.json` 目前为通用索引解析（字段 0=id、1=classLevel、4=name、
   6=description、15=攻击范围向量），后续可对照 `EnemyHandbookInfo`（dump.cs 附近
   169339-169372）精化字段名。

## 10. 不确定点

- 图鉴条目字段名未按 C# 类精化（结构已提取）。
- `skills[].initCooldown` 在部分条目为 null（字段确实缺省）；具体语义（null 是否等于
  cooldown）需 prefab/运行时确认（03 文档 §4 已讨论 `_overwriteInitCooldown`）。
- EnemyLevel.level=null 的默认等级语义（0）为推断。
