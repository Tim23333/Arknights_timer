# 09 敌方技能 prefab 解剖（enm_pfb 实测证据）

> 敌方技能 prefabKey 对应的 GameObject 资产在
> `data/battle/enm_pfb_*.ab_unpacked`（36 个包），可用 UnityPy 直接读取组件
> 序列化字段，验证 03/04/07 文档的框架。以下为实测样例。

## 1. 命名映射【确认】

prefabKey 直接对应 GameObject 名：`boom`、`stunAttack`、`Devour`、`PowerAttack`、
`Slapshot` 等均可在 enm_pfb 中找到（实测 14 个匹配样例，含 `Boom_enemy/Boom_ally`
变体、`Boom[ddlamb]` 等按干员/阵营细分）。

## 2. 样例：PowerAttack（CAB-39e1b2e5768b3ccda9d22135c681ed56）

GameObject `PowerAttack` 挂 3 个 MonoBehaviour：

### 2.1 EnemySkill（字段实测）

```json
{"_familyMask": 3,           // ATTACK|COMBAT：非阻挡与阻挡态都可用
 "_trigger": null,           // 无独立 TargetTrigger —— 走攻击流程触发
 "_checkParentActive": 0,
 "_maxTriggerTime": -1,      // 无限次
 "_resetMainAbilityCdWhenCastEnd": 0,
 "_resetCdWaitFirstPeriod": 1,
 "_overwriteInitCooldown": -1,
 "_ignoreSilence": 0}
```

### 2.2 Ability（字段实测）

```json
{"_selector": null,
 "_waitForAttackEvent": 1,     // 等待攻击事件（类 castLikeAttack，04 文档）
 "_interruptAbilityOnDetach": 0,
 "_attachPassiveBuffsOnDummy": 1,
 "_forceAsDmgOrHealAbility": 0,
 "_ignoreIfOwnerDead": 0,
 "_interuptIfTargetDead": 0}
```

### 2.3 演出/特效组件（字段实测）

```json
{"_castEffects": [
   {"_directionType": 0, "_effects": ["enemy_dubmb_attack_start_01","","",""],
    "_startEvent": 2, "_endEvent": 3, "_oneshot": 0,
    "_useFourDirectionalFace": 0, "_delayIfFirstAttack": 0.0},
   {"_effects": ["enemy_dubmb_skill_start_01", ...], ...}],
 "_preDelayFactor": 0.0}
```

## 3. 对文档的验证意义

- **触发方式**：PowerAttack 无 Trigger 组件、`_waitForAttackEvent=1` → 按普攻/战斗
  攻击流程释放（04 文档 §3/§4），`_familyMask=3` 说明远近战通用；
- **选技字段**：`_maxTriggerTime/_ignoreSilence/_resetMainAbilityCdWhenCastEnd/
  _overwriteInitCooldown/_resetCdWaitFirstPeriod` 与 03 文档 §2.1 的序列化字段一一对应，
  且 EnemySkill 组件的实际字段名得到证实；
- **CD 语义**：`_overwriteInitCooldown=-1` 表示“用数据层 initCooldown/cooldown”，
  与 03 文档 §4.1 一致；
- **演出帧**：`_startEvent/_endEvent`（AbilityStandard.Event 枚举值 2/3 =
  ON_CAST_START/ON_CAST_END，03 文档 §5.1）驱动特效，preDelayFactor 参与起手缩放。

## 4. 已完成（2026-08-05，见 11 文档）

1. 批量解剖完成：`data/skill_prefab_catalog.json`（4423 prefabKey / 47802 组件）；
2. Trigger 解析：`data/skill_behavior_catalog.json` 内已按 PPtr 引用解析（253 个
   技能带 trigger，实测全部为无序列化参数的空壳——触发条件来自 blackboard
   的 range_radius/interval 等或代码，见 11 文档 §6）；
3. blackboard × prefab 合并：`data/skill_behavior_catalog.json` 逐技能给出
   cooldown/initCooldown/atk_scale/duration/stun 等与 familyMask/timeMode/
   preDelay/animKey 的对应关系，可直接用于帧级时序推导。
