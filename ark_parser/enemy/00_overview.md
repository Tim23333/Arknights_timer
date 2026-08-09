# 00 敌方行为模拟总览（数据 -> 运行时 -> 每帧调度）

> 本文把 `data/` 数据层、`dump.cs` 运行时类、既有 01/02/03/05/06/07/08 文档串成
> 一条“可直接实现敌方行为模拟器”的链路。结论分级【确认】/【推断】。

## 1. 数据 -> 运行时映射

```
数据表（01/02 文档）                      运行时组件（dump.cs）
enemy_database.json  EnemyData    ──>   Enemy : Unit
  attributes                           AttributesData（HP/ATK/攻速/移速/免疫位…）
  talentBlackboard                     BasicTalent / TalentBlackboard
  skills[] (ESkillData)                EnemySkill[] + Ability + TargetTrigger
  spData (ESpData)                     SpController / SpData
  motion / rangeRadius                 MoveController / 索敌半径
stage/level 资产                       关卡初始化：EnemyDatabase.GetComputedEnemyData
  enemyDbRefs{id,level}                (id, level) -> EnemyData 合并
  waves[]/routes[]                     WaveScheduler / Route / BasicCursor
  runes (词条)                         战前改写技能/属性
```

关卡资产（`level_*` TextAsset，Only Sign）已于 2026-08-05 解密：2854 个关卡
解析在 `data/levels/*.json`；模拟汇总 `data/stage_sim_bundle.json`（含
`waveTimeline` 绝对时间表、enemyRoster、stage 映射）；覆盖统计
`data/sim_coverage.json`（3467 stage 中 2140 已有关卡）。流程见 02 文档 §1.1，
schema 校准见 10 文档。

## 2. 逻辑帧

【确认】`GlobalConsts.TIME_ROUGH_LOGIC_RATE = 30`（dump.cs:441464），即
**1 秒 = 30 tick**，固定步长驱动所有 `OnTick(FP deltaTime)`。
模拟器按 30Hz 积分即可与游戏逻辑一致（05 文档 §0）。

## 3. 每帧调度顺序（【推断】，由类职责与既有文档归纳）

```
BattleController.Tick(1/30s)
  1. 波次调度：WaveScheduler 到点生成敌人（02 文档）
  2. 每个 Enemy.OnTick：
     a. 状态机 tick（当前 State.OnTick）：移动/攻击/技能/异常
     b. MoveState: MoveController.CalculateMoveDelta -> 位置积分（05 文档）
     c. AttackState/CombatState: 冷却推进 -> _StartAttack / 选技（04/07 文档）
     d. EnemySkill.Tick: 技能冷却 / Behaviour.OnTick（03 文档 §2.1）
     e. Ability.Tick: 施放中 Ability 的 preDelay/生效/收尾（03 文档 §5）
     f. 异常状态计时（Stun/Freeze/Levitate/Palsy…，06 文档）
     g. SpController: SP 回复（随时间型每秒 increment）
  3. 碰撞/阻挡/寻路更新（05 文档 §4/§6）
```

## 4. 状态机总表（Enemy.States.State，dump.cs:441897）

| 值 | 状态 | 主要行为 | 状态类 |
|---|---|---|---|
| 0 | DEFAULT | 占位 | - |
| 1 | MOVE | 沿路线移动，行进中可放远程技能/普攻 | MoveState(442119) |
| 2 | ATTACK | 射程内远程攻击/技能循环 | AttackState(442158) |
| 3 | COMBAT | 被阻挡近战循环 | CombatState(442364) |
| 4 | STUN | 眩晕：不可移动/攻击/技能，SP 停 | StunState(442388) |
| 5 | DEAD | 死亡 | DeadState(442239) |
| 6 | BORN | 出生 | BornState(442076) |
| 7 | REACH_EXIT | 进蓝门扣血后消失 | ReachExitState(442335) |
| 8 | REBORN | 复活 | RebornState(443063) |
| 9 | UNBALANCE | 失衡（击飞前摇） | UnbalanceState(442593) |
| 10 | FALLDOWN | 倒地 | FallDownState(442734) |
| 11 | DISAPPEAR | 消失 | DisappearState(442878) |
| 12 | BLINK | 闪现 | BlinkState(442995) |
| 13 | FROZEN | 冻结：不可行动 | FreezeState(442451) |
| 14 | LEVITATE | 浮空：不可行动，高度提升 | LevitateState(442516) |
| 15 | DIALOG | 剧情 | - |
| 16 | PALSY | 麻痹（停顿型） | PalsyState(442412) |
| -1 | TERMINAL | 终结 | - |

## 5. 两侧逻辑复用

- 攻击、技能、天赋全部是 `Ability`（FamilyGroup：ATTACK/COMBAT/SKILL/TALENT/
  GENERAL，dump.cs:367418），走同一施放管线（03 文档 §2.4）。
- 我方干员（character/04 文档）同构，状态枚举略异（IDLE/SKILL/DOZE…）。

## 6. 阅读顺序

01/02（数据）-> 03（技能系统）-> 05（移动系统）-> 04（攻击/战斗时序）->
06（异常/受控）-> 07（判定逻辑）-> 08（模拟器规格落地）。
