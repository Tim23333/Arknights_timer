# 04 我方判定逻辑（索敌 / 攻击 / SP / 技能 / 阻挡）

> 依据 `Ark_data/dump.cs`（Il2CppDumper 空壳，字段/枚举/签名可确认，方法体不可见）。
> 结论分级【确认】/【推断】。

## 1. 我方状态机（Character.States.State，dump.cs:439537）

`DEFAULT=0, IDLE=1, ATTACK=2, COMBAT=3, SKILL=4, STUN=5, DEAD=6, BORN=7,
DISAPPEAR=8, FROZEN=9, REBORN=10, DYING=11, DIALOG=12, DOZE=13, TERMINAL=-1`。

状态类（dump.cs:439592-440262）：
- `IdleState`（439637）：待机；
- `AttackState`（439825）：远程/射程内普攻循环，关键私有方法
  `_NextAttackOrExit` / `_StartAttack(firstAttack)` / `_GetTarget` /
  `_CheckSwitchToCombat`；
- `CombatState`（439657）：被阻挡/近战，`_NextCombatOrExit` / `_StartAttack` /
  `_GetTarget`（取阻挡者 Enemy）；
- `SkillState`（439888）：施放技能，`_StartSkill` / `_DoStartSkill`，
  结束后按 `m_remainingEscapeTime` 退出；
- `StunState`（439921）/ `FreezeState`（440030）/ `DozeState`（439965）/
  `RebornState`（440116）：受控/复活。

## 2. 索敌与攻击

- 远程干员在 `AttackState` 中 `_GetTarget()` 索敌（射程内敌方优先），
  索敌范围由 `rangeId` 引用（character phases[].rangeId / skills[].rangeId）。
- 近战干员进入 `CombatState`：目标取“当前阻挡的敌人”（`BlockedEnemyManager`，
  dump.cs:440291；`Character.BlockRadiusManager`，440349），`_CheckSwitchToCombat`
  在攻击状态检测是否有可阻挡目标。
- 普攻节奏：`baseAttackTime`（秒，如 1.6）决定攻击周期，`attackSpeed`
  （100 基准，倍率）修正；每帧 `OnTick(FP deltaTime)`（30 tick/s 逻辑帧）
  推进冷却并在到点时 `_StartAttack`。
- 普攻/技能同为 `Ability` 管线（FamilyGroup ATTACK/SKILL），
  结束回调 `(ability, FinishReason, resetCd)` 驱动“打完下一刀或退出攻击状态”。

## 3. SP 与技能释放

- SP 由 `SpController` 管理，规则见 02 文档 §2（spType/spCost/initSp/increment）。
- `skillType=AUTO`：SP 满后自动释放（`BasicSkill.IsAutoSkillTriggerable`，
  dump.cs:421083）；
- `skillType=MANUAL`：需玩家操作（模拟器可视为由调度器触发）；
- 技能施放进入 `SkillState`，期间普攻暂停；技能结束回 IDLE/COMBAT/ATTACK。
- 受控状态（STUN/FROZEN/DOZE）期间 SP 不增长、无法攻击/施法（与敌方对称）。

## 4. 阻挡

- `blockCnt`（阻挡数）来自 AttributesData；被阻挡敌人列表由
  `Character.BlockedEnemyManager` 维护。
- `Character.BlockRadiusManager`（dump.cs:440349）管理阻挡半径；
  `Enemy._CheckBlockable`（dump.cs:441462）按 motionMode/weight/volume 判定
  （详见敌方 05 文档 §4）。

## 5. 与敌方模拟器的复用

- 帧驱动、Ability 施放、FinishReason 打断、异常状态对行动的影响均与敌方共用
  `Unit`/`Entity` 基类逻辑，模拟器可一套骨架跑两侧；
- 差异点：我方无移动状态机（部署后固定站位，仅技能位移类改变位置）、
  无蓝门/生命扣除、索敌规则以 rangeId 范围表为准。

## 6. 不确定点

- `_GetTarget` 的具体索敌排序（距离/阻挡/优先级）方法体不可见，标注【推断】；
- rangeId -> 具体格子集合需解析范围表（`range_table` 未在当前 data/tables 中，
  可用游戏内实测或社区数据补齐）。
