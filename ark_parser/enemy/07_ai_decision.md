# 07 判定逻辑（索敌 / 状态切换 / 选技 / 阶段与脚本节点）

> 与 03 文档 §3（选技决策）配套：本文补索敌、状态切换、多阶段、脚本节点。
> 结论分级【确认】（签名/枚举/注释）与【推断】（语义归纳）。

## 1. 索敌（TargetTrigger / SearchTarget）

### 1.1 触发源

- `TargetTrigger`（dump.cs:437376，抽象）：`target / isReadyToTrig / Search(bool
  force) / CheckTargetIn / Reset(owner, ability)`；
- 典型子类 `TileTrigger`（437436）：搜“地面格上的目标”，`SEARCH_TARGET_TICK=5`
  每 5 帧搜一次（`m_findTargetTicker`）；
- `TileTriggerWithCertainCondition`（437488）：附加异常/条件过滤；
- 数十种子类覆盖：范围/阻挡者/血量/标签/异常免疫等条件。

### 1.2 索敌半径

- 敌人静态索敌半径 = `attributes.rangeRadius`（远程攻击距离）与
  `viewRadius`（视野）取用场景不同（普攻触发 vs 技能触发）【推断】；
- 技能索敌半径：`EnemySkill._GetRangeRadius(data, owner)`（385898）静态计算，
  可被词条 `enemy_skill_radius_mul` 放大（03 文档 §1.4）。

### 1.3 目标优先级【推断】

方法体不可见；依据通用规则与 `TARGET_FREE/BLOCK_FREE/MOTION_TARGET_FREE`
旗标推断：范围内“未被隐藏/无敌/不可选中”的敌方目标，近战优先阻挡者，
远程按距离/出生顺序。精确排序建议用现网回放验证。

## 2. 状态切换判定（MOVE/ATTACK/COMBAT）

`Enemy.States.MoveState` 区域（dump.cs:441431-441470）暴露关键私有方法：

- `_CheckCanSwithToAttackState()`（441441）：能否进入攻击态（有目标 + 冷却就绪）；
- `_SearchAttackTarget()`（441444）：行进中搜索攻击目标；
- `_FetchCombatTarget()`（441447）：取阻挡者（被阻挡时）；
- `_CheckBlockable(Entity, source, out weight, out volume)`（441462）：
  阻挡判定（重量/体积/motionMode）；
- `CheckInBlockRange(entity, shrink)`（441456）/ `_SearchBlockee(force)`（441459）。

切换规则（【推断】，由 FSM 与状态类归纳）：

```
MOVE 态每 tick:
  if 被阻挡（blockee 存在且可战斗）: -> COMBAT
  elif _SearchAttackTarget() 命中且普攻/技能可放: -> ATTACK
  else: 继续移动
ATTACK 态:
  打完/被打断 -> 若被阻挡 -> COMBAT，否则 -> MOVE
COMBAT 态:
  阻挡解除 -> NextCombatOrExit -> MOVE/ATTACK
```

## 3. 选技与普攻互斥（承接 03 文档 §3.1）

```python
def pick_action(enemy):
    wrapper = enemy.combatWrapper if enemy.is_blocked else enemy.attackWrapper
    for skill in enemy.m_skills:              # priority 排序
        if skill.available() and skill.trigger_ready():   # 见 03 §3.1
            return cast(skill)
    if wrapper.main_attack_cd_ready():
        return cast(wrapper.main)
    return None
```

关键可用性检查（03 文档 §2.1/§4）：
`isEnabled`（含沉默、`_ignoreSilence` 豁免）、`isUsedUp`（`_maxTriggerTime` 限次）、
CD 就绪（`PeriodicTimer`，dump.cs:112094）、SP 足够（`isSpCostSkill`）、
`CheckTrigger(allowNoTrigger)`（无目标时若能力 `allowNoTarget` 仍可放，367710）。

## 4. 多形态 / 多阶段敌人

- `EnemySkill._checkParentActive`（03 文档 §2.1，0x28）：技能要求父形态（UnitMode）
  激活才可用——多形态敌人按形态过滤技能；
- `Enemy.UnitMode` / 阶段切换由脚本节点或行为树驱动（如 Boss 转阶段触发
  `Nodes.TriggerEnemySkill`）；
- 运行时改选择器参数：`Enemy.TryUpdateEnemySkillSelector(skillKey, checkActivate,
  blackboardKey, value)`（dump.cs:445043）——如动态改 `max_target`；
- 敌人形态相关的免疫/属性变化由异常旗标与 attributes 覆盖承载。

## 5. 行为树 / 事件节点（Nodes.*）

| 节点 | dump.cs | 作用 |
|---|---|---|
| Nodes.TriggerEnemySkill | 600935 | 强制触发指定技能；注释确认“combat 与非 combat 触发逻辑不同”；开关含 `_checkSkillActive/_checkSkillReady/_interruptCurAbility/_forceFindTargetBySkillSelector/_clearPalsyingBuffBeforeTrigger/_tryCastDirectlyWhenNoTarget` |
| Nodes.CheckEnemySkillSelectorHasTargets | 600671 | 检测选择器是否有目标 |
| Nodes.CheckEnemySkillAffecting | 590513 | 检测技能是否生效中 |
| Nodes.ModifyEnemySkillMaxTarget | 600817 | 改技能 max_target |

这些节点由关卡/Boss 脚本（xLua）组合，负责血量阈值、转阶段、强制放技等
“非统一 AI”逻辑；纯数据敌人不需要。

## 6. 模拟器实现注意

1. 普通敌人：每可行动帧跑 §3 的选技循环即可覆盖绝大多数行为；
2. 阈值/脚本型（Boss）：需要额外接入 Nodes.* 语义（至少 TriggerEnemySkill 的
   强放与打断开关）；
3. 索敌每 5 帧（TileTrigger）与“每帧搜索”的区别影响帧级一致，模拟器可
   直接每帧搜索（结果差异仅在极端移动场景）。

## 7. 不确定点

- priority 排序方向（升/降）为【推断】（03 文档）；建议以实测 BOSS 技能顺序校准；
- 目标排序规则（距离 vs 出生顺序 vs 阻挡）方法体不可见；
- 行为树（xLua）内容不在 dump.cs 中，Boss 专属逻辑需从关卡脚本/社区数据补齐。
