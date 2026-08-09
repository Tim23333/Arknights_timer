# 06 控制 / 异常状态（受控后的表现与免疫）

> 依据 dump.cs：AbnormalFlag 枚举（1442098）、AbnormalCombo（1442152）、
> Enemy.States.*State（442388-443063）。结论分级【确认】/【推断】。

## 1. 异常旗标全集（AbnormalFlag，dump.cs:1442098）

| 值 | 旗标 | 含义 |
|---|---|---|
| 0 | STUNNED | 眩晕 |
| 1 | SP_RECOVER_STOPPED | SP 回复停止 |
| 2 | TARGET_FREE | 可被无视（不可被选中） |
| 3 | BLOCK_FREE | 不可被阻挡 |
| 4 | HIDDEN | 隐藏 |
| 5 | INVINCIBLE | 无敌 |
| 6 | UNDEADABLE | 不可死亡 |
| 7 | HEAL_FREE | 不可治疗 |
| 8 | UNBALANCE_IMMUNE | 失衡免疫 |
| 9 | INVISIBLE | 隐形 |
| 11 | DISARMED | 缴械（禁用普攻） |
| 12 | SILENCED | 沉默（禁技能） |
| 13 | UNMOVABLE | 不可移动（停顿） |
| 16 | FROZEN | 冻结 |
| 17 | CAMOUFLAGE | 迷彩 |
| 19 | STUNNED_NO_AMPLIFY_DAMAGE | 眩晕(不增伤) |
| 20 | DISABLE_COMBAT | 禁近战 |
| 23 | COLD | 寒冷 |
| 24 | SKILL_NOT_ACTIVATABLE | 技能不可激活 |
| 25 | LEVITATE | 浮空 |
| 26 | DURANCE | 束缚（禁锢） |
| 28 | OUT_OF_GROUND | 出土（沙盒） |
| 31 | DISARMED_COMBAT | 禁战斗攻击 |
| 33 | FEARED | 恐惧 |
| 34 | SKILL_ACTIVABLE_IN_ABNORMAL | 受控中可施放技能 |
| 35 | MOTION_TARGET_FREE | 移动目标自由 |
| 36 | FORCE_LEVITATE | 强制浮空 |
| 39 | PALSY | 麻痹 |
| 40 | PALSYING | 麻痹中 |
| 41 | ATTRACTED | 吸引 |
| 43 | DOZE | 沉睡 |
| 44 | TELEPORTED | 传送 |
| 45 | GROUND_BOUND | 落地束缚 |

`AbnormalCombo`：`SLEEPING=0`（沉睡）、`SHELTERING=1`（庇护）。

## 2. 状态 -> 表现映射（Enemy.States.State，441897）

| 异常 | 状态 | 移动 | 普攻 | 技能 | SP | 备注 |
|---|---|---|---|---|---|---|
| 眩晕 STUNNED | STUN(4) | 停 | 禁 | 禁/中断 | 停 | FinishReason=PALSY 同族中断 |
| 冻结 FROZEN | FROZEN(13) | 停 | 禁 | 禁/中断 | 停 | 冰冻免疫位 |
| 浮空 LEVITATE | LEVITATE(14) | 停 | 禁 | 禁/中断 | 停 | 高度提升，落地后继续 |
| 麻痹 PALSY | PALSY(16) | 停 | 禁 | 禁/中断 | 停 | Ability 收 PALSY 中断 |
| 失衡 UNBALANCE | UNBALANCE(9) | 停 | 禁 | 禁 | - | 击飞前摇 |
| 倒地 FALLDOWN | FALLDOWN(10) | 停 | 禁 | 禁 | - | 失衡后落地 |
| 沉睡 SLEEPING(combo) | DOZE 类 | 停 | 禁 | 禁 | 停 | 受击可醒（受击免疫见敌人免疫位） |
| 停顿 UNMOVABLE | MOVE 内 | 停 | 可 | 可 | 可 | 仅禁移动（如停顿 buff） |
| 束缚 DURANCE | MOVE 内 | 停 | 可 | 可 | 可 | 类似停顿 |
| 沉默 SILENCED | 原状态 | 可 | 可 | 禁 | 可 | EnemySkill `_ignoreSilence` 豁免 |
| 缴械 DISARMED/DISARMED_COMBAT | 原状态 | 可 | 禁 | 可 | 可 | 禁普攻/战斗攻击 |
| 恐惧 FEARED | 特殊 | 逃 | - | - | - | FEARED_PRIVATE 细节在 prefab |
| 吸引 ATTRACTED | 特殊 | 拉向 | - | - | - | 牵引 |
| 传送 TELEPORTED | BLINK(12) | - | - | - | - | 瞬移表现 |

## 3. 免疫（敌方 AttributesData，01 文档 §4）

敌方属性表内置异常免疫位（dump.cs:168958-168979）：
`stunImmune`/`silenceImmune`/`sleepImmune`/`frozenImmune`/`levitateImmune`/
`disarmedCombatImmune`/`fearedImmune`/`palsyImmune`/`attractImmune`/
`teleportImmune`/`groundBoundImmune`。
模拟器施加异常前先查对应免疫位。

## 4. 异常来源与参数（blackboard）

- 技能/天赋通过 blackboard 声明异常：`stun`（眩晕时长秒）、`duration`、
  `interval`、`hit_duration`、`move_speed`（减速）、`ep_damage_ratio`
  （元素损伤）、`cnt`/`times`（次数）等；
- `stun` 数值即眩晕秒数（×30 = 帧数）；多个同类异常通常刷新/叠加由
  AbnormalState 管理器决定（方法体不可见，标注【推断】）；
- 敌人自己施加的异常（如自爆眩晕）同样走这套体系。

## 5. 受控期间的帧级表现

- 进入 STUN/FROZEN/LEVITATE/PALSY 状态时：
  `Enemy.SetEnemyCombatWrapperInterrupted()`（dump.cs:444271）中断近战序列；
  正在施放的 Ability 收 `DoFinish(PALSY/INTERRUPTED)`；
- 状态期间 `OnTick` 只推进异常计时与动画，不推进移动/攻击/技能冷却
  （SP 停止回复）；
- 解除后回到原状态（MOVE/ATTACK/COMBAT）并恢复：移动续走、攻击按剩余
  冷却续打、技能按剩余 CD 继续。

## 6. 不确定点

- 各异常“叠加 vs 刷新 vs 各自计时”的精确规则方法体不可见（【推断】）；
- 恐惧/吸引/出土等特殊状态的完整行为在 prefab 配置中，未逐个解剖；
- 元素损伤（ep）体系（损伤条/爆发）依赖 `maxEp/epRecoveryPerSec/epBreakRecoverSpeed`
  属性与独立异常类型，建议单独展开。
