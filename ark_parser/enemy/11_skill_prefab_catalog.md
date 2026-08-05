# 11 敌方技能 prefab 参数目录（enm_pfb 全量提取，2026-08-05）

> 从 `data/battle/enm_pfb_*.ab_unpacked`（36 个包、1225 个 CAB）用 UnityPy
> 读取全部 MonoBehaviour 类型树，产出技能行为目录。覆盖 enemy_database
> 全部 711 个 prefabKey 中的 **682 个（95.9%）**、1658 个（敌人,技能）实例。

## 1. 产物

| 文件 | 内容 |
|---|---|
| `data/skill_prefab_catalog.json`（~35MB） | 全量：4423 个 GameObject（prefabKey）→ 47802 个组件（class 标签 + 完整序列化字段 + cabin/pathID/scriptPathID） |
| `data/skill_prefab_catalog_summary.json` | 每 prefabKey 的紧凑参数（EnemySkill/Ability/AttackAbility/BuffAbility 关键字段 + buffKeys） |
| `data/skill_behavior_catalog.json` | **逐敌人技能**：enemy_database blackboard + prefab 组件参数 + 已解析 trigger + buffKeys 合并 |
| `data/skill_prefab_coverage.json` | 覆盖统计与缺失清单 |

## 2. 提取管线

`extract_prefab_skills.py`：遍历 enm_pfb CAB → UnityPy `read_typetree()` →
按字段签名打 class 标签（Arknights 的 CAB 里没有 MonoScript 对象，类名只能
靠签名推断，scriptPathID 已保留供后续精确映射）→ 按 GameObject 名分组。

`build_skill_behavior.py`：把 enemy_database 的 ESkillData（priority/
cooldown/initCooldown/blackboard）与 prefab 组件合并，并用 `_trigger`
的 PPtr pathID 在同 prefab 内解析出 Trigger 组件参数。

## 3. 组件 class 标签（签名启发式）

| class | 判别字段 | 数量 |
|---|---|---|
| EnemySkill | `_familyMask` | 1337 |
| AbilityStandard | `_castEffects`/`_preDelayFactor` | 3245 |
| AttackAbility | `_attackBlackboardModeIndex`/`_defaultModeIndex` | 3285 |
| BuffAbility | `_extraCondition`+`_maxTarget` | 771 |
| ProjectileAbility | `_projectileActions` | 111 |
| CompositeAbility | `_abilities` | 219 |
| Ability | `_selector`+`_waitForAttackEvent` | 4817 |
| Other | 动画/表现/占位组件 | 34017 |

## 4. 已确认的模拟关键字段

EnemySkill（dump.cs:385626）：
- `_familyMask`：Ability.FamilyGroupMask（1=ATTACK/2=COMBAT/4=SKILL/8=TALENT…，
  PowerAttack=3 即 ATTACK|COMBAT，远近战通用）；
- `_maxTriggerTime`：-1 无限次；`_overwriteInitCooldown`：-1 表示用数据层
  cooldown/initCooldown（03 文档 §4.1）；
- `_ignoreSilence`、`_castLikeAttack`（走攻击流程释放）、`_spCost`。

AbilityStandard（dump.cs:368229/12999）：
- `_waitForAttackEvent=1` → 类普攻释放（04 文档）；
- `_timeMode`：0=FROM_ATTACK_SPEED（吃攻速）、1=FROM_ANIMATION、
  2=SPECIFIED（用 `_cooldown`）、3=LOAD_FROM_BLACKBOARD（用 `_cooldownKey`）；
- `_selectTargetSource`：0=NONE、1=FROM_OWNER、2=INPUT_TARGET、3=INPUT_POINT、
  4=INPUT_GRID_POS；
- `_selectTargetTiming`：0=AT_BEGINING、1=BEFORE_SPELL_START、
  2=RESELECT_IF_TARGET_DEAD、3=BEFORE_FIRST_SPELL_START；
- `_preDelay`/`_preDelayFactor`、`_cooldown`/`_cooldownKey`、`_escapeTime`、
  `_animKey` 系列（攻击/下落动画键）。

AbilityStandard.Event：0=ON_ATTACHED、1=ON_DETACHED、2=ON_CAST_START、
3=ON_CAST_END、4=ON_SPELL_ON、5=ON_SPELL_END、6=ON_ATTACK_FINISH、
7=ON_ATTACK_CHECK_POINT、8=ON_OVERLOAD（驱动 castEffects 的起止帧）。

## 5. 样例结论（blackboard × prefab）

- **PowerAttack**（18 敌）：EnemySkill familyMask=3；Ability waitForAttackEvent=1、
  timeMode=0（吃攻速）、atkScale=1.0；伤害倍率来自 blackboard `atk_scale`
  （如 1.5）；buffKeys 含 `sfpin_power_attack` 等。
- **StartRun**（逃跑）：timeMode=2（SPECIFIED）、selectTargetSource=2；
  blackboard `move_speed`/`block_free_time` 决定加速与不可阻挡时长。
- **Shine**（闪亮）：waitForAttackEvent=0、timeMode=3（LOAD_FROM_BLACKBOARD）；
  blackboard `interval/duration/stun/range_radius` 直接喂给技能。
- **AirSupportAtk**（空援轰炸）：EnemySkill maxTriggerTime=1（只触发一次）；
  blackboard `duration`。
- **Boom**（源石虫自爆）：无 EnemySkill，实为**死亡 buff** 组件
  （buffKeys：`enemy_vtzepl_die`、`enemy_ftzlc[boom]`、`projectile_on_killed`…）。

## 6. 已知限制

- 29 个 prefabKey 未在 enm_pfb 找到：多为攻击模式变体（M0/M1/T0/T1/S1*，
  由 prefab 的 mode index 配置实现）与行为节点名（Branch/Exit/Return/
  DownAnim/Countdown 等），不一定是独立 prefab。
- **全部 253 个已解析 TargetTrigger 均为空壳**（无序列化参数）：触发条件
  由技能 blackboard（如 `range_radius`/`interval`/`duration`）或 TargetTrigger
  子类代码决定，prefab 只负责挂类型（scriptPathID）。全量目录里仅 1 种带
  参数的 TriggerCondition 组件（`_hpRatio`/`_buffsToTirgger` 等，3 处）。
- class 标签为签名启发式；如需精确类名可用 DNFBDmp 生成 .fbs 或按
  scriptPathID 对照 global-metadata。
- class 标签为签名启发式；如需精确类名可用 DNFBDmp 生成 .fbs 或按
  scriptPathID 对照 global-metadata。
