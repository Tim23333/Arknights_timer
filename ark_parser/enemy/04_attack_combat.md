# 04 攻击与战斗时序（普攻 / 被阻挡近战 / 帧级流程 / 打断）

> 与 03 文档（技能系统）配套：本文聚焦普攻与“战斗攻击”的帧级时序。
> 结论分级【确认】（字段/枚举/签名）与【推断】（方法体不可见时的语义归纳）。

## 1. 两条攻击管线

`Enemy` 持有（03 文档 §2.5）：
- `attackWrapper`（dump.cs:443259）：**非阻挡态**（MOVE/ATTACK）使用的远程/行进攻击；
- `combatWrapper`（dump.cs:443333）：**被阻挡后**的近战循环。

二者都持 `mainAttack`/`mainCombat`（`AbstractBasicAttack : Ability`）与技能列表，
并实现 `SearchTarget / Cast / _OnCastFinish` 或 `_PickAbility / StartCombat /
NextCombatOrExit`。

## 2. 普攻节奏（属性驱动）

- `attributes.baseAttackTime`：一次完整普攻周期（秒），如源石虫 1.7；
- `attributes.attackSpeed`：攻速（100 为基准，buff 修正倍率）；
- 实际周期 = `baseAttackTime * (100 / attackSpeed)`（【推断】，由攻速语义推出）；
- 每 tick 推进 `Ability.m_cooldownTimer`，CD 归零且索敌成功即发起下一次攻击。

## 3. Ability 施放帧级阶段（03 文档 §2.4/§5 展开）

```
发起 CastToTarget
  ├─ preDelay（起手，期间 isPredelay=true，可被打断）
  ├─ 生效（damage/hit/projectile 发射点；isCasting=true）
  └─ 收尾 -> DoFinish(FinishReason, resetCd)
      FinishReason: NORMAL_EXIT=0 / INTERRUPTED=1 / OWNER_DEAD=2 /
                    TARGET_DEAD=3 / PALSY=4   （dump.cs:367458）
```

- `m_castStartFrameCnt`（Ability 0x5C）记录起始帧，用于帧级同步；
- 技能/普攻共用此管线；`EnemySkill._castLikeAttack`（03 文档 §2.1）让技能
  “按普攻方式施放”（占用攻击动作、吃攻击流程回调）。

## 4. 被阻挡近战（CombatWrapper）

`Enemy.CombatWrapper`（dump.cs:443333）：
- `StartCombat(firstAttack)` 进入近战循环；`NextCombatOrExit(firstAttack)`
  打完一刀后决定“继续下一刀”还是“脱战退出”；
- `_PickAbility` / `_EarlyPickAbility`：选普攻还是技能（优先级排序，07 文档）；
- `m_isCombatInterrupted` + `Enemy.SetEnemyCombatWrapperInterrupted()`
  （dump.cs:444271）：受控/打断时中断近战序列；
- 阻挡解除（目标死亡/离开）时 `NextCombatOrExit` 退出 COMBAT 回 MOVE。

## 5. 打断与恢复规则

- `Enemy.InterruptLastAbilityIfNot(bool resetCooldown, Ability ability)`
  （dump.cs:44680）：打断上一次施放（除非就是传入的 ability），可选重置 CD；
- `Ability.InterruptIfNot()`（dump.cs:367827）+ `DoFinish(INTERRUPTED)`；
- `FinishReason=OWNER_DEAD`：敌人死亡强制中止；`TARGET_DEAD`：目标死亡，重选目标；
- `PALSY`：麻痹直接中断施放（异常体系，06 文档）；
- 技能特有：`_resetMainAbilityCdWhenCastEnd`（放完技能重置普攻 CD，
  03 文档 §2.1）、`_resetCdWaitFirstPeriod`。

## 6. 弹道与伤害结算时机

- 远程攻击通过 `Projectile`（dump.cs:413122）发射；命中后结算伤害；
- 相关黑板键：`projectile_life_time`（寿命）、`projectile_range`（射程）、
  `projectile_speed`（速度）、`hit_duration`（命中持续时间）；
- 近战普攻在 Ability 生效帧直接对目标结算。

## 7. 模拟器要点（帧级）

```python
def enemy_tick(enemy, dt):            # dt = 1/30
    if enemy.state in (ATTACK, COMBAT):
        wrapper = enemy.combatWrapper if enemy.is_blocked else enemy.attackWrapper
        if not wrapper.casting_ability:
            if wrapper.cooldown_timer <= 0 and wrapper.has_target():
                ability, skill = wrapper.pick_next()   # 07 文档
                wrapper.cast(ability, skill)
    # Ability 阶段推进（preDelay -> 生效 -> 收尾）
    for ability in active_abilities:
        ability.tick(dt)
```

## 8. 不确定点

- `baseAttackTime * 100/attackSpeed` 的精确公式（含四舍五入/定点数）为【推断】，
  建议用现网实测校准；
- 近战“生效帧”相对 preDelay 的偏移在 prefab 配置中，需解析 enm_pfb 资产确认。
