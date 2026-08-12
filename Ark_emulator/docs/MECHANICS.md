# 明日方舟底层机制参考（用于模拟器实现）

> 来源：PRTS wiki（m.prts.wiki）相关条目 + 本地解包数据/文档
> （ark_parser/enemy 00-11） + dump.cs。置信度：【确】=官方/wiki 明确；
> 【推】=由代码签名/数据推断；【TODO】=待实测/待补。

## 1. 帧与时间

- 逻辑帧率固定 30 tick/s（`TIME_ROUGH_LOGIC_RATE=30`，dump.cs:441464）。
- 所有数值以帧为最小单位推进；攻速/移速等换算成帧后再积分。

## 2. 伤害计算【确】

### 2.1 基础公式

| 类型 | 公式 |
|---|---|
| 物理 | `max(atk_eff - def_eff, 0.05 * atk_eff)`（5% 保底） |
| 法术 | `max(atk_eff * max(0, 1 - mres/100), 0.05 * atk_eff)`（5% 保底），法抗上限 100 |
| 真实 | `atk_eff` |
| 元素 | 见 §7 |

### 2.2 数值叠加分层（伤害计算页）

```
面板(来源侧): 直接加算 -> 直接乘算(百分比相加) -> 最终加算 -> 最终乘算(连乘)
敌方属性(目标侧): 直接加算 -> 直接乘算 -> 最终加算 -> 最终乘算
之后: 伤害乘算(百分比相加) -> 伤害重写 -> 屏障/护盾/闪避 -> 结算
```
例：“攻击力+180%”=直接乘算 1+1.8；“攻击时攻击力提高至380%”=最终乘算 ×3.8；
“鼓舞”=最终加算；“攻击力-40%”目标侧最终乘算 ×0.6。

### 2.3 伤害流程钩子（ON_* 事件）

1 ON_CALCULATE_DAMAGE（来源：攻击倍率调整）
2 检查 modifier 是否 cancel
3 ON_BEFORE_APPLYING_MODIFIER（目标）
4 ON_OUTPUT_MODIFIER（来源：治疗倍率调整）
5 伤害则 ON_OUTPUT_DAMAGE（来源：伤害倍率调整）
6 ON_APPLYING_MODIFIER（目标：受治疗倍率调整）
7 On_Take_Damage/On_Take_Heal（取消隐匿/无敌下攻击、禁疗、反伤、闪避、抵挡、护盾）
8 ON_APPLIED_MODIFIER（目标）
9 伤害则 ON_AFTER_OUTPUT_DAMAGE（来源：命中触发判定）

### 2.4 取整

- 就近取整采用“四舍六入五成双”（banker's rounding，dump 内部 FP 处理）。
- 红字=暴击显示：最终伤害 ≥ 1.5×期望伤害 时显示（期望伤害不算贯穿/后置增益）。

## 3. 攻击间隔与攻速【确】

- 基础攻速 100；实际攻击间隔 = `baseAttackTime × 100 / clamp(attackSpeed, 20, 600)`。
- 攻速属性下限 20（倍率上限 5 倍间隔）、上限 600（1/6 间隔）。
- 攻击流程：抬手（前摇锁定目标）→ 生效帧 → 收尾；攻速压缩的是“攻击后读秒”。
- 近战/远程：攻击属性数据里 2bit（00 无 / 01 近战 / 10 远程 / 11 近+远）。

## 4. SP 与技能【确】

### 4.1 干员【已实现 2026-08-06】

**spType（位掩码，dump.cs Torappu.SpType）**
- 0=NONE（不回复）/ 1=自动回复 / 2=攻击回复 / 4=受击回复 /
  6=攻击或受击 / 7=全部。
- 数据中另有大量 `spType=8`：对应旧版 `SpTypeIndex.NEVER_USE`，即
  「部署后触发、无技力」技能（斯卡蒂 S2 跃浪击、砾 S1 影袭、红 S1 处决模式、
  傀影 S1 等），`spData` 无 spCost/initSp/increment、skillType 为空；
  部署瞬间自动释放效果，不参与 SP。

**自动回复（冷却槽模型）**
- 底层是隐藏「技力冷却槽」：槽长 = 1/increment 秒（increment 通常 1.0），
  槽走满补 1 点 SP 并重置；SP 最小单位为 1，无小数（不用连续积分）。
- 阻回（技能持续期间）/ 满 SP / SP_RECOVER_STOPPED(flag 1) 时计时暂停，
  剩余时间保留；条件解除后从剩余时间继续。
- 自然回复速度修正（spRecoveryPerSec）实际是修改槽长。

**攻击回复 / 受击回复**
- 攻击回复：每次攻击生效帧 +1；连击每一段都 +1，但近卫-剑豪分支
  （subProfessionId == "sword"，陈/柏喙/艾丽妮等）天生二连只 +1（PRTS 例外）。
- 受击回复：每次被攻击 +1；标了 no_hit_recovery 的伤害不触发
  （`battle.apply_damage(..., no_hit_recovery=True)`）。
- 位掩码判定：`s.sp_type & mode` 非 0 即回复，6/7 组合技能均生效。

**释放与阻回**
- 手动/自动技能触发时扣除 spCost；active 期间「阻回」：自动、攻击、受击
  全部停止；技能结束（时长到 / 弹药耗尽）后恢复，冷却槽剩余时间保留。
- 初始技力按已选技能 initSp 在部署时预充（模拟器暂以各可选技能 initSp 的
  最小值预充，未建模「装备第几号技能」，见文末 TODO）。

**可充能与弹药**
- 可充能：SP 上限 = spCost × maxChargeTime；自动触发技能满第一层即释放
  （如炎爆 maxChargeTime=2，sp>=9 就开火），手动技能可攒满多层。
- 弹药（durationType=1，SkillDurationType.AMMO）：无持续时间，激活时按
  黑板上 cnt/ammo 装载弹药；每次普攻消耗 1 发，耗尽即结束技能并退出阻回。
- 蓄力 = 满充释放额外效果（等价于可充能 2 次，暂未单独建模）。

### 4.2 敌人【确】
- 敌人技能按**冷却 CD** 触发：所有技能各自走 CD+判定；初始 CD 决定首次释放。
- 多个技能同时就绪：按**优先级**（priority）释放；同优先级随机。
- 敌人 spData 非空时走 SP 条（“蓝条”），如弹药=每次消耗 1 SP。
- 敌人技能大多不是普攻，不受战栗/麻痹对普攻的限制。

## 5. 索敌与仇恨【确】

### 5.1 优先级
阻挡 → 特殊优先级（干员/技能自带索敌）→ 第二优先级 → 仇恨值 → 最早出现。
- 被阻挡的敌人强制攻击阻挡者（无视可选性/隐匿/无敌）。
- 近战干员优先攻击自己阻挡的敌人；远程干员不因阻挡而优先。

### 5.2 仇恨值公式
- 敌人类目标：`1000 × 嘲讽等级 - 路径距离`（路径距离=到终点寻路曼哈顿距离
  串联+前进方向投影修正；不可达则直线距离）。
- 角色类目标：`10000000 × 嘲讽等级 + clamp(创建时间,0,10000)×1000 + 同帧部署数×1`。
- 创建时间=战斗开始起的秒数（上限 10000）；同帧部署数每帧更新。

### 5.3 仇恨过滤器（postFilter）
79 个过滤器（ID 0-78），常见：
- 4 仇恨降序（默认单攻/技能）；0 ALL（群攻不排序）；
- 1 终点距离升序；2/3 生命比例升序（治疗）；8/9 防御降/升序（神射手）；
- 14 随机；15/16 生命值降/升序；17/18 攻击力降/升序；27/28 重量降/升序；
- 42 阻挡数降序；76 与自身寻路距离升序。
双权排序：第一参考值同才比第二参考值；比对精度默认 0.001（4/76 号为 0.1）。

### 5.4 索敌刷新间隔（SEARCH_TARGET_TICK，dump.cs）【确+已实现】
- `SelectorTrigger.SEARCH_TARGET_TICK = 3`（dump.cs:437169）：攻击/技能的目标
  选择器每 3 个逻辑 tick（30Hz 粗逻辑下 = 0.1s）最多重跑一次；期间保留上一个
  仍然有效的目标（`_keepTarget` / `m_lastTarget`），新的更高优先级目标要等
  下一个搜索边界才会被采纳。`Search(force)` 立即重搜（技能施放/目标失效/阻挡
  切换等强制路径）。
- `_overrideSearchTargetTick`（prefab 数据，>=0 时覆盖周期）与
  `CompoundPeriodicTicker`（传统 + 确定性双 ticker，m_nextReadyFrame 计数）。
- `TileTrigger.SEARCH_TARGET_TICK = 5`（dump.cs:437439）：地块类选择器。
- 模拟器实现：`targeting.search_gate`（通用）+ `HateSystem.operator_attack_target`
  （干员/医疗普攻索敌）+ 敌方普攻 `_start_normal_attack` + 敌方技能
  `EnemySkillController._find_target`（技能目标选择同样进门：窗口内保留缓存
  目标，缓存目标失效/出范围时立即 force 重搜）；单位可设 `_search_period`
  覆盖周期。阻挡快路径不进门（阻挡切换即时生效）；TileTrigger=5 已建模为
  常量，模拟器内地块选择技能为一次性/数据驱动，无周期性地块重搜可接。

### 5.5 主线 15 章 PRTS 调度（Mainline15PrtsManager）【推+已实现】

- 数据源（dump.cs:10402 / 402606-402612）：15-18 关由 PRTS 敌人
  （enemy_1564_mpprts）执行脚本队列，Boss（enemy_1565_mpprme）与其高地
  卫兵（enemy_10072_mpprhd 等）通过 buff 模板插入动作：
  - `Main15InsertPrtsAction`：按 priority 插入队列；地块选择按
    `_chooseMostCharSurroud` / `_chooseMostEnemySurroud` /
    `_chooseSource`；刷怪 key 按地形高度选 Fly/Highland/Lowland。
  - `Main15TryNextPrtsAction`：推进子动作管线（force 立即跳过）。
  - `Main15SkipPrtsAction` / `Main15FilterPrtsLastSubAction`（含
    `_filterActionInstead` 取反）/ `Main15CreateBuffToPrts` /
    `Main15ForceSetBattleSpeedLevel`。
- 动作类型：MOVE_AND_SPAWNENEMY / MOVE_AND_CREATEBUFF /
  MOVE_AND_DRAG_SOURCE；子动作：MOVE_TO_ORIGIN / MOVE_TO_DRAG / DRAG /
  SPAWN / MOVE_TO_CREATE_BUFF / CREATE_BUFF / FOLLOW_BOSS。
  子动作序列为【推】：
  - 刷怪：MOVE_TO_DRAG -> SPAWN -> FOLLOW_BOSS
  - 拖拽：MOVE_TO_DRAG -> DRAG（到达施放 arrive buff）-> FOLLOW_BOSS
  - 造 buff：MOVE_TO_CREATE_BUFF -> CREATE_BUFF -> FOLLOW_BOSS
- 模拟器：`ark_emulator/prts.py`（优先级堆 + deque 子动作管线 +
  `_trace_pos` 移动 + 拖拽跟随 + spawn_enemy_directive 刷怪 +
  materialise_buff 施加）；battle 每 tick 驱动、快照含 `prts` 字段。
- 挂载：15 章敌人基础 prefab 上 `_attachPassiveBuffsOnDummy` 组件携带
  的 Main15* 模板 buff（enemy_mpprhd_passive / enemy_mpprme_spawn_mark
  等）在 spawn 时挂到敌人身上（按 key 去重，仅含 Main15* 节点才挂）。
- 配置（env_v060_mainline15_prtsCtrl，解自 [uc]envsystems AB）：
  `_prtsEnemyKey`（mpprhd，PRTS 驱动敌人）、`_prtsSpawnCheckDistance`、
  动作结束/失败 buff、8 组高低地刷怪键对（tileHeightType → enemyKey +
  trap）。fly/highland/lowland 占位键按目标瓦片高度从键对解析（优先匹配
  瓦片预部署陷阱）；无配置时按黑板上解析，失败发 prts_spawn_failed。

### 5.6 Act35Side 宝石机制（env_017_act35side）【推+已实现】

- 数据源（dump.cs:10261 / 394988）：Clear/Polluted 宝石为静止敌人
  （enemy_10009_sggem）占据瓦片；主线 15-18 守卫（enemy_10077_mpbarr_2）
  复用该活动模板（enemy_sgbird/sgbtle/sgrich[spawn] 等）。
- 节点：Act35SideSummonGems / SummonGemsInRange（rangeId 或圆形半径）/
  SummonGemsInFourDirections / SummonLinkGem / CheckIfOnGemsTile
  （_checkNotOn 取反、_excludeLinkGems 排除连接宝石）/
  CheckNotOnExcludedTile / AssignGemsCountToBlackboard /
  EliminateGems（沿方向直线消除）。
- 模拟器：`ark_emulator/act35.py` Act35GemsManager——合法瓦片召唤宝石
  敌人 + 类型 buff、维护宝石地图、按需查询/消除；快照含 `act35` 字段。
- 深度区域消除（连通区 match-3、伤害传递）由宝石 buff 模板事件处理，
  管理器实现核心；召唤后宝石不移动（move_speed=0）。

### 5.7 Act31Side 污染区（level_hard_13-04 狄恩杰）【推+已实现】

- 数据源（dump.cs:13363-13369）：13-04 hard 狄恩杰 boss 的水/污染机制。
  - Act31SideAddAreaPollute / DeathPolluteTile：半径范围加污，数值取
    源单位黑板上 value/value_eff（节点 _addPolluteV 为 0 时）。
  - Act31SidePurifyAreaPollute：连通污染区（4 向 flood-fill）净化。
  - CheckInPolluteArea / CheckTileInWaterArea / CheckRootTilePolluteValue
    （GE/GT/LE/LT/EQ，可带区域最大值）：门控。
  - AssignAreaPolluteValueToBB / TriggerRebuildAreas / PumpFlowIntoOtherArea
    / CheckPumpBackTileValid。
- 模拟器：`ark_emulator/act31.py` 每瓦片污染值地图 + 连通区净化；快照含
  `act31` 字段。水位连通/泵流为【推】近似（污染瓦片即水域），深度水流动
  画后续可按需细化。
- ModifyEnemyGraphicScale（Special/Graphic）：写入敌人 `_graphic_scale`
  （复活缩小等表现）。

### 5.8 其余通用节点补全（bundle 零未实现）

- `ApplyFixedElementDamage`：bb[值键] × bb[倍率键]（可空）施加元素损伤
  （SANITY/WATER/FIRE/DARK → EP 积累）；真实用于纯燚 S2、敌人灼烧
  （enemy_fthlgj[burn]）、水蚀（enemy_muston_ep）等。
- `CheckBuffAttributeModifierChanged`：转换器门控——源属性相对上次缓存值
  变化时同步 buff 的 FINAL_ADDITION 修饰并返回 True（atk_to_atk /
  def_to_def / hp_to_hp[final_addition] 系列）。
- `LegionModeOnlyAssignCardCntToBB`：乐土手牌（_legion_hand）中匹配
  _cardId 的卡数写入 bb[_cardKey]。

### 5.9 活动模式节点族（WDSLM / 沙盒 / DurBus）【已实现】

- WDSLM 站台（dump.cs:14118-14127，水世界观众台）：
  - `RegisterAsStand`：按 useIdToFindHost + hostId（enemy_1542_wdslm）
    找宿主，把源注册进 battle._wdslm_stands[ability]。
  - `RunActionsToWdslmAbilityTarget`：按 _actionTargetType（HOST /
    STANDS / STANDS_EXCEPT_SELF / SELF_WITH_HOST_AS_SOURCE）解析目标集，
    BUFF_OWNER 保持原宿主、每个站台作为 TARGET 执行 _actionsToTarget。
  - `EqualizeTargetHpRatio`：目标 HP 比例对齐源（_useSourceHpRatio）或
    固定 _hpRatio。
- 沙盒：SandboxMarkEntityNotReward（_sandbox_not_reward 标记）、
  SandboxShowToast（事件）、SandboxEnableTraceTarget /
  SandboxSetEnemyTraceTarget / SandboxCheckEnemyCanTraceTarget /
  SandboxMarkTraceReached（复用 _trace_target/_trace_pos 基础设施）、
  SandboxIsRushEnemyMode / SandboxIsRushEnemy / DisableClickCharacterInfo。
- DurBus：battle._durbus_passengers[ability] 乘客注册表；
  CheckPassengers / ReleasePassenger / KillPassengers。

## 6. 阻挡【确+推】

- 干员有阻挡数（blockCnt）；敌人占用阻挡数（默认 1，欺凌者/倾轧者占 3，
  部分敌人要求阻挡数≥N 才能被挡）。
- 敌方“重量等级”（massLevel）用于位移技能/推拉判定；力量等级
  （baseForceLevel）决定推动力度（TODO：精确对照表）。
- 被阻挡后敌人进入 COMBAT 近战循环；阻挡解除后回 MOVE/ATTACK。
- 空降阻挡在入场动画期间即视为阻挡中。

## 7. 元素损伤【确】

- 4 种：神经(SANITY)/侵蚀(WATER)/灼燃(FIRE)/凋亡(DARK)（+狂躁 ANGER）。
- EP 上限默认 1000；领袖级敌人 +1000（=2000）。
- 元素伤害=损伤值 × (1 - 损伤抵抗×0.01)；元素值扣除到 0 触发爆发。
- 爆发：立刻给效果 + 进入爆发冷却（期间所有元素值锁定/不可回复），
  结束时全部元素值恢复满。
- 爆发效果（我方/其他单位，2026-04 后敌人统一用敌方效果）：
  - 神经：我方=10s 眩晕+1000 真伤；敌方=3 层麻痹+6000 元素伤。
  - 侵蚀：我方=-100 防永久可叠+800 物伤；敌方=8s 内-120 防永久可叠+5000 元素伤。
  - 灼燃：法抗-20，我方 1200 法伤 / 敌方 7000 元素伤。
  - 凋亡：我方=15s 阻回+静默每秒-1 SP+100 法伤；敌方=15s 50% 虚弱每秒 800 元素伤。
- 爆发冷却时长=该元素爆发持续时间：神经 10s / 侵蚀我方 10s·敌方 8s / 灼燃 10s /
  凋亡 15s（敌我统一 30s 的旧近似已修正）。
- 敌方爆发的“元素普通伤害”（6000/5000/7000/800×15s）施加在已进入爆发的
  自身元素条上，爆发冷却中所有元素值锁定 → 实际无效果（游戏同款行为）。
- 当前损伤元素=元素值最低者（索敌/显示用）；实际爆发元素=首个施加到爆的元素。

## 8. Buff 叠加规则【确】

- 属性 Buff 分四层（§2.2）：直接加算/直接乘算/最终加算/最终乘算。
- 同名 Buff 默认不叠加（刷新），可配置叠加策略。
- 光环类 Buff：进入范围加、离开范围/技能结束/退场清除。
- 异常状态（眩晕/冻结/浮空/麻痹/沉睡/停顿/束缚/沉默/缴械…）见
  ark_parser/enemy/06 文档；施加前检查免疫位。

## 9. 移动【确】

- 移动速度单位=格/秒（moveSpeed 1.0=1 格/秒）。
- 路线=检查点列表；BasicCursor 逐检查点推进；到达判定距离 0.05。
- 每 5 tick 刷新所在格（UPDATE_POS_TICK=5）；寻路用 SPFA 按 motionMode 分桶。
- 飞行/地面用 MotionMode/MotionMask；通行由 TileData.passableMask 与
  MapData.Edge.blockMask 决定。

## 10. 部署与费用【确+推】（2026-08-06 费用计时器已精确化）

- 部署费用：关卡 options initialCost/maxCost；费用随时间回复，底层是
  `PrecisePeriodicTimer`（dump.cs:1409）：周期 = costIncreaseTime（默认 1s，
  全量关卡分布 0.8/1/2/3/4/5/5.5/10/999+；999+ = 无自然回复），
  周期走满 +1 并保留精确余量（FP 定点，无浮点漂移；30 tick 恰为 1 点）。
- 费用满/锁定时计时暂停并保留剩余时间；花费后从剩余时间继续。
- 负费用：`NEGATIVE_COST_RECOVERY_MULTIPLIER=0.5`（GlobalConsts）→
  自然回复速度减半（等效周期 x2）。
- 费用计时器修饰符（Buff/Rune）：`AddCostTimerModifier(mulValue, source,
  priority, costAddLocked)` / `RemoveCostTimerModifier(source)` /
  `ModifyCostIncreaseTime(mul)` / `SetCostIncreaseTime(value)`
  （BattleCostManager，dump.cs:9935）；多个修饰符相乘（组合语义【推断】）。
- 费用锁定：`LockCostIncreasement(isLock, reason)`，CostLockReason：
  1=DIALOG_SHOW / 2=AUTOCHESS_REST / 3=SANDBOX_V3_WAIT_BASE。
- 快照新增 `costTimer{period, progress, nextCostIn, locked}` 供 AI/UI 使用。
- 再部署时间=干员属性 respawnTime（秒）；撤退/死亡后按此计时。
- 部署限制：characterLimit（可部署数）、tilesDisallowToLocate、buildableType
  （地面=1/高台=2）匹配干员 position。
- 部署时播放入场动画期间“不可选中”（阻挡优先可强制攻击）。

## 11. 波次与敌人生成【确（本地数据）+ 2026-08-06 修正】

- **运行时波次加载（已修正）**：wave i 的所有 fragment 动作队列排空后，调度器
  进入本波清场等待；只有 `managedByScheduler=true` 且 `dontBlockWave=false` 的
  敌人全部死亡/进蓝门/被 `ReleaseEnemyFromCurrentWave` 释放，才执行 postDelay，
  再加载 wave i+1 并等待其 preDelay。`maxTimeWaitingForNextWave>0` 时清场等待
  受该秒数上限约束；-1 表示无上限。静态 `build_wave_timeline` 只提供“不计清场
  等待”的最早时间预览，实际战斗使用 `RuntimeWaveScheduler` 动态推进。
- **波内 fragment 顺序执行（已校准）**：`Scheduler._DealWave` 逐个 yield
  `_DealFragment`；后者先等待 fragment.preDelay，再构造动作队列并 yield
  `ExecuteActionQueue`，动作队列排空后才返回并开始下一个 fragment。action 在
  `fragment_start + action.preDelay + i*interval` 生成 count 个敌人
  （i=0..count-1），routeIndex 指定路线。此前将全部 fragment.preDelay 错当成
  相对波开始，导致 main_05-10 第 5 个 fragment 的浮士德在 t=11 提前生成；
  按当前 GameAssembly.dll 原生调度器校准后为 t=114。
- **同帧生成顺序（"不存在同时出现"）**：同一 tick 内按
  `(t, wave, fragment, action, seq)` 确定性顺序逐个创建（seq 为 count 内
  序号）；spawn 事件在 waves 阶段最先处理，早于敌人/干员行动。
- `blockFragment` 阻塞的是异步 action executor 的完成回调，不是等待生成的敌人死亡；
  当前模拟器动作 executor 均同步完成，所以动作队列排空即可进入下一 fragment。
- enemyDbRefs{id, level, useDb} 决定实际敌人数值（enemy_database 按等级覆盖）；
  敌人死亡/进蓝门扣生命值（lifePointReduce；蓝门=1）。

## 12. 待实测/待补清单（TODO）

- ~~物理/法术伤害 5% 保底是否同时作用于法术~~（2026-08-08 确认：法术同样有
  5% 保底，法抗 100 仍打 5% 抛光伤害，见 §2.1）。
- ~~力量/重量推动的精确对照表~~（2026-08-06 已实现，见文末「推与拉」节；
  baseForceLevel 现网数据无人设置，角色类单位本身免疫位移）。
- ~~敌人技能生效帧相对 preDelay 的偏移~~（2026-08-08 已按 prefab
  `_waitForAttackEvent` 标定：wait=0 在 preDelay 当帧生效，wait=1
  在 preDelay + OnAttack 帧生效，见「敌方技能时序」节）。

## 2026-08-06 敌方攻击距离 / 索敌范围修复【确】

- `enemy_database` 的 `rangeRadius`：590 条敌方数据中 `-1.0` 表示无普攻，
  其余为 0.8~99 的实际攻击距离；已接入 `attributes.rangeRadius`，在
  `battle.spawn_enemy` / `spawn_enemy_directive` 写入属性，
  `consts.resolve_attack_range` 换算；None/0/非法时回退 1.5。
- 索敌行为：攻击距离 <= 1.5 按近战（COMBAT/阻挡环）索敌，> 1.5 按远程索敌。
- `viewRadius`（视野半径）已写入 attributes，AI 索敌使用。
- 敌方技能范围：prefab 的 `_rangeId`（含 selector）约 86 个取值
  （`x-1/x-4/x-5/0-1` 等）；2406 条组件数据中 AOE 类技能通过 blackboard
  `range_radius` 决定半径。

## 2026-08-06 敌方 prefab buff 归属【确（dump.cs）】

- `BuffToOwnerDuringAbility`：prefab 上带 `_forceFinishBuffOnCastEnd` /
  `_startEvent` / `_endEvent`（dump.cs:13226），`_buffs` 为技能释放期间
  对施法者的 buff 列表；例 `enemy_trspsb_eating` 等。
- `_passiveBuffs` / `_passiveBuffsToOwner`：光环/常驻 buff。
- `_filterBuffSource`：按来源过滤目标 buff（216 条 buff 数据）。
- `_activeBuffs` / `_additiveActiveBuffs` 与 Ability 的 `_buffs` 共同决定
  技能 buff 的施加；快照中技能状态含 `selfBuffs` / `targetBuffs`。

## 2026-08-06 伤害类型 / 元素类型 / buff 异常位【确（dump.cs）】

- DamageType 游戏值：prefab `_damageType` NONE=0 PHYSICAL=1 MAGICAL=2
  PURE=3 HEAL=4 ELEMENT=5（dump.cs:366766）；模拟器内部
  PHYSICAL=0 MAGICAL=1 TRUE=2 ELEMENT=3，`translate_game_damage_type`
  映射 1->0、2->1、3->2、5->3。
- ElementType：prefab `_elementDamageType` + blackboard
  `ep_damage_ratio[trigger]`；SANITY=1..DARK=4（dump.cs:366797）；
  模拟器 EP 下标 0=神经 1=侵蚀 2=灼燃 3=凋亡。
- buff 异常位：559 条 buff 带 `abnormalFlags`（INVINCIBLE/STUNNED/
  INVISIBLE...），经 `int()` 解析后按 `_flag_id` 对应设置异常位，
  施加 buff 即挂对应异常状态。
- 敌方技能参数：11 个敌方技能（xdagt/skzamy/xb2bullb 等）中 7 个把
  priority/spCost/cooldown 放进了 blackboard；`DeepBreathS4.spCost ==
  'startCol'` 是坏数据，按 0 处理。

## 2026-08-06 攻击时序（我方/敌方通用）【确（Spine + 实测）】

- 近战/远程攻击都走 `_pending_attack` 前摇：生效帧取自 Spine OnAttack，
  `frames = interval * hit_frame_ratio * 30`；
  hit_frame_ratio = OnAttack 帧/动作总帧（普攻约 0.5，部分 0.65）。
- 攻击循环 = 抬手（锁定目标）→ 生效帧（结算）→ 收尾，攻速压缩收尾段。
- 快照暴露 `pendingAttack`（target/remaining/ranged），AI 可据此决策。

## 2026-08-06 敌方技能时序【确（prefab + Spine）】

- 生效帧由 prefab `EasyToStartAbility._waitForAttackEvent` 决定
  （2026-08-08 已按 prefab 标定）：
  - `waitForAttackEvent=1`（413/711 技能）：效果在 preDelay 结束后的
    校准 OnAttack 帧执行（`preDelay + hit_times[i]*30` 帧，多段技能
    每段一次），如浮士德 CriticalHit 40 帧 / SummonBallis 27 帧；
  - `waitForAttackEvent=0`（150/711 技能）：效果在 preDelay 结束
    当帧执行，不再等 OnAttack 帧（修复前会多等 0.4~3.8s），如
    霜星 ArcticBlast 0.933s、W 的 C4 0.6s 发射弹道；
  - 缺失字段（提取未覆盖）保持 OnAttack 驱动（默认 wait=1）；
    wait 判定优先取按敌人的 skill_behavior_catalog 条目（共享
    prefab 合并值可能被其它敌人污染，如 Lasso 合并后为 0、行为
    目录为 1）。
- spell_on（action node + 自身 buff + 目标效果）统一在生效帧触发：
  wait=1 时在首个校准 OnAttack 帧，wait=0 时在 preDelay 结束当帧；
  生效时刻取 `max(preDelay, OnAttack)`（Lasso preDelay=OnAttack=0.4s
  时在 0.4s 生效而非 0.8s）。
- AbilityRun 施放 spell 后由 Spine OnAttack 驱动命中结算：
  `hit_wait = max(0, hit_times[0] - preDelay) * 30` 帧，到达 OnAttack
  帧时执行 spell_on 与 `_execute_effects`（多段技能每段各结算一次，
  spell_on 仅首次）。
- 自身 buff：wait=1 时随首个命中帧施加（BuffToOwnerDuringAbility 的
  spell_on 语义），wait=0 时在 preDelay 结束施加。
- 黑板解析补 valueStr：字符串参数（如 SummonBallis 的 branch_id
  faust_ballis）不再丢失，分支激活正确按 27 帧命中结算。

## 2026-08-06 干员攻击帧 + 攻击回复 SP【确】

- `_operator_attack` 建立前摇（远程发弹道、近战延迟结算），
  `_resolve_operator_attack` 在 Spine OnAttack 生效帧结算：
  `frames = interval * hit_frame_ratio * 30`；
  OnAttack/总帧比：scave 等 0.5（1.05s 间隔约 16 帧）。
- 攻击回复 SP 挂在生效帧：连击每段 +1，剑豪二连仅 +1；
  on-attack 效果（attack@*）同帧触发。
- Token 攻击同样走 `pendingAttack` 前摇；部署后触发技能（spType=8）
  在部署瞬间释放。

## 2026-08-06 推与拉：力度/重量精确映射【确（PRTS + dump.cs 签名）】

### 受力等级
- `受力等级 = 力度等级(force) - 重量等级(massLevel)`；massLevel 缺省 0
  （与游戏一致：猎狗等无 massLevel 字段的敌人 PRTS 实测重量 0）。
- 数据实测力度值：`force` 1.0x242 / 2.0x55 / 3.0x6；`attack@force` 1.0x91；
  `talent@force` 6.0；捕网 `sktok_archook` 11.0。
- `BattleFormula.CalculatePushForce(int pushForceLevel, int massLevel,
  Vector2Int pushForceRange, out int pushForceIndex)` / `CalculatePullForce`
  与 PRTS 表格一致。

### 推力（PUSH_FORCE_TABLE）
| 受力等级 | 列表值 | 受力N/初速度 | 弹道距离 | 特效距离 |
|---|---|---|---|---|
| <=-3 | 0 | 0 | 0 | 0 |
| -2 | 100 | 1.0 | 0.11825 | 0.08492 |
| -1 | 200 | 2.0 | 0.4403 | 0.37363 |
| 0 | 400 | 4.0 | 1.6958 | 1.56247 |
| 1 | 450 | 4.5 | 2.13705 | 1.98705 |
| 2 | 530 | 5.3 | 2.95013 | 2.77347 |
| >=3 | 580 | 5.8 | 3.52392 | 3.33058 |

- 作用瞬间：目标获得动量 = 实际受力x1s（初速度=受力N），随后匀减速滑行
  （摩擦 u=0.5、g=9.81，失衡速度 <=0.1 退出）；滑行时长 `2x距离/初速度`。
- 弹道类（温蒂 2/3、阿消 1/2）比特效类（食铁兽 2、见行者）多 1 帧初速度
  滑行，距离略远；分类受 [uc]skills 缺 GameObject 归属限制，目前用白名单
  + 远程普攻启发式（`_force_kind`）。
- 方向性修正：沿部署方向为方向力；目标-干员连线夹角 >45 度或距离 <0.25 格
  时修正为径向力且受力等级 -2（见行者/莱伊可干预，未建模）。

### 拉力（PULL_FORCE_TABLE）
| 受力等级 | 列表值 | 受力N | 拖拽时间 | d=2 | d=3 |
|---|---|---|---|---|---|
| <=-3 | 0 | 0 | 0.5s | 0 | 0 |
| -2 | 2 | 2 | 0.5s | 0.0320 | 0.0325 |
| -1 | 10 | 10 | 1s | 0.5699 | 0.9240 |
| 0 | 40 | 40 | 1s | 拉至身前 | 拉至身前 |
| 1 | 42 | 42 | 1s | 拉至身前 | 拉至身前 |
| 2 | 44 | 44 | 1s | 拉至身前 | 拉至身前 |
| >=3 | 46 | 46 | 1s | 拉至身前 | 拉至身前 |

- 拉力起点：干员前方 0.5 格（大部分技能）；拖拽期间
  `F_t = F0x(x_t/x0)^4` 逐帧变化，进入拖拽者中心 0.6708 半径急停。
- 受力等级 <0 时按 d=2/d=3 参考值插值；角色撤退/弹道消失则拉力解除（未建模）。

### 实现落点
- `consts.py`：`PUSH/PULL_FORCE_TABLE`、`force_level_from`、`push_displacement`
  /`push_duration`、`pull_duration/pull_pulled_home/pull_displacement`。
- `battle.displace(..., duration, kind, force_level)`：匀减速滑行
  （`v = 2xremaining/t_remaining`），停止点精确等于表格距离。
- `entities.update_displacement`：匀减速推进 + 撞墙/落穴判定；快照新增
  `displacement`（dr/dc/remaining/total/时长/kind/forceLevel/dest/source）。
- `operator_skills._displace`：方向修正 + 受力等级 + 推拉表；弹道白名单
  `PROJECTILE_FORCE_SKILLS`（阿消 1/2、温蒂 2/3）。
- 敌方 prefab 黑板上无 force 键；角色类单位免疫位移，故敌方侧推力未实现。

## 2026-08-06 SP 精确模型【已实现（PRTS + 本地数据 + dump.cs）】

- `operator_skills.py`：spType 位掩码判定（支持 6/7）、1s 冷却槽自动回复
  （阻回/满/禁回暂停并保留剩余）、active 期间阻回、可充能
  maxSp=spCost×maxChargeTime、弹药技能（durationType=1，普攻耗 1 发、
  耗尽退出）、部署触发技能（spType=8）部署即放、剑豪攻击回复 +1 例外、
  `recover_sp` 返回实际授予量。
- `battle.py`：`apply_damage(..., no_hit_recovery=False)` 钩子；
  攻击生效帧按 active 技能 `attack@times/cnt` 计算连击段数调用
  `on_attack_landed(hits)`，并 `on_ammo_attack()` 扣弹药；
  部署时写入 `sub_profession_id` 并触发部署技能。
- 测试：`tests/test_sp_mechanics.py`（9 项，覆盖冷却槽/位掩码/阻回/充能/
  弹药/部署技能/剑豪/无法受击回复）。
- TODO：装备技能索引（initSp 取已装备技能而非最小值）；蓄力与
  maxChargeTime 触发的额外效果；「无法触发受击回复」的具体来源清单
  （元素爆发、部分装置/召唤物攻击等）；敌方侧 spType 位组合复用。

## 2026-08-06 波次时序模型修正【已实现（本地数据 + dump.cs Scheduler 字段）】

- 发现旧 stage_sim_bundle waveTimeline 的多波次关卡错误：所有波次起点都被
  叠到 t≈0（wave preDelay 相加模型），而实际游戏波次必须顺序衔接。
  例 main_08-17：旧模型 wave1 5~29s、wave2 11~39s（重叠）；正确模型
  wave1 53~77s、wave2 97~125s、wave3 128~153s。
- `ark_emulator/waves.py`：新增 `build_wave_timeline(raw_waves)`（波次与
  fragment 顺序衔接、同帧 (wave,fragment,action,seq) 排序）；
  `WaveScheduler` 对输入时间轴做同一确定性排序。
- `battle.py`：有原始 waves 时优先重建时间轴，无则回退 bundle 时间轴
  （自定义关卡不受影响）。
- `ark_parser/enemy/build_sim_bundle.py`：同步修正生成器（供未来重新生成
  bundle；当前已入库的 108MB bundle 仍是旧模型，模拟器已不依赖它）。
- 测试 `tests/test_wave_timing.py`：单波手算时间、多波顺序不重叠、同帧
  顺序确定性、模拟器端到端，以及 main_05-10 浮士德 t=114 回归断言。
- 遗留：`maxTimeWaitingForNextWave` 精确语义。

## 2026-08-06 费用回复计时器精确化【已实现（dump.cs + 本地数据）】

- 依据 dump.cs：费用用 `PrecisePeriodicTimer`（period=costIncreaseTime），
  `BattleCostManager.UpdateCost(fixedDeltaTime, side)` 每帧推进，满/锁定时
  暂停；`m_costTimerModifiers`（PriorityQueue）承载回复速度修饰符；
  `m_negativeRecoveryMultiplier`（默认 0.5）用于负费用。
- `battle.py`：新增 `cost_period()`（基期 x 修饰符乘积 x 负费用因子）、
  `modify_cost_increase_time` / `set_cost_increase_time` /
  `add_cost_timer_modifier` / `remove_cost_timer_modifier` /
  `lock_cost_increasement` / `cost_timer_state()`；tick 用 1e-9 容差保证
  +1 精确落在 30 tick 边界（修复旧连续累加器的浮点漂移，如 1s 周期此前
  实际约 31 tick 才 +1）；快照新增 `costTimer` 字段。
- 测试 `tests/test_cost_manager.py`（8 项：精确周期/满时暂停保留余量/修饰符/
  绝对值设置/锁定/负费用减速/无回复哨兵/快照字段）；原
  test_cost_recovery_interval 的 12.0/base+2.0 断言修正为精确的
  13.0/base+3.0。
- 遗留：多个 cost-timer 修饰符的组合语义（PriorityQueue 具体规则）、
  DIALOG_SHOW 锁定在模拟器中的自动接线（目前只提供 API）。
- 2026-08-06 更新：CostTimerModifier 补全 costAddLocked 字段
  （dump.cs:375904 AddCostTimerModifier 第 4 参）；修饰符周期连乘，
  任一 costAddLocked 修饰符存在即冻结自然回复，移除后恢复；
  cost_timer_state().locked 合并该锁定。测试新增
  test_multiple_modifiers_multiply_and_lock（1.5x2.0 连乘=3.0s、
  costAddLocked 冻结/移除恢复）。

## 2026-08-06 Web 编辑器敌人可视化放置【已实现】

- `/editor` 页面新增敌人调色板：搜索敌人（`/enemies?q=`，返回
  enemyRoster 的 key + 中文名）→ 选择敌人 → 开「place mode」→ 点击地图
  格子放置；放置物以红色标记显示在格子上，侧栏列出全部放置项（可删除/
  清空），保存时与 enemies JSON（分组波次）合并进 waveTimeline。
- 引擎支持自定义生成坐标：waveTimeline SPAWN 事件或 custom_enemies
  override 可带 `row`/`col`，敌人在指定格生成（默认仍为路线起点），
  随后沿 routeIndex 路线移动；越界自动钳制到地图内。
- 新增 `Simulator.store` 属性（供编辑器/工具读取数据）；`live_server`
  新增 `GET /enemies?q=` 接口。
- 页面改为独立文件 `ark_emulator/web_editor_page.html`（中文安全，
  `web_ui.editor_html()` 优先读取，回退内联字符串）。
- 测试 `tests/test_editor.py`（4 项：时间轴指定坐标/override 指定坐标/
  编辑器流程端到端/页面与接口）。

## 2026-08-06 干员技能 prefab 完整分组【已实现（[uc]skills CAB 解包）】

- 从 `data/battle/prefabs/[uc]skills.ab_unpacked`（UnityPy 直读 GameObject
  名 + MonoBehaviour typetree）提取 1866 个 GameObject / 6938 组件：
  - `ark_parser/character/data/skill_prefab_catalog_operator.json`：全量
    组件（cabin/pathID/scriptPathID/class/fields）。
  - `ark_parser/character/data/operator_skill_prefab_summary.json`：紧凑
    参数（class、namedAsAlias、`_buffs`/`_activeBuffs`/`_passiveBuffs`、
    selector/cast 字段），模拟器直接消费。
  - `operator_skill_prefab_coverage.json`：1449/1473 个 skills.json
    prefabId 命中（98.4%）；24 个缺失为较新角色，疑似在热更包
    PersistentData/Bundles/anon 的 skills 包中（待 AssetStudio 补提）。
- 语义映射（按组件类 + 字段）：
  - Ability/AbilityStandard._buffs → 施法者自身 buff（如砾 S1 def_atten、
    阿米娅 S3 switch_mode/suicide、艾丽妮 S2 mark/recharge）；
  - BuffAbility._buffs / Ability._activeBuffs → 目标 buff：当前仅实现
    异常类（abnormalFlags → 施加给范围内敌人，如德克萨斯 S2 眩晕），
    非异常目标 buff（治疗/回费等）需 selector 解析后接入；
  - _passiveBuffs → 保留给光环接入。
- 模拟器接入（operator_skills.py）：
  - `_operator_prefab_buffs(skill_id)` 返回 (class, field, buff) 三元组，
    优先全量目录、回退原静态 data_operator_skill_buffs.json；
  - `on_start` 对 owner buff 用 materialise_buff 施加到干员；目标异常 buff
    施加到范围内敌人；**prefab owner buff 已覆盖的数值属性（attributeModifiers）
    不再从 blackboard 重复叠加**（修掉双计，如清道夫 S2 攻击力）。
- 测试：test_operator_skills.py 新增 prefab owner buff（砾）/ 目标 buff
  不自眩晕（德克萨斯）/ mberry 真实 buffKey 三项。

## 2026-08-06 SP 收尾：装备技能索引 + 无法触发受击回复【已实现】

- **装备技能索引**：squad 配置 `skillIndex`（游戏 SquadSlot 字段）经
  `BattleController.deploy_operator` 传入 `OperatorSkillController`：
  - SP 条上限/初始技力取该技能（maxSp=spCost×charges、initSp）；
  - 只允许激活已装备 SP 技能（其余返回 not_equipped），AUTO 只自动释放
    已装备技能；部署触发技能（spType=8）不受影响；
  - 未提供 skillIndex 时保持原共享 SP 条行为（向后兼容）。
- **无法触发受击回复的来源**：
  - 元素损伤（DamageType.ELEMENT）一律不触发受击回复（battle.apply_damage
    强制 no_hit_recovery）；
  - buff 模板固定/持续伤害（_n_DamageByAtkScale / _n_NoSourceDamage /
    _n_ApplyDamageByFixedValue）不触发受击回复；
  - 环境/地形伤害（火山/毒雾/落穴）本就无 source，不触发（不变）。
- 测试：test_sp_mechanics.py 新增 4 项（装备技能 SP 条归属 / 未装备技能
  激活拦截 / squad skillIndex 端到端 / 元素伤害不触发受击回复）。
- 遗留：受击回复的其它来源（如反伤、闪避后无伤害等）随各系统接入时再
  逐点核对；技能 prefab 目标 buff 的 selector 解析（治疗/回费等）。

## 2026-08-06 目标 buff selector 解析 v1 + 增益减益动作节点补全【已实现】

- **目标 buff 分类（v1）**：prefab 目标 buff 按内容决定施放对象：
  - abnormalFlags → 范围内敌人（如德克萨斯 S2 眩晕）；
  - 模板含治疗/元素治疗动作（Heal/ApplyElementHeal）→ 范围内友方
    （如蜜莓 S1 ep_heal_all）；
  - 其它（回费/模式切换等）暂不施加，避免错侧投放（charge_cost 等）。
- **buff 模板动作节点补全**（buff_templates.py）：ModifyCost（回费）、
  ApplyElementHeal（元素治疗）、Withdraw（强制退场/自杀）、RechargeToken
  （充能回 SP）、DisableTrait/EnableTrait（占位）、
  RemainingRatioToAttributeModifier（按剩余比例衰减的数值修饰，如
  砾 S1 防御 +200% 线性衰减：t0=+200%、t3s=+100%、t6s=+0%）。
- **buff 生命周期细节**：
  - ON_BUFF_START 在施加时触发（含新节点）；waitFirstTriggerInterval=0
    的模板立即触发首次 ON_BUFF_TRIGGER（def_atten 开局即满值）；
  - 无 durationKey 的 prefab buff 回退到技能黑板上 duration / 技能生效窗
    （>=1s），解决 1 tick 即消失的问题；
  - 施法者 buff 含 Withdraw 动作（阿米娅 S3 自杀）不在施放时触发（技能
    结束才退场）。
- **回费去重**：prefab owner buff 带 ModifyCost 时不再叠加黑色板 cost
  瞬时回费（清道夫 S2 此前 +22 双计，现正确 +11）。
- 测试：test_operator_skills.py 新增 5 项（砾衰减精确值/阿米娅不立即退场/
  蜜莓治疗给友方不给敌人/charge_cost 不错投/清道夫回费去重）。
- 遗留：BuffAbility 的 selector/runActionOnEvent 完整解析（当前按模板
  语义启发式分类）；敌方侧 buff 模板同批节点待接线。

## 2026-08-06 AI 打图接口（AgentEnv）+ 敌方 buff 引擎验证【已实现】

- **AgentEnv**（ark_emulator/agent_env.py，Gym 风格）：
  - `reset(seed, level_id, squad, custom_enemies, custom_level)` ->
    (obs, info)；`step(action)` -> (obs, reward, done, info)，每步推进
    1 逻辑帧；非法动作返回 invalid 而不崩溃；
  - 动作：deploy / withdraw / skill / deploy_summon / deploy_token /
    pause / resume / step_ticks；
  - 观测 = 全量快照（增量事件）；奖励权重可配：击杀 +10、漏怪 -20、
    部署 -0.5、技能 -0.1、胜利 +100 / 失败 -50；
  - 辅助：`deployable_chars()` / `buildable_cells()`；`play_random`
    随机策略演示；示例 `examples/agent_play.py`；README 已加用法。
- **敌方 buff 引擎验证**：敌方技能 buff 与干员共用同一 materialise_buff +
  BuffSystem 管线（skills.py 的 prefab_buffs/self_buffs 均走 add_buff），
  上一轮新增节点（ModifyCost/元素治疗/Withdraw/充能/衰减修饰/立即触发）
  敌方侧自动生效；新增 test_enemy_buffs 衰减用例（def_atten 在敌人身上
  +200% -> 0 线性衰减）。
- 测试：test_agent_env.py（6 项：reset/非法动作/部署/击杀胜利奖励/确定性/
  随机演示）。

## 2026-08-06 AgentEnv 升级：合法动作空间 + 奖励塑形 + 批量环境【已实现】

- `legal_actions(include_directions=False, max_cells=64)`：返回当前可执行
  的 deploy / skill / withdraw 动作字典，逐项校验：费用足够、再部署冷却、
  characterLimit、目标格可建造且未被占用、SP 就绪、已装备技能规则；
  `step(None)` = 等待（推进 1 帧）。
- 奖励塑形：新增 `damage_reward`（对敌伤害）、`damage_taken_penalty`
  （我方承伤）、`time_penalty`（按帧计时）权重，默认 0 保持原奖励不变。
- `BatchEnv(n, ...)`：同步向量环境，`reset_all(seeds)` / `step_all` /
  `legal_all()` / `done_all()` 支持一次评估 N 个种子。
- 测试：test_agent_env.py 新增 4 项（等待动作/合法动作空间/伤害塑形/
  批量环境），现共 10 项。

## 2026-08-06 脚本化智能体基线（GreedyDefender）【已实现】

- `ark_emulator/agents.py`：基于 `legal_actions()` 的启发式策略
  （先锋开局、路线重装阻挡、医疗/术师部署、技能就绪即放、低血量撤退），
  `play_episode(env, agent)` 单局、`evaluate(levels, seeds, ...)` 用
  BatchEnv 扫掠多关卡 x 多种子；作为 RL/搜索策略基线。
- 演示：`python examples/agent_greedy.py`（main_01-01 端到端可跑，
  击杀 8/漏怪 10，作为基线基准）；`examples/agent_play.py`（随机策略）。
- 测试：test_agents.py（3 项：自定义关卡获胜、主线冒烟、evaluate 扫掠）。
- 注：热更 `[uc]skills.ab` 未下载到本地客户端（hot_update_list 有清单、
  本地无文件），24 个新角色技能 prefab 无法本地补提，已记录为外部数据
  阻塞；AssetStudio CLI 导出模式需最小参数（无 -g/-o）才能运行。

## 2026-08-06 GreedyDefender 调优 + 漏怪事件坐标【已实现】

- GreedyDefender 增强：`early_blocker`（开局优先部署垂直流阻挡，DP 不够时
  攒钱等待）、禁止在角色未齐前重部署（避免 DP 浪费）、plan 去重
  （head/mids/tail 重排不再产生重复项）、阻挡优先于输出。
- 漏怪事件 `enemy_reach_exit` 新增 `row/col/routeIndex`（AI/回放可定位
  漏点）；main_01-01 实测漏点分布：垂直流(0,5) 8 只、中路(3,8) 2 只。
- 基线：`examples/agent_greedy.py` main_01-01 目前 defeat（击杀 8/漏 10/
  部署 4）——这是启发式策略的已知基线（受 DP 收入与早期双流阻挡约束），
  后续 RL/搜索策略以此为对比起点；模拟器保真度本身不受影响。
- 测试：test_agents.py 新增漏怪事件坐标用例；main 冒烟改用 early_blocker
  编队；自定义关卡获胜用例保持。
- 注：热更 [uc]skills.ab 未下载，24 个新角色技能 prefab 本地不可得
  （外部数据阻塞）；AssetStudio CLI 导出需最小参数。

## 2026-08-06 批量关卡基准评测（BatchEnv x GreedyDefender）【已实现】

- `ark_emulator/benchmark.py`：`run_benchmark(levels, seeds, agent, ...)`
  用 BatchEnv 跑 关卡 x 种子 评测，产出 JSON 报告（每关胜率/奖励/击杀/
  漏怪/部署/结束 tick + 汇总）；`examples/benchmark_report.json` 为当前
  基线快照。
- 修复 BatchEnv 评测共享 agent 状态串扰（每 env deepcopy 独立 agent）。
- 基线（GreedyDefender，seeds 0-2，max_steps 3000，5 关）：
  - 胜率 3/15=0.2；level_main_00-02 全胜（14 杀 0 漏 6 部署）；
  - 01-01 击杀 8/漏 10/部署 4；01-02/01-03 击杀 2/漏 10/部署 3；
    01-04 击杀 0/漏 12/部署 2 —— 均为启发式策略的已知基线（DP 收入与
    双流阻挡时序约束），RL/搜索策略以此为对比起点。
- 测试：test_benchmark.py（结构 + 保存 + 一次小型真实运行）。

## 2026-08-06 BeamAgent：短 rollout 束搜索部署【已实现】

- `ark_emulator/agents.py` 新增 `BeamAgent(GreedyDefender)`：部署窗口期
  （<beam_deploys 人）对每个候选部署位（各角色目标格最近的 top-N 格）做
  `rollout_seconds` 秒的贪心回放，用环境累计奖励选最优；利用环境确定性
  发现手写启发式错过的 DP/阻挡权衡。
- main_01-01 实测：击杀 9 -> 14（束搜索找到更早的中路/垂直补位），但漏怪
  仍 10（双流阻挡时序 + DP 收入上限；光束窗口后仍靠启发式）。
- 测试：test_agents.py 新增 BeamAgent 微型 rollout 用例（自定义关卡获胜）。
- 备注：BeamAgent 每决策约需数十秒（rollout 开销），暂不加入批量基准；
  后续可做 rollout 缓存/并行化，或作为 RL 初始策略。

## 2026-08-06 BuffAbility runActionOnEvent 时序接线【已实现】

- 依据 prefab：BuffAbility 的 `_runActionOnEvent` 决定目标 buff 施加时机
  （AbilityStandard.Event：0=ON_ATTACHED / 2=ON_CAST_START /
  4=ON_SPELL_ON 立即；1=ON_DETACHED / 3=ON_CAST_END / 5=ON_SPELL_END
  技能结束时）。全量分布：4x63 / 2x44 / 3x32 / 5x6 / 0x12 / 8x1。
- operator_skills.py：`_operator_prefab_buffs` 返回携带组件元数据的四元组；
  cast-end/spell-end 的 BuffAbility 目标 buff 延迟到 `on_expire` 施加
  （异常→敌人、治疗→友方，与施放时同一分类）；DataStore 实例缓存避免
  每调用重复读 1-2MB JSON。
- 测试：test_operator_skills.py 新增 cast-end 用例（技能结束前不施加、
  结束后目标被眩晕）。

## 2026-08-06 游戏更新后 AssetStudio 重解包 + 多段命中生效帧修正【已实现】

- **重解包**：给 AssetStudio BundleFile 打补丁（内层 CAB 全部落盘
  `_unpacked`），本地 NuGet 离线还原后重编译 CLI，把更新后的 main anon +
  PersistentData 全部 AB 解压成 201 个 CAB（`unpack_work/ab_update`）。
- **敌方侧新增**：新热更 `enm_pfb_34.ab`（996 GameObject，含新敌人
  enemy_10228_agball 等）已合并；敌方技能 prefab 目录 4423 -> 4555
  prefabKey，技能行为目录解析率 682 -> 706/711（99.3%）；enemy_database
  已含新敌人（纯普攻型，无技能列表）。
- **干员侧数据复查**：重新跑 extract_tables.py，skill_table 哈希
  `afb859` 与 skills.json 来源一致（干员数据未过期）；但更新后
  `[uc]skills.ab` 仍未下载到本地，24 个新干员/装置技能 prefab 仍缺失
  （清单见文末附录，含珊比 S3「不准走！」等）。
- **多段命中生效帧修正**：AbilityRun 的命中队列归零当 tick 结算（原来
  +1 帧迟到），生效帧精确 = 施放起点 + preDelay + 校准 OnAttack 时间
  （data_enemy_attack_timing.json 按 prefabKey 的 onAttack 序列，多段技能
  每段各结算一次）；新增 test_skill_system 多段命中用例（M1MultiAttack
  5 帧逐帧命中）。
- 附录：24 个缺失 prefab —— 干员：予愿安洁莉娜 1/2/3、谬因 1/2/3、
  嘉辛塔 2、机械师 1/2/3、佩德洛 1/2、珊比 1/2/3、时隙 2；装置/召唤物：
  邮箱、结构性原理、战术锚点 1/2、迷狂牢笼 3、源阶方模块、箱型恶笼草、
  丰饶树冢。

## 2026-08-06 干员技能 prefab 补全：24 -> 3 缺失【已实现】

- **根因定位**：游戏目录里另有
  `StreamingAssets/AB/Windows/battle/prefabs/[uc]skills.ab`（非 anon），
  其 CAB（同名 CAB-e39773c4…）比 data/battle 里的旧提取**更新更大**
  （3884472 vs 3728172 字节；GameObject 1866 -> 2920）。旧副本是早期快照。
- **处理**：用更新版 CAB 替换 data/battle/prefabs/[uc]skills.ab_unpacked，
  重跑 `extract_operator_skill_prefabs.py`：
  - 覆盖率 1449/1473（98.4%）-> **1470/1473（99.8%）**；
  - 缺失从 24 个降到 3 个（sktok_mtship_1/2 战术锚点 S1/S2、
    sktok_phatm2_mndclv_3 迷狂牢笼 S3 —— 在未下载的其它包）；
  - 珊比 S1「还不走？」实测可激活并施加真实 owner buff `thumpy_mode_1`；
    珊比 S3「不准走！」prefab 就位（AttackAbility + CompositeAbility）。
- 旧 CAB 备份于 `data/battle/_old_cabs/`。

## 2026-08-06 干员技能伤害类型/元素/弹道参数接入 prefab【已实现】

- 提取器 compact_params 增补 `_damageType/_elementDamageType/_epDamageRatio/
  _projectileKey/_additionalProjectile/_extraDamageType`；重跑目录。
- `ActiveSkillEffect` 伤害类型优先读 prefab `_damageType`（游戏枚举
  1=PHYSICAL 2=MAGICAL 3=PURE 5=ELEMENT → 模拟器枚举），回退角色描述启发式；
  实测德克萨斯 S2 剑雨由启发式物理改为 prefab 法术（MAGICAL），且携带
  projectile_sword_rain（弹道接入后续做）。
- 测试：test_operator_skills.py 新增 prefab 伤害类型覆盖用例。
- 剩余：3 个 token 技能 prefab（sktok_mtship_1/2、sktok_phatm2_mndclv_3）
  本地各包均无；CompositeAbility 子能力递归解析（阿米娅 S3 等）待做。
- 2026-08-06 更新：sktok_phatm2_mndclv_3 经 characters.json MainSkill
  overridePrefabKey 解析为 sktok_empty（存在），覆盖率为 1474/1476；
  仅 sktok_mtship_1/2 为真占位槽（无 prefab 属预期）。

## 2026-08-06 莱伊沙地兽（巡哨伙伴 + S2 广域警觉）实现【已实现】

- **沙地兽命周：**token_10034_ray_sndbst 经天赋 tokenKey 注册可招唤，
  仅可部署在招唤者攻击范围内；按先天赋高阶候选 duration
  （15s/25s）自动到期退场（Token.expire_tick + token_expire 事件）。
- **检探区域：**Token x-4 范围统计为 battle.token_area_cells(op)；
  targeting 优先选择区域内敌人并扩展有效攻击范围
  （自身范围 ∪ 沙地兽区域）；区域内目标的物理伤害
  最终乘 (1+damage_scale)（E2 15%）。
- **S2 广域警觉：**活跃时攻击范围覆盖为 rangeId 4-10
  （on_start/on_expire 保存与恢复）、攻击力加成（通用）、
  沙地兽再部署时间乘 (1+respawn_time)；无限持续技能
  （duration=-1 非部署技能）现在不再立即结束。
- **弹荫回收（S2 被动）：**莱伊对检测区域内敌人的成功
  物理伤害会记入沙地兽 token._recover_bullets；沙地兽退场/到期时
  按上限回收弹荫（ray_sandbeast_ammo_recover 事件）。
- **通用修复：**非攻击型 summon（沙地兽等）不再攻击（
  _NON_ATTACK_TOKENS + 原始 atk 为空的 token 强制 atk=0），
  被动型定向塔仍保持 maxHp×scale 攻击（._bb_like 后缀匹配）。
- 测试：test_ray_kit.py 新增 5 个沙地兽用例（命周/优先级与范围扩展/
  伤害加成/退场回收弹荫/S2 范围与再部署）；
  全量回归 27/27 全绿。

## 2026-08-06 莱伊（猎手）弹药联动 + 束缚实现【已实现】

- **束缚（UNMOVABLE=13）**：敌人带有该 flag 时无法移动（
  entities._can_move），但仍可攻击；技能 attack@unmove_duration
  已接入 apply_on_attack。
- **猎手攻击倍率覆盖（S3）**：hunter_atk_scale 优先读活跃技能
  blackboard 的 attack@atk_scale（1.9~3.3），否则用特性 1.2；且猎手活跃
  技能的 attack@atk_scale 不再触发 apply_on_attack 的额外伤害层（
  避免双重计算）。S3 启动时清空弹仓、装填间隔
  reload_interval-1.2（已有），命中附加 2s 束缚；技能期间击倒敌人
  则结束时返还 10 点技力（ray_s3_sp_refund 事件）。
- **入神（天赋 2）**：攻击同目标每次叠 +8%/9% ATK（上限
  max_stack_cnt=3），切换目标重置为 1 层（始终至少 1 层，
  PRTS 备注）；hunter_focus_multiplier 在开火时与攻击倍率相乘。
- **S1 脱身矢（特殊子弹）**：启动时立即发射一枚不耗弹
  的特殊子弹（atk×atk_scale 2.2~4.5 物理 + 推进 force）；若击倒则下次
  装填额外 +cnt 弹（可叠加，hunter_reload_bonus 事件）。
- 测试：新增 tests/test_ray_kit.py 7 用例（特性基础、S3 倍率+束缚、
  S1 不耗弹+击倒加装填、入神叠层/切换重置、非莱伊无叠层、
  束缚限动、S3 击倒返技力）；全量回归 27/27 全绿。

## 2026-08-06 疗养师（healer）距离衰减实现【已实现】

- **机制（PRTS 清流页 “无特性影响的范围=2-3” + 本地 buff
  模板 finlpp/ceylon/whispr/nowell/lumen_trait 三者交叉确认）**：
  疗养师治疗同部署方向 2-3 内圈之外的目标时，
  治疗量最终乘 heal_scale（0.8，不受距离红利/周围红利叠加）。
- 内圈 2-3 = 标准医师 E0 的 7 格形状（rows ±1 × cols 0-2，
  顶/底行中间列缺失）；超出部分（含 E0 的 3-3 右侧列与
  E1+ 的 3-4 外圈）均按 0.8 计算。
- 实现：traits.TraitSystem.heal_falloff_scale(target, battle) 使用
  range_offsets_rotated('2-3', op.direction) 判定；battle.apply_heal 统一挂载
  （源为疗养师时先乘衰减再回复）；可通过
  trait_immune=True 跳过（对应游戏内 “不受特性影响” 治疗）。
- 影响：普通攻击治疗、技能治疗（清流 S1/S2、锡兰
  S1/S2、絎雨 S1/S2、流明 S1/S2/S3）均遵循；生命回复速度
  类 buff（絎雨天赋 “不受特性影响”）不经
  apply_heal，不受影响。
- 测试：test_traits.py 新增内/外圈治疗量、面向旋转、
  非疗养师不衰减、技能治疗衰减 3 个用例；全量回归
  25/25 文件全绿。


## 2026-08-06 屏障（Barrier）子系统 + 珊比双天赋接线【已实现】

- **屏障子系统（通用）**：Unit 新增 barrier 吸收池；
  battle.apply_damage 在公式后、扣 HP 前先由屏障吸收（元素损伤
  不经屏障）；新增 battle.add_barrier(unit, amount, max_value, source)
  与事件 barrier_added/barrier_hit；损伤事件携带 barrierAbsorbed；
  快照包含 barrier 字段。
- **珊比天赋 1 探险理论（已接线）**：造成物理伤害时附带
  atk×ep_damage_ratio[trigger] 侵蚀损伤并给敌人打永久标记
  thumpy_water_mark（退场时清除）；敌人处于侵蚀爆发冷却时改为
  减少 duration_dec 秒冷却（互斥，PRTS 备注）；
  自身受到的元素损伤乘 ep_damage_scale
  （0.95/0.90/0.85/0.80）。
- **珊比天赋 2 坚硬脚板（已接线）**：被标记敌人水侵蚀爆发时，
  珊比获得 DEF 叠加（每层 def，上限 max_stack_cnt=30）与
  shield_value 屏障（上限 scale×max_hp，累加）。
- 实现：talents.TalentSystem 新增 ep_damage_scale/on_damage_output/
  thumpy_burst_reward；battle.apply_damage 引用输出钩子；buffs.update_ep
  应用 ep_damage_scale、_burst_effect 水侵蚀分支处理标记奖励。
- 测试：新增 tests/test_thumpy_talents.py 4 用例（附侵标记、冷却
  减少、爆发奖励叠加、屏障吸收）；全量回归 26/26
  文件全绿。

## 2026-08-06 珊比 S3 侵蚀爆发额外减防实现【已实现】

- **机制（PRTS 珊比页 + skchr_thumpy_3 blackboard
  thumpy[ep_break_water].def=-30 + thumpy_s_3[trigger] 模板交叉确认）**：
  S3 传送带上的敌人每次水侵蚀爆发时，获得一层永久叠加的
  额外 -30 防御（DEF 直接加算，叠加不上限）。
- 实现：battle._tick_conveyor_tile 在每次周期伤害前给传送带上敌人
  标记 thumpy_s3_mark（携带技能 blackboard 的 def_delta）；buffs._burst_effect
  水侵蚀分支检查该标记，爆发时给敌人叠加
  thumpy_ep_break_def buff（stat=def, add=-30, layers 逐次+1，无限期）；
  并发出 thumpy_ep_break 事件。
- 备注：珊比天赋 1 的侵蚀附加与天赋 2 的
  DEF/屏障奖励（坚硬脚板）仍待接入（需天赋系统扩展）。
- 测试：test_skill_tiles.py 新增爆发减防用例（预填 EP 990 +
  传送带周期侵蚀触发爆发）；全量回归 25/25 全绿。

## 2026-08-06 干员技能弹道接入 + 部署/阻挡保真修复【已实现】

- 弹道发射：技能 prefab 带 `_projectileKey` 时，on_start 不再即时结算，
  而是对范围内目标各生成一枚弹道（`battle.spawn_projectile`），携带
  Ability `_preDelay` 施法前摇（delay_ticks），飞行命中后回调结算：
  基础伤害（prefab `_atkScale` 仅当黑板无 atk_scale 时兜底）、
  stun/sluggish/ep_damage_ratio、弹道携带的 `_activeBuffs`（异常位）。
- 多次发射：Ability `_additionalTimes`（如德州 S2=1 → 两发剑雨）。
- AOE 目标：黑板 max_target 优先；技能描述含“所有敌人/全部敌人”时默认
  不限目标，否则单体。
- 弹道速度：精确表 data_projectile_speeds.json（2530 键）→ 启发式 → 10。
- overridePrefabKey：DataStore/operator_skills 解析 characters.json
  MainSkill 覆盖（sktok_phatm2_mndclv_3 → sktok_empty）。
- 部署掩码修复：远程干员（position 2）要求 buildableType & 2（高台），
  近战（position 1）要求 & 1（地面），此前硬编码地面导致远程无法上高台。
- 阻挡排队修复：敌人下一格被满员阻挡者占住时原地等待，不再穿人
  （Enemy.blocked_wait / _update_blocking 溢出检测）。
- 测试：test_operator_skills 新增剑雨弹道用例（两发 MAGICAL+眩晕、前摇 15
  tick、速度表）；test_projectiles 速度表期望更新；相关测试部署位改高台。


## 2026-08-06 CompositeAbility 子能力递归解析【已实现】

- 提取器增补：组件带 gameObjectPathID；catalog meta 带 GameObject
  pathID->名字；summary 保留 _abilities/_extraAbilities/_wrappedAbilities
  引用列表与组件 pathID。
- loader 递归解析：技能 prefab -> CompositeAbility._abilities /
  AttackAbility._extraAbilities / _wrappedAbilities 的 PPtr（组件 pathID）
  -> 子 prefab，去重访问。
- 共享模板过滤：被 >=3 个技能引用的通用 prefab（ExtraAbility0/Aura/
  Attack/RangedAttack/MultiAttack...）不整体归因；仅当其中组件携带的
  弹道 key 与本技能角色代码匹配（如 projectile_chr_horn_s1 -> horn）才
  纳入，避免把 Ling/irene 的弹道污染到其他角色。
- 效果：可解析弹道的技能从 132（仅顶层）扩展到 161（含子能力），
  如德州异格 S3 剑雨、凛御银灰 S3、Irene S3、Ling S2、Reed2 S2、
  Typhon S2 均正确获得弹道/伤害类型；elysm/iana 等不再被共享模板污染。
- 部署触发修复：trigger_on_deploy 尊重 squad skillIndex（此前总是放
  第一个 spType=8 技能）。
- 已知限制：Horn S1 等弹道挂在未通过 PPtr 图链接的独立 prefab 上，
  暂未解析（回退即时伤害）。


## 2026-08-06 干员技能阶段性周期（phased interval）【已实现】

- OperatorSkillRun 从黑板提取 "<prefix>.interval" 阶段：括号式
  （texas2_s_3[sword].interval）与点式（appear.atk_scale / appear.stun），
  排除 attack@/talent@ 前缀键。
- ActiveSkillEffect.tick 每帧按各阶段 interval（帧=round(interval*30)）
  触发 _run_phase：周期费用（X[cost].cost）、一次性阶段属性 buff
  （X[period].def / X[b].atk 等，首帧施加一次）、以及伤害爆发
  （阶段 atk_scale/damage/stun/sluggish/ep，回退顶层黑板；弹道技能
  生成弹道命中结算，目标上限取阶段 max_target）。
- on_start 部署爆发：若存在 "appear" 阶段（如德州异格 S3 appear.atk_scale
  =1.0 / appear.stun=1.0），以其数值打满范围敌人、发 1+_additionalTimes 发
  弹道；否则沿用顶层黑板。
- _operator_prefab_params 的 _additionalTimes/_preDelay 改从任意
  Ability 组件收集（此前仅在携带弹道的组件上收集，漏掉 AppearSwordRain
  的两次伤害配置）。
- 验证：德州异格 S3 部署时 3 敌 x2 发剑雨（100% 法术 + 1s 眩晕），之后
  每 1s 对最多 2 目标放剑雨（70% 法术 + 0.2s 眩晕）；测试
  test_phased_periodic_sword_rain 覆盖节拍与弹道计数。


## 2026-08-06 Web 单步 + 数据可达性核查【已实现】

- live_server POST /action 新增 "step"（暂停中推进 n tick 并返回快照），
  web_ui 顶部新增 "step 1s" 按钮；端到端验证（pause -> step 30 ->
  快照 tick+30 且保持暂停）。
- Horn S1 弹道核查：projectile_chr_horn_s1 挂在共享 "RangedAttack"
  prefab 上，且 skchr_horn_1 的 AttackAbility 无任何 PPtr 引用——该
  弹道来自角色基础攻击模板而非技能图，本地技能 CAB 不可达，维持
  即时伤害回退（终态限制）。
- DIALOG_SHOW 锁定：级别/技能数据只有 dialogue_config_signal_key 信号
  引用，无对话时长数据，不做臆测接线；lock_cost_increasement(reason=1)
  API 保留供上层调用。


## 2026-08-06 特殊地形 buff 接入模板引擎【已实现】

- 审计 data_tile_defs.json（111 tile）与 SCRIPT_KIND：冰面(35 关)/泥地(21)
  /流沙(19)/芦苇(20-25)/深海(34)/阴阳(25-27)/木地板(15)/火山(40) 等在
  真实关卡广泛出现，此前只有 dot/volcano/buff/infection/hole/conveyor/
  gravity 生效，其余分类后无行为。
- TileEffectSystem 新增 _apply_tile_template_buffs：对 mire/ice/quicksand/
  reed/deepsea/yinyang/wood 类 tile，将其 buffs + dynamicBuffs 通过
  materialise_buff 应用（每 tick 刷新，同 key 不重复添加），由 buff
  模板引擎驱动派生 buff/异常（冰面 -> e2c_cold/e2c_freeze 冻结链；
  泥地 -> buff_mire[trigger]/effect/log 链）。
- 测试 test_special_tile_template_buffs 覆盖冰面冻结链与泥地 buff 链。


## 2026-08-06 快照补全：干员 activeSkill【已实现】

- Operator.to_dict 新增 activeSkill 字段：当前激活技能 skillId、剩余
  时长（秒）、弹药数、已施加 buff key 列表；无激活技能时为 null。
  AI（AgentEnv/BeamAgent）可据此判断技能窗口与弹药状态。
- 实测：德州 S2 激活后 snapshot.deployed[0].activeSkill 输出
  {skillId, remaining, ammo, buffs}。


## 2026-08-06 敌方技能演出/音效节点事件化【已实现】

- ActionNodeExecutor 新增 CreateEffect / PlayAudio 处理：敌方技能
  _actions 图中的演出与音效节点现在输出 skill_effect / skill_audio
  事件（含 unit/effect/audio），不改战斗状态，供观察者/回放/前端消费。
- 敌方技能 prefab 中共 15 个 CreateEffect、9 个 PlayAudio 节点。
- 测试 test_action_node_effect_audio_events 覆盖两类事件输出。


## 2026-08-06 敌方技能索敌优先阻挡者【已实现】

- MECHANICS 5.1 规则补全：被阻挡敌人的技能（_find_target）优先以阻挡
  者为目标（此前普通攻击已实现、技能仍取最近目标）。
- 测试 test_enemy_skill_targets_blocker：敌人被较远干员阻挡时，技能
  仍指向阻挡者而非范围内更近干员。


## 2026-08-06 GreedyDefender 路由感知阻挡位【已实现】

- GreedyDefender._plan 接受 obs.routes：有路线数据时阻挡者放在真实
  路线格上（1 号阻挡者取离任一出口最近的路线格，2 号取离 1 号最远的
  路线格），替代硬编码 mid 行；BeamAgent 同步传入 routes。
- 基准（3 seeds x 5 关）：01-01 漏怪 17->10（15 杀），01-02 12->10
  （9 杀），总胜率仍 0.2（00-02 全胜）；属策略质量而非模拟器保真，
  作为后续 RL/搜索策略的基线。


## 2026-08-06 敌方 action 节点补全（阻挡/运动/场地交互）【已实现】

- ActionNodeExecutor 新增：
  - ReleaseFromBlocker：解除目标阻挡（清 blocked_by + remove_blockee，
    COMBAT -> MOVE），输出 enemy_released；
  - ChangeMotionMode：切换敌人运动模式（WALK=0/FLY=1，_resetToDefault
    回 WALK），影响洞/阻挡判定，输出 enemy_motion_mode；
  - FinishManagedProjectiles：清除指向目标的弹道；
  - SetBodyDirection / CreateTileEffect：演出/场地交互以观察者事件
    输出（enemy_facing / tile_effect）。
  - IgniteAllReedTile（2026-08-08 已实现真实状态变更）：全部芦苇地块
    切到 mode 1 燃烧（“领袖”Arson 纵火），复用 switch_tiles_mode。
  - SwitchDynamicBuffTileMode（2026-08-08 已实现真实状态变更）：战斗
    按格记录动态 buff 地块模式（battle._tile_modes），INDEX 设
    modeIndex / FLIP_BOOL 翻转（芦苇 0=熄灭 1=燃烧），切换后刷新
    站在该格的单位 buff（移除旧模式 buff，下帧按新模式重挂），快照
    tileModes 暴露。
- 敌方 prefab 动作图统计：ChangeMotionMode 8、ReleaseFromBlocker 6、
  SwitchDynamicBuffTileMode 8、CreateTileEffect 3。
- 测试 test_action_node_tile_and_release_handlers 覆盖状态变更与事件。


## 2026-08-06 敌方 action 节点深化（跳波/传送/换位/召唤）【已实现】

- ActionNodeExecutor 新增：
  - FinishCurrentWave：跳过当前波剩余事件（waves.finish_current_wave），
    输出 wave_finished_early；
  - ForceSetToTilePosition：解除阻挡并把单位传送到最近可行格，输出
    enemy_teleport；
  - Transport：交换来源/目标格位，输出 transport；
  - SummonEnemiesOnTargetTile：在目标格召唤敌人。
- 统计：FinishCurrentWave 7、ForceSetToTilePosition 5、Transport 5、
  SummonEnemiesOnTargetTile 7。
- 测试 test_action_node_wave_teleport_transport_summon 覆盖四类状态变更。

## 2026-08-06 ????特性?trait????????

- ?? `ark_emulator/traits.py` + `data_class_traits.json`?
  - ??? TraitData blackboard?characters.json???????????
    ?cost=1?????????interval=3/cost=-3???????????
    ????????0.8s????????max_target???-15%????
    ????/????????value??
  - ????????????????????????????2????????
    ???????????32???????????8????????
    ??/?????????????????
- ???apply_damage ???????_trait_tick ????+?????
  _trait_hit ????????/??/?????+??????_char_damage_type
  ?????targeting.operator_target ????????????????????
- ???????DataStore.flying_enemy_keys ?????? 【飞行单位】 ??????
  ????? is_flying ?? BLOCK_FREE??????????
- ???Operator.to_dict ?? trait {profession, subProfession, description,
  blackboard, flags} ? profession/subProfession ???
- ???tests/test_traits.py 8 ???????/??????/??/????/
  ??????/??????/??????/??????????? 24/24 ??

## 2026-08-06 ??????????? S3 ??????????

- ????????????battle._skill_tiles??place_operator_skill_tiles /
  clear_operator_skill_tiles / skill_tile_at?tick_once ?????????
  5.7 ???????_tick_skill_tiles??
- operator_skills.ActiveSkillEffect ?? _place_skill_tiles?? prefab ??
  ???_operator_prefab_buffs ? thumpy[switch_mode_2] ? OffsetTile ?????
  ?????????? 4 ?????on_expire / ??????
- ????????????<=4 ???? conveyor_speed=0.8 ?/?????
  ?ai.update_enemy_ai ??????????????????????????
  ??????????? atk_scale?0.2->0.4????? + WATER ????
  ?ep_damage_ratio[trigger]???? 8%/10%/12%??????? EP ???
- ???snapshot.skillTiles ???? {row,col,kind,skillId,instId,remaining,
  blackboard}??? skill_tile_placed / skill_tile_removed / conveyor_pull?
- ???????????>4???????????????? debuff
  ?thumpy[water_break_detect] DEF -30/?????? EP ???????
- ???tests/test_skill_tiles.py 5 ????4?/??+??+????/????
  ??????/????/?????????? 25/25 ??

## 2026-08-06 ???hunter???/?????????

- PRTS ??????????????4/6/8 ????????????? 1 ?
  ?????? atk_scale=120%?????????????????????
  ?? 1 ???????????????????????????????
  ???? S2 +0.8 / ?? S3 -1.2??
- traits.TraitSystem ?? hunter ????is_hunter/hunter_ammo_max/
  hunter_atk_scale/hunter_reload_interval/hunter_tick???????
  hunter_tick ???????+atk*1.2????????????+1 ???
  ????????????? = baseAttackTime + ???? reload_interval?
- battle._operator_attack ?? atk_scale ?????????????????
  _update_operators ??????????? hunter_tick?
- ???hunter_attack????/ hunter_reload_start / hunter_reload?
  ?? trait.hunter ?? {ammo, maxAmmo, atkScale, reloading, reloadInterval}?
- ?????????????? S1 ?????S3 ????/???????
  ??????????????????????????
- ???test_traits.py ?? 3 ?????/???1.2??????????
  ????test_traits ? 11 ?????

## 2026-08-06 ???/??? ?????????

- ????incantationmedic???? scale=0.5???????????????
  ??????????????????? ATK*50%?data_class_traits ??
  incantHeal ???traits.on_hit ???
- ????chainhealer???? attack@chain.max_target=3?atk_scale=0.75?
  ???????? ATK???????????????????? 2 ??
  ????? ATK*(0.75^n)????????????data_class_traits ??
  chainHeal ???battle ?????_resolve_operator_attack heal ???
  ?? _trait_hit ?????
- ???test_traits.py ?? 2 ??????????+???????????
  ???? 1.0x/0.75x?????? 13 ?????


## 2026-08-06 ??/???????????????
- data_class_traits.json ? `instructor`?atkScale=1.2??`bombarder` ???
  `groundOnly: true, aftershock: true`?? preferAir ???????????????
- traits.py?
  - `atk_scale(ranged)`????? ?1.2??????? ?0.8????????
    melee ? ?1.0??battle._operator_attack ??????
  - `ground_only()` + targeting.operator_target ???????????????????
  - `bombarder_aftershock_count()`??? 1 ????`attack@times` ?????
    ???? times=2 -> ??+1 ????`attack@enable_third_attack`??????
    -> 2 ????3 ???
  - `_bombarder_aftershock`??????????? 3x3 ?????????
    append_atk_scale?0.5??ATK ???????? waves ???????????
    ??????????? `attack{type:aftershock}` ???targets/waves/amount??
- ???prefab?charpack Attack_A: projectile + _additionalProjectile=after_shock,
  _additionalTimes=1?trait config ? attack@append_atk_scale/times ???????
  + PRTS????? 0.9??????????? 50%????????
- ???test_traits.py ?? 7 ???? 1.2?????/????????? 2 ??
  ??? 1 ??ground-only ????????????? 27/27 ??
- ?????????data_range_table.json ???????? (0,0)?`_operator_attack`
  ? ranged ????? (0,0)????????????????????????????
  ??????????????????????????? position/profession
  ?? ranged ??????


## 2026-08-06 ??????/???????????
- ?? data_range_table.json ??????????? (0,0)?`_operator_attack` ?
  ranged ????? (0,0)?????????????????????
- ??????? position ???entities.Operator/Token ?? position?deploy /
  deploy_token / predefined token ? character data ????
  - position 2???????/??/??/??...?????????
  - position 1 ??????????/??/??/????????????????
    ???????????????
  - ???? position ? token???????????
- ?????token ? char_id ???? key ?? AttributeError???
  char_id ? token_id?????????????????????????
- ???test_projectiles.py ?? 2 ??????????+???????????
  ?? 3 ?????buff ??/??????????????????????
  ?????????????? 27/27 ??


## 2026-08-06 ?????????????
- ???subProfessionId=`funnel`???/??/?????trait blackboard
  init_atk_scale=0.2 / delta_atk_scale=0.15 / max_atk_scale=1.1 /
  max_stack_cnt=6??? `projectile_chr_gdglow_funnel`=10?PRTS??? 20%?
  ??????? +15%??? 110%??????
- entities.FunnelDrone?? Unit ???????????/???????????
- battle.py?
  - ??? `_sync_funnel_drones`??? 1 ???? attack@cnt ????? S1/S2 +1?S3 +2??
  - `_update_funnel_drones`????????????????baseAttackTime?
    ???????????????????? 0.2?1.1 ????????????
    source????/????S3????????????? 0.5s ???
  - funnel ?????????????????????
- operator_skills.py?????/??????????? rangeId ???
  ??? S2 3-18?????????????
- ???????? buff ???
  1. `BuffSystem.add_buff` ?? buffKey ??? attributeModifier ??????
     ??? S1 atk+attackSpeed ????? atk??
  2. `materialise_buff` ? stat ?????? template_key??? ON_BUFF_START
     ???ModifyCost ????? buff ???????scave S2 ????????
- ???tests/test_funnel.py 8 ????/??/??/???/S1/S2/S3/????
  ???? 28/28 ??
- ???????????1???1.5%/??40 ?????? 1.1?200%~360% ATK
  ??????2????? magic_resist_penetrate_fixed ???????? S2
  ???? scale=1.5?


## 2026-08-06 ?????? + ???? + ?????????
- talents.py `stat_modifiers()`????????????????????????
  ????atk/def/max_hp/move_speed/magic_resistance?? multiplicative ??
  ????attack_speed/block_cnt/??/??/??/?SP/??/????/??...?
  ? additive ??????? attributes?key="talent:*"?????????buff
  ???????????????15????????160???atk+10%????+6%?
- ????1??????????????????????????1.5%/??
  ??+1?40??????????? 3x3 ?? attack@atk_scale_2?E2=3.0?x ATK
  ?????????????S3 ?????????? funnel_destruct ???
- ??S2??????????????? x scale?1.1->1.65??????????
  ?max_stack 6 -> 10?????????
- ???Attributes.add_modifier ??????additive/multiplicative????
  add/mul ????????????
- ???test_funnel.py ?? 4 ?????????????????????
  ?????????? test_gravel_def_atten_decays_exactly??????E2????
  ???? 28/28 ??
- ????????????????????????????????????/
  ?????????????????


## 2026-08-06 ????????????
- talents.py ?? `aura_specs()`???/???/??/????
  - ??????????????? atk ? (1+value)?E2 10%??
  - ??????????????? 3x3 ????position 1??? atk ? (1+value)?E2 10%??
  - ?????????????????????blockCnt>=3 ??+6/?+12%?
    blockCnt<3?sophia_t_1_less.*???+3/?+6%?
  - ????????????????? 3x3 ?????+12%???????????+12%?
- battle.py `_update_talent_auras()`?? tick ????????????buff ?
  talent_aura:{src}:{stat}??????????/???BuffSystem ????????
- ?? stat_modifiers ???????/???? atk ???????????????
  ? interval/duration/prob/hp_ratio ??????????????15???+60?
  ??????????
- ???tests/test_talent_aura.py 4 ???? test_funnel ?????????
  ????????? atk?????? 29/29 ??
- ??????????????????????? + ??>80% ??????
  ?????????????????????/??? 3x3 ???????


## 2026-08-06 ????2???????????????????????

- ???char_4125_rdoc talents?E1 dec_rate=-0.2 / E2 dec_rate=-0.1?
  scale=50?+ data_buff_templates.json ? rdoc_t2[shield]/[listener]/[heal]
  ?????? PRTS ????????
- ???
  - ???????????????????? 1:1 ??????
    ?? = ?????????? ? 5000%?scale=50??
    ???????????? >= ????????????????
    ??? rdoc_t2[listener] ? FilterByBlackboardValue ????
  - ??????? buff???? +1000?????? barrier ??????
  - ?? 1s ????????? 0.1s ?????? 2%(E1)/1%(E2)?
    ?????????? RoundBuffBlackboard Floor ????? = ?? ceil??
- ???
  - entities.Unit?`_rdoc_shield/_rdoc_shield_cap/_rdoc_decay_rate/
    _rdoc_next_decay_tick` + `absorb_rdoc_shield()`????? rdocShield?
  - battle.apply_heal?healed < amount ???/?????
    add_rdoc_shield?? talent_system.rdoc_overheal_params ??????
  - battle.add_rdoc_shield???/??/???? tick=+30?1s????
    _update_rdoc_shields ? tick_once ?????3 tick = 0.1s ????
  - battle.apply_damage???????? rdoc ?????? barrier/HP?
    barrier_hit / barrierAbsorbed ?????
- ???tests/test_rdoc_barrier.py 6 ?????/??/1s ??/E1-E2 ???/
  ?????/???????? 29/29 ??


## 2026-08-06 ?????? + ?????????????

- ??1???????(char_485_pallas, E1 15% / E2 25%)?
  - ?????????????nationId=minos????/???/??/??/
    ???/??????????? 80% ???????????
    ??????? buff ???????????????????????
  - ???aura_specs ?? named=peak_performance ???_update_talent_auras
    ? (??,??) ????????? buff?_aura_target_ok ??
    nationId=minos ? hp_gt ???? tick ????? <=80% ?????
- ??2???????(E2 40 / ?5 45)???????????????
  ????????????????????
  - ???_on_operator_hit_heal ???????????
    talent_system.attack_heal_flat() ???
- ??????instructor??????????????? 1-2 ??????
  ????????????????? _sub == "instructor" ???
- ???tests/test_pallas_talents.py 4 ??????????/HP ??/
  E1 ??/?????????????


## 2026-08-06 ?? S1??????/ S2???????????

- S1??????????SP 35/?5?M3 25/15??
  - ?????????? atk ? heal_scale?1.0?4.0??????????
    ?? -0.3?-0.7?prefab owner buff rdoc_s1[switch_mode] ???
    ?? base_attack_time ??????
  - ?????prefab _showSpAsBulletMode=1 ? is_ammo????????
    attack@trigger_time=31??????? 1 ?????????on_ammo_attack??
  - ???????? 3 ??skill_max_trigger_time=3?per-deployment ??
    ? OperatorSkillRun.use_count????????
- S2?SP 30?M3 20/?15?????
  - ?????????????projectile_chr_rdoc_s2??? 5.0???
    4-1=?? 4 ???????????????????/??? ? ??
    atk ? heal_scale?3.0?7.5?????? ? ???????????????
    ?????? 3 ??
  - ???_rdoc_s2_fire ??????? + spawn_projectile(hit_callback)?
- ???????duration<0 ????? duration ???????????
  ????atk/def/base_attack_time/attack@* ?????????Ray S2/
  Whisperain S2??????? 0.1s ?????? S2?????????
  already_active ??????
- ???tests/test_rdoc_skills.py 5 ???S1 ??/??/???S1 ?????
  S2 ?????????S2 ??????????S2 ?????????????


## 2026-08-06 ?????????? ON_BEFORE_EP_BREAK_START?????

- ?????/??????????????????????????
  ON_BEFORE_EP_BREAK_START ????????? buff ???
  - ??????????? buff?owner=??????? S3 phatm2_s_3[token]
    ???????/???thumpy[water_break_detect]??
  - ?????????? buff?owner=????target=???????
    blaze2_t_1 ????????????? ? ????????????
  - ??? bb._ep_break_type ? FilterEPBreakRecoveryType ???
- BuffTemplateEngine ???????
  - ?? _n_FilterEPBreakRecoveryType?SANITY=0/WATER=1/FIRE=2/DARK=3??
    _n_IfConditions?_n_TriggerBuffsByKeys?_n_CheckTargetRootTile??
    ????/????/??????_n_CheckHeightTypeOfRootTile?LOWLAND/
    HIGHLAND??_n_SpawnTokenOnTargetTile?_n_CreateBuffToCharacterOn-
    TargetRootTile?????????HP ??+?? buff??
  - run_actions ????????????????? bool ???????
    ?????IfNot ????False ????????gate=False ?????
    ?? [CheckX, IfNot, CheckY, Spawn] = "NOT X ? Y ???" ???
  - ?? CheckContainsBuff ? AND ????????all([])=True??
- battle.spawn_token_forced??????/???????????????
  ????????????? key ?????????HP ???????
  ?????/????????????
- ???tests/test_ep_break_templates.py 5 ?????????/??????/
  ?????? DEF+??/??????????/????????????
  33/33 ??


## 2026-08-06 ??? S3?????+ maxHp ?????????

- ??? S3?skchr_amiya_3?30s?SP 120??
  - prefab owner buff amiya_s_3?atk ?(1+100%)?maxHp ?(1+25%)?
    ???????????????????? damage_type_switch ????
    ??/????
  - ??????????prefab ? suicide buff?ON_BUFF_START=Withdraw?
    ???? deferred_buffs?on_expire ???????????????
    ??????????????????
- ?????maxHp buff/?????????? Unit.max_hp????????
  ?? HP??? maxHp ????????????? maxHp?????? +12%?
  ?????
- ???tests/test_amiya_s3.py 2 ????? buff+?????30s ???
  ???????? 33/33 ??


## 2026-08-07 ?? S3???????????????

- S3?30s?SP 40??? y-8??
  - ??????????rangeId y-8??atk+60%?prefab owner buff
    phatm2_s_3 ????op.prefer_unburst=True???/????????
    ?????????????targeting ????
  - ?????? 5 tick ?? phatm2_s_3[token] ?? buff???????
    ???????? phatm2_s_3[token] ???????????/??
    ??????? buff ???????????? 1.5 ?????+50%
    ????????
  - ????????????add_ep source ???? ??
    ON_AFTER_OUTPUT_ELEMENT_DAMAGE ??? buff ? phatm2_s_3[sanity]
    ??????? phatm2_s_3[trigger] ??????????
    ep_damage_ratio?10%?????????????????????
    ?????
  - ????????????? phatm2_s_3[token]/[trigger] buff ?
    ?? prefer_unburst?
- ??/?????
  - battle.add_ep / BuffSystem.update_ep ?? source?
  - ?????_n_IsTargetInEPBreakRecovery?_n_ApplyElementDamage?
    _n_FinishBuff?_n_FilterElementDamageModifer?_n_FilterModifierByRealDelta
    ?EP ??=????????
  - ?? _targets/_source_unit?TARGET/MODIFIER_TARGET ???????
    ??????? owner??? MODIFIER_TARGET ? buff ??????
  - BuffSystem ????? EP ?????ep_cooldown_speed??
- ???tests/test_phatm2_s3.py 4 ?????+??+?????????
  DoT+?????????????????????????????
  34/34 ??


## 2026-08-07 ????????????? + ON_EP_BREAK_START ???????

- ?????????attack@ep_damage_ratio????????????
  ????????????? atk?ratio ?????????????
  ??/??/??/???????????? 8 ?????????
  ep_damage_ratio ?????? T1 ?????0.3 ??? + 0.2 ????
  ?? bb_exact ???????? ep_damage_ratio ? attack@ ????
  ???????
- ?? T1 ??????????? blaze2_t_1 ?? buff?????
  ep_damage_scale=3.5 / hp_ratio=0.12??
  - ON_BEFORE_EP_BREAK_START????????? ? ????
    hp_ratio??????
  - ON_EP_BREAK_START?????????????????
    atk?ep_damage_scale ?????? add_ep_force ??????????
    ???????????????????
- buffs._dispatch_ep_break_event ???? ON_BEFORE/ON_EP_BREAK_START
  ?????????? buff + ?????? buff??
- ???tests/test_element_talents.py 2 ?????????+???
  ??????+?????????? 35/35 ??


## 2026-08-07 酒神 T2 坠梦 + 烛煌 T2 绝处重燃

- 酒神 (char_1042_phatm2) 第二天赋 坠梦
  - 全场 aura：在场时，处于神经损伤爆发期的敌人攻击速度 -12/-16
    (黑板 attack_speed）。battle._update_enemy_talent_auras 每 tick 同步：
    敌人有 ep_burst_cd_0 则挂 phatm2_t_2[attack_speed] buff，爆发结束即移除；
    酒神退场后自动清理。
  - 攻击范围内敌人普通攻击时受到 70 点神经损伤
    (黑板 value）。对范围内敌人挂 phatm2_t_2 听聊 buff（
    template_key=phatm2_t_2）；敌人普攻起手 (spell-on)时
    battle.on_enemy_ability_spell_on 派发 ON_BEFORE_ABILITY_SPELL_ON，引擎
    _n_ApplyElementDamage 新增固定元素损伤模式
    (_isFixedEpDamage + _fixedEpDamageKey) 对侵攻者造成神经 EP，
    source 保留为酒神（可驱动 S3 标记合作）。
  - 其他：这两个参数不再混入干员自身属性
    (stat_modifiers 排除酒神 T1/T2；T1 的 range_radius 是泼洒半径)。

- 烛煌 (char_1040_blaze2) 第二天赋 绝处重燃
  - 部署时挂 blaze2_t_2 听聊 buff（blackboard:
    hp_recovery_per_sec_by_max_hp_ratio=0.03/0.035, dynamic=6000, stun=5）。
  - 致命伤害（障磕后仍会致死）前拦截
    (apply_damage 在 take_damage 前计算 barrier 吸收后的有效伤害)：
    进入倒地 (重燃) 状态：中断技能、清空自身 buff
    (保留天赋/状态标记)、hp->1、获得 6000 屏障、
    0.3s 不死+无敌、禁疗/绑架/沉默、拦挡 0、不可攻击。
  - 倒地期间：每秒回复 maxHp * ratio（绕过禁疗）；
    对晕眩/冻结/无法行动/沉睡免疫且反制
    (敌方源头反射同样异常)；外部治疗被拒绝，
    但 T1 熔点引爆的自疗通过 HealViaMaxHpRatio 的
    _ignoreHealFree 生效。
  - 回满复活：对半径 1.7 范围内敌人晕眩 5s，
    清除屏障/倒地标记，复活动画期间短暂不死+无敌。
    可重复触发（次数不限）。
  - 引擎：Unit 的 invincible/undeadable/heal_free 支持异常 flag
    (INVINCIBLE=5 / UNDEADABLE=6 / HEAL_FREE=7)；apply_heal 新增
    ignore_heal_free 参数。倒地标记 buff 不挂模板键，
    避免官方 reborn_state 模板的 ON_TAKE_DAMAGE BlockDamage 双重结算屏障。

- 测试：tests/test_t2_reborn_talents.py 3 用例（神经爆发攻速
  减速与普攻神经 EP、倒地/回血/复活/晕眩/反制/
  重触发）；test_phatm2_s3 旧断言纳入 T2 的 +70 EP
  （范围内敌人普攻）。全量回归 36/36 文件全绿。


## 2026-08-07 敌方技能 prefab 键解析 706/711 -> 全覆盖

之前的 missingPrefabKeys (5 个) 全部追溯完毕，其中 4 个是命名变体或本地提取，1 个确认无 prefab：

- cut_tree / cuttree -> CutTree：旧版游戏 GameObject 名 cuttree，新版改名 CutTree
  (enemy_1512_mcmstr 伐木，bb max_cut/max_cnt=1，cd 30)。loader.PREFAB_KEY_ALIASES 双写法都别名到当前名。
- BoomAll -> DeathBoomAll：克丽斯腾 skill3 热寂（全场爆破），prefab 本体叫 DeathBoomAll。
- Shining / Countdown：数据库 prefabKey 与 GameObject 名无法匹配，但当前版
  enm_pfb_33.ab 内实际存在这两个能力的完整组件集（用 ArknightsStudioCLI
  -m export -t monoBehaviour 导出，按 m_GameObject pathID 分组）。已提取到
  Ark_emulator/ark_emulator/data_enemy_prefab_overrides.json，loader._prefab_override 优先查询：
  - Shining：汉科/大总统汉科照明弹（cd 15），Ability._projectileKey=
    projectile_enemy_shdbjg_shining（弹道速 10 格/s，本地已有），_activeBuffs
    含 enemy_shsmok_disable（驱散烟雾/剔隐蔑迷彩）。
  - Countdown：决胜时刻球 10s 倒计时 buff 应用器（enemy_mupenb_start_count_down）。
- DownAnim：德莱昂/征服者德莱昂的下降动画（bb cooldown=25, cooldown_fix=0.5）。全量
  搜索导出 JSON 后确认无这个 GameObject/字段值，它是动画状态引用
  （与 Fly/Boom/Exit 组成飞行状态机），并非序列化 prefab。

工程实现（loader.py）：
- PREFAB_KEY_ALIASES 别名表；prefab_components/prefab_ability_fields 先别名再查询。
- synthesize_skill_entry(enemy_key, skill)：当 skill_behavior_catalog 缺少某技能时，从完整
  prefab 编目合成同样 schema 的条目（EnemySkill参数/abilities/trigger/buffKeys），
  enemy_skills() 自动追加，EnemySkillController._catalog_entry 无需改动即可匹配。
- data_enemy_prefab_overrides.json：本地提取的组件（同 skill_prefab_catalog schema）。

原始提取物件：Ark_emulator/data_raw/enm_pfb_current（当前版 35 个 AB）与
enm_pfb_json（ArknightsStudioCLI 导出的 MonoBehaviour JSON）。

- 测试：tests/test_enemy_prefab_aliases.py 5 用例（别名解析、合成 entry、
  Shining/Countdown 本地 override、新敌人 spawn 时技能赋值）。


## 2026-08-07 干员模组（X/Y 模组）框架

- squad 配置支持每个干员携带模组：
  moduleId + moduleLevel（或嵌套 module {id, level}）。
- 属性加成（数据驱动）：loader.module_stat_bonus 读 module_stats.json
  （496 个模组），部署时按等级 phase 添加
  max_hp/atk/def/attack_speed/magic_resistance/cost/respawn_time/block_cnt。
- 天赋升级（数据驱动）：loader.module_talent_upgrades 解析 battle_equip.json
  的 phase 候选（每个天赋两个候选：基础值 + 潜能增强版，
  潜能 >= 4 时取后者），按基础天赋的 blackboard 键顺序覆盖值。
  例：酒神 Y模组坠梦 lv3 = attack_speed -20（pot4 -24）/value 90，
  直接流入敌方侧 aura 与普攻神经 EP 扣算。
- 快照：Operator.to_dict 新增 module 字段（{id, level}）。
- 已知边界：模组的特性追加（如酒神 X模组对精英/领袖
  元素损伤 +18%）与额外效果（烛煌 X模组爆炸后 10s 攻击力+5%、
  Y模组受击反击 + 复活回 SP）尚未通用化，需按干员单独接线。
- 测试：tests/test_modules.py 4 用例（属性加成、快照、嵌套配置、
  天赋黑板覆盖与 aura 流动）。


## 2026-08-07 信赖加成 + 模组特性接线

- 信赖加成：squad 可携带 trust (0-200)，部署时依
  trust_prts.json 的 200%满信赖值线性拆算（每项向下取整）。
  例：烛煌 trust200 -> atk +90，trust100 -> +45；酒神 trust200 -> maxHp+300/atk+40。
  快照带 trust 字段。
- 模组特性（首个通用接线）：Enemy 新增 level_type
  (0 普通 / 1 精英 / 2 领袖，来源 enemy_database.levelType)。
  BuffSystem.update_ep 增加源侧模组特性钩子：酒神
  Y模组 (uniequip_002_phatm2) 对精英/领袖敌人造成的元素损伤
  +18%（battle_equip phase-1 描述已确认）。
- 测试：tests/test_modules.py 6 用例（属性、快照、天赋黑板、
  信赖线性、精英/领袖 元素损伤 +18%）。


## 2026-08-07 当前版敌方 prefab 目录重建 + trigger 解析

- ArknightsStudioCLI -m export -t monoBehaviour --export-asset-list xml 导出当前
  enm_pfb (2026-08-01) 的 49800 个 MonoBehaviour JSON + assets.xml；assets.xml 的
  Container 提供 prefab 名（dyn/battle/prefabs/enemies/<name>.prefab），
  PathID 提供组件引用解析钥。
- 生成 Ark_emulator/ark_emulator/data_enemy_prefab_catalog_current.json
  （2075 prefab / 49800 组件 / 41.7MB，含 pathID）；loader.prefab_catalog
  将其合并到 June 基础目录上（同名替换 + 新增敌人键），
  总键 4590，并加进程级缓存避免重复解析 80MB。
- synthesize_skill_entry 的 trigger 解析改进：EnemySkill._trigger 引用
  在技能 prefab 内未命中时，回退到该敌人自己的 prefab
  （当前目录含 pathID）。例：汉科 Shining 的 trigger =
  目标选择器 {minTargetNum:1}（非时间触发），说明
  当前的优先级调度模型与游戏数据一致；
  光照弹的 15s 周期来自技能 cooldown，而非特殊触发。
- 新敌人预存在：enemy_2138_shdbjg (31)、enemy_2140_shsgzd (47)、
  enemy_4064_mupenb (23) 等按敌人键可查询；德莱昂的 3 个
  EnemySkill trigger 组件仍为空字段（类型树被剥），
  DownAnim 仍无可解析 prefab。
- 原始提取物：Ark_emulator/data_raw/enm_pfb_current + enm_pfb_full
  （assets.xml + prefab_map.pkl）。


## 2026-08-07 周期 buff 触发间隔精度修复

- 问题：BuffSystem.apply 用 _trigger_spec 的 1s 回退覆盖了
  materialise_buff 已设置的真实 triggerInterval（真实分布
  0.05/0.1/0.2/0.5/1/2/5s等），导致 DoT/周期效果按错误节奏触发。
- 修复：
  - materialise_buff 同时传递 triggerInterval、firstTriggerInterval、triggerCnt
    到 entry（_first_trigger_interval / _trigger_max）。
  - BuffSystem.apply 保留已提供的 _trigger_interval，仅在缺失时
    回退到模板 1s；waitFirstTriggerInterval=1 时设置
    _first_trigger_remaining（首次触发延迟），triggerCnt>0 时设置触发上限。
  - BuffSystem.update 按首次延迟 -> 固定间隔 -> 触发上限执行。
- 测试：tests/test_buff_triggers.py 2 用例（首次延迟+间隔+上限精确
  时间线；materialise_buff 字段传递与 apply 保留）。


## 2026-08-07 强攻手/推击手：同时攻击所有阻挡敌人【已实现】

- **特性**（PRTS 强攻手/推击手）：普攻一次挥击命中自身阻挡的**所有**敌人；
  没有阻挡任何敌人时原地待机（不进行普攻）。
- **数据**：data_class_traits.json 的 subprofession `centurion`（强攻手）、
  `pusher`（推击手）新增 `attackAllBlocked: true`。
- **实现**：
  - traits.py 新增 `TraitSystem.attack_all_blocked()`（读 attackAllBlocked flag）。
  - battle.py `_operator_attack(..., targets=...)`：`targets is None` 时若 trait
    生效则自动取 `op.blocked_enemies`（存活且 `blocked_by is op`）作为目标集合，
    在前摇开始时快照；pending attack 记录 `targets` 列表。
  - battle.py `_pending_attack_live()`：每个 tick 剪除已死亡目标，全部死亡则
    取消本次攻击；命中帧到达时 `_resolve_operator_attack` 对每个存活目标各结算
    一次近战伤害/弹道，并逐目标触发 trait on_hit 与技能 attack@* 效果；
    ATTACK 事件携带 `targets`（所有命中目标 id 列表）。
  - `_update_operators`：attackAllBlocked 干员在攻击计时归零时以被阻挡敌人为
    目标发起攻击，无阻挡则 0.1s 后重试（待机）。
- 行为细节：SP/弹药等按**攻击动作**结算一次（不是按目标数）；目标在前摇期间
  死亡会在命中帧被剪除，不影响其余目标。
- 测试：tests/test_attack_all_blocked.py 4 用例（强攻手双目标同时命中+事件、
  推击手双目标、无阻挡不攻击、命中帧前目标死亡剪除）。

## 2026-08-07 子职业特性补全：撼地者/阵法术师/解放者【已实现】

- **撼地者（hammer，奥达等）**：普攻命中主目标后，对目标周围
  `attack@ability_range_radius`（1.0，即切比雪夫距离 1 格）内的其他敌人
  造成 `attack@atk_scale_2`（0.5）倍攻击力的群体物理伤害；主目标正常结算
  全额伤害。`_hammer_splash` 挂在 trait on_hit 链上，事件类型
  `attack/hammer_splash` 携带溅射目标列表。
- **阵法术师（phalanx，蜜蜡等）**：不处于攻击前摇（`_pending_attack` 为空）
  时防御力 ×2（mul +1.0）、法术抗性 +20（add）；进入攻击前摇立即解除，
  命中后恢复待机态重新生效。逐帧由 `phalanx_sync()` 同步属性修饰器
  `trait_phalanx_idle`。
- **解放者（librator，骋风等）**：无技能激活时阻挡数强制为 0（属性修饰器
  `trait_librator_idle`，additive -base_block，因 Attributes 会跳过 0 值
  修饰器故不用 final_mul 0）且不进行普攻（攻击门控：无 active 技能时
  attack_timer 保持 0.1s 待机）；攻击力在 `max_stack_cnt`（40s）内线性
  提升至 `atk`（+200%），技能激活时锁定当前提升值并恢复阻挡/攻击，
  技能结束时重置为 0 重新蓄力。逐帧由 `librator_sync(skill_active, dt)`
  维护 `trait_librator_ramp` / `trait_librator_idle`。
- 数据：data_class_traits.json subprofession 新增 `hammer`/`phalanx`/
  `librator` 条目（34 个子职业）。
- 测试：tests/test_subclass_traits.py 4 用例（溅射命中相邻敌人且远处不受
  影响、待机双防/前摇解除/恢复、待机不攻击且阻挡 0、蓄力 2s +10% ATK +
  技能开/关状态切换与重置）。


## 2026-08-07 ??????? + ???? + x-N ??????????

- ????bard?U-Official ???????????????????
  ?????x-4=3x3??? ?? = ????? x atk_to_hp_recovery_ratio
  ?0.1???????PRTS ?????????“??????”????
  ????????????????? hpRecoveryPerSec ???????
  ?key trait_bard_aura:<instId>???????????????????
  ???????????????/??? bard_aura_clear() ???
- ???????_tick_hp_regen(dt) ???????/????
  hpRecoveryPerSec ?? HP??? heal_free????????????
  ???????/????????????????????
- x-N ?????range_offsets_rotated ??? x-N ????????? N
  ?????????? range_table ??????x-4=3x3“??8?”?
  PRTS ??????????????????????????????/
  ????/??????????? 3x3??
- ???tests/test_bard_trait.py 5 ??????/???????/????
  ????/???????/????????test_ray_kit ???????
  ??? 3x3 ????????? 43 ?????????


## 2026-08-07 ????????????

- ????mystic???/???/??/??/???/?????????
  ???????????????????? bb times??? 3????
  ???????????? + ????????????????????
  ?????????????
- merge_cnt??? times=9/merge=3??? merge ????????????
  ??? = ?? x ??????????? 1 ??
- ???_operator_attack ?? hits/hit_scales ???pending ????
  ??????? apply_damage?????? spawn ??????????
  ?? mystic_attack_tick?trait ??????????????????
  ???????????????
- ???tests/test_mystic_trait.py 4 ???????? 3 ?/?? 1+3 ?/
  ?? 9 ? 3 ???=10x/????????

## 2026-08-07 ???????????

- ????? HateSystem.operator_target ?????????????
  ?????legacy ??????????????????????
  ?return None????????? main_01-01 ???-??????
  ????? _next_map???????????? checkpoint????
  (3,5) ??????? (2,5)???? 3 ???? (2,5) ???????
  ????????????????/????????
- ????????? AI/?????????????????????
  next ??????????targeting.py ?????? flip ???
  ??? candidates ??????? S3 ?????/????????
  ?????


## 2026-08-07 ????stalker?+ ????????????

- ??????/??/??/??/????/?????bb prob=0.5??
  - ??????????y-1??????attackAllInRange???????
    ???? = ??????????????
  - 50% ???????????? damageHitratePhysical/Magical ? 50
    ??????apply_damage ????????????????????
    ?????????/???????
  - ???? -1 ?????????tauntLevel -1???????????
- ????executor??/?/??/???/??/??????/??R??/???/
  Misery/THRM-EX??PRTS ??“???????”????????
  respawnTime??/?? = 18s?THRM-EX 200s???????????
- ???tests/test_stalker_trait.py 4 ?????/?????/??/????
  ?? 45 ?????????


## 2026-08-07 ????/????/?????????

- artsfghter????????/??/???????????????
  ???????????artsprotector????????/??/????
  ?????? data_class_traits damageType=MAGICAL ?????
- splashcaster????????/??/???/????/???????
  ???????????????? 1 ??????????????
  ??????? attack/splashcaster_splash??_hammer_splash ???
  _splash_hit?????? 0.5x / ?????? 1.0x?????????
  ??????
- ??????executor?????????????? respawnTime=18 ????
  lord????atk_scale ?? traits ????sword?????? SP ??
  ????
- ???tests/test_arts_subclasses.py 3 ?????????????
  ??+??????


## 2026-08-07 ??? + ?????????

- ????blessing???/???/??/??/?????????????
  ?????????????????????????????????
  ?????? = ??? x heal_scale?0.75??????? heal ???
  ????????????????_resolve_operator_attack ?????
  ? blessing ? heal_scale?
- ?????primcaster???/??/Miss.Christine/??/????PRTS
  ????“?????????????????”??????/????
  ???????????????? DoT???/???????????
  ????????????????/??????????? damageType
  MAGICAL?
- ???tests/test_blessing_trait.py 2 ????????????/??
  ????? 0.75x ?????????


## 2026-08-07

## 2026-08-07 巫役 ritualist 天赋套件

- data_class_traits 新增 ritualist 子职业（法伤，可造成元素损伤）。
- 凛视 threye T1：每次伤害输出附带凋亡 EP = ATK × ep_damage_ratio（游戏模板 threye_t_2，部署聊听 buff + ON_OUTPUT_DAMAGE 触发）。注：原文案限定【探索者的银洼止境】模式，模拟器现按全场生效处理。
- 盟约·辅助干员 pithst T1：攻击同时附带神经+灼燃+凋亡 EP，各 = ATK × ep_damage_ratio（模板 pithst_t_1）。
- PhonoR-0 T1：部署后 40s 内每次攻击附加固定凋亡 EP（attack@dark_damage_value）；并对攻击范围内所有敌人施加法术脆弱+元素脆弱（伤害放大 damage_scale）。
- 波卜 bobb T1：对每个敌人首次攻击时上烧燃 EP DoT（ATK × ep_damage_ratio_talent/s，5s，模板 bobb_t_1[damage]）。
- 塑心 cello T1：每秒对攻击范围内敌人造成 ATK × ep_damage_ratio 凋亡 EP + 0.2s 停顿（E1+，模板 cello_t_1[core]）。
- 伯塔尼 botany T1：任意场上敌人侵蚀爆发时攻速 +attack_speed 叠层（最多 max_stack_cnt=3；模板 botany_t_1 未含距离门检，按模板全场生效）。
- 修复 buff_templates ApplyElementDamage 等节点目标解析实参错位：_source_unit 把 source 传到 target 形参，导致 MODIFIER_TARGET 解析成持有者，EP 加到了干员自身。
- 测试 tests/test_ritualist_talents.py 6 用例（普攻附 EP、固定值窗口、首击 DoT、范围光环停顿、爆发叠层）。
## 2026-08-07 行医（wandermedic）元素回复特性【已实现】

- 分支特性：每次治疗行为（普攻/技能/buff 模板治疗）同时回复目标全种类元素损伤（神经/侵蚀/灼燃/凋亡四条 EP），每条 = 源 ATK × ep_heal_ratio（特性 bb 0.5，WDM-X 模组 0.6），各自钳制在 0 以上；爆发冷却中的 EP 条不回复，并对外发出 ep_recovered 事件。
- 选敌：行医可选中满血但有元素损伤的友方（普通医疗不行）；优先级为生命比例最低 > 当前损伤元素条最严重（最接近爆发）；禁疗目标不可选，且整次治疗（含 EP 回复）被阻断。
- 引擎：BuffSystem 新增 recover_ep（update_ep 负值分支加 0 下界、不触发伤害观察者、记录最近损伤元素）；ApplyElementHeal（ep_heal_all）改为回复全部 EP 条；选敌在 targeting.operator_target 按行医规则扩展候选池。
- 测试 tests/test_wandermedic_trait.py 9 用例（特性参数/全条回复/满血可选/满血无 EP 不选/优先级/禁疗/不受特性影响跳过/非行医不回复/钳制到 0）。
## 2026-08-07 脆弱（Fragility）系统 + PhonoR-0 天赋接入【已实现】

- 伤害管线：目标携带脆弱 buff 时按类型放大最终伤害——weak[magic] 放大法术、weak[phy] 放大物理、weak[ep] 放大元素损伤（EP 量）、通用 weak 放大所有 HP 伤害（物理/法术/真实）；多个脆弱 buff 相乘。
- PhonoR-0（char_4136_phonor）T1：部署后 40 秒窗口内，攻击范围内所有敌人获得法术脆弱+元素脆弱（bb damage_scale = 1.03/1.05/1.08/1.10，对应 3%/5%/8%/10%）；buff 寿命 1 秒逐 tick 刷新，离开范围/窗口结束/撤退后自动消失。
- 对应游戏模板：phonor_t_1[aura] → weak[magic][inf] / weak[ep][inf]（buff 表黑键 damage_scale[mag] / damage_scale[element]，值取自天赋 bb damage_scale）。
- 测试 tests/test_weakness_system.py 9 用例（范围施加/范围外不加/法术放大/物理不受影响/元素 EP 放大/窗口过期/通用 weak/物理脆弱/相乘叠加/撤退清除）。


## 2026-08-07 子职业机制补齐：geek / unyield / fortress / underminer【已实现】

- 怪杰 geek（阿、空构）：每秒流失 maxHp × hp_ratio（特性 bb 0.01 = 1%），不致死最低保留 1 HP；走 battle._trait_tick 累积器，发出 trait_hp_drain 事件。
- 不屈者 unyield（火神、露托等）：部署时挂永久 HEAL_FREE（无法被友方治疗）；自治疗路径需跳过禁疗（ignore_heal_free）。
- 要塞 fortress（灰毫、号角、火哨）：不阻挡时远程群体物理攻击（目标地块 3x3 满发 ATK，雷氏距离 1.0）；阻挡时对阻挡目标近战单体攻击。走 _operator_attack(fortress_splash=True) + _resolve_operator_attack 命中时计算满发，事件 type=fortress_splash。
- 削弱者 underminer（初雪、狡狸、海拿等）：data_class_traits damageType=MAGICAL，普攻为法术伤害。
- 测试 tests/test_more_subprofessions.py 6 用例（geek 损血比例/保底 1HP、unyield 禁疗与跳过、fortress 满发/调度驱动/近战单体、underminer 法伤视防）。


## 2026-08-07 dollkeeper?傀儡师?替身机制 + guardian 治疗验证【已实现】

- 傀儡师 dollkeeper（风丸、贝娜、维荦）：受到致命伤时不撤退，切换成<替身>作战（阻挡数=0、不嘲讱）；有替身 token 时（风丸 纸偶 token_10022_kazema_shadow）统代替换为 token 属性；持续 trait.duration（20s）后本体回归（满血、SP=0）；替身期间再次致命则撤退。实现在 battle._try_dollkeeper/_doll_restore + apply_damage 致命钩子，发出 doll_state 事件（swap/restore），快照新增 doll 字段。
- 守护者 guardian（临光等）：技能治疗友方已由技能系统通用 heal_scale 路径覆盖（临光 S1 急救：AUTO、heal_scale 1.1@L1/1.8@M3、ct 3s），无需分支特殊处理。
- 测试 tests/test_more_subprofessions.py 新增 dollkeeper 替身/还原/替身期死亡 + guardian S1 治疗友方共 3 用例（该文件现共 11 用例）。


## 2026-08-07 reaperrange?收割者（远）?+ 快照序列化修复【已实现】

- 收割者（远）reaperrange（松果、送葬人、奥斯塔、假日威龙陈等）：普攻命中攻击范围内所有敌人（attackAllInRange），对自己前方一横排的敌人伤害提升至 150%（bb atk_scale=1.5，按朝向判定前方一横排）；实现为 _operator_attack 计算 target_scales 并行带入命中事件。
- 快照序列化修复：Unit.base_to_dict 的 buff 字段直接 dict(b)，而游戏流程中 buff.source 是单元对象（如砾部署天赋 buff），导致 LiveServer /snapshot JSON 序列化 TypeError。新增 _json_safe 递归清洁（单元引用转 inst_id），快照始终可序列化。
- 端到端取证（审计用）：选关卡 level_id + stage_to_level、自定义编队 squad phase/level/potential、自定义关卡敌人 custom_enemies 属性覆盖、自定义关卡 build_level（地图+波次）、实时快照（敌人位置/血量/攻击/减益、干员 buff/doll/trait）、LiveServer /snapshot 全部 PASS。
- 测试 tests/test_more_subprofessions.py 新增 reaperrange 全范围+前排 150% 与快照序列化共 2 用例（现共 13 用例）。


## 2026-08-07 剩余分支数据标记 + 全量回归与敌方 boss 行为取证

- 分支标记：陷阱师 traper（可对空、部署陷阱）、炼金师 alchemist（可对空、投掷炼金单元）、侦察者 skywalker（飞空 liftoff）、工匠 craftsman（部署装置）已入 data_class_traits；具体行为走现有技能/token/地块系统，待逐干员集成测试。
- 全量回归：51 个测试文件全部在本会话跑过（359 项集合）均绿。
- 敌方 boss 行为取证：克丽斯腾 enemy_1543_cstlrs 刷新后经通用敌方技能管线正常施放（BecomeStar2 @0.5s、Reborning @5.5s），DeathBoomAll 预设已通过 loader 别名解析。
- UI 取证：web 页面加载、关卡搜索/选择、squad/custom enemies JSON 配置、实时地图、LiveServer /snapshot 均通过。


## 2026-08-07 skywalker?侦察者?飞空阻挡飞行敌人【已实现】

- 侦察者 skywalker（云迹/蒂比/予愿安杰莉娜）：技能激活期间处于飞空（liftoff，判定为活跃技能 blackboard 含 attack@height_offset），此时可以阻挡飞行敌人（最多 2 只；普通干员仍不可阻挡飞行敌人）；飞行敌人默认挂 BLOCK_FREE（字段 3），仅 liftoff 的 skywalker 绕过该限制。技能结束后已阻挡的飞行敌人自动释放（_update_blocking 释放逻辑）。
- 测试 tests/test_more_subprofessions.py 新增 skywalker 飞空阻挡/阻挡释放 1 用例（现共 14 用例）；test_traits 的飞行不可阻挡回归保持绿。


## 2026-08-07 traper?陷阱师?夹子部署与踩踏触发【已实现】

- 陷阱师 traper（罗宾/霜华/钼铅）：技能释放时 buff 模杰 trigger_charge_token 的 RechargeToken 节点现在攻击范围内最近的可部署空地块部署陷阱 token（按干员代号匹配 token_*_mine，例罗宾 token_10013_robin_mine）；敌人踩上陷阱地块触发：物理伤害 = atk × atk_scale（束缚夹子 2.0、弹射夹子 2.3）+ 束缚（UNMOVABLE，constraint 秒）/弹射（force 推冲），触发后陷阱消耗，发出 trap_fired 事件。
- 实现：BuffTemplateEngine._try_deploy_trap + _n_RechargeToken 兼容旧 SP 充能路径（非陷阱干员仍走 SP 充能）；battle._trigger_traps 每 tick 检测敌人与陷阱 token 同地块触发。
- 测试 tests/test_more_subprofessions.py 新增 traper 部署+触发 1 用例（现共 15 用例）；RechargeToken SP 充能回归保持绿。


## 2026-08-07 alchemist 炼金单元 + craftsman 装置部署【已实现（部分）】

- 炼金师 alchemist（锡人）S1 “老科利”：通用技能管线已覆盖：释放后目标获得 tinman_s_1[dot] + attr_down[atk] buff（atk -15%）并受到周期伤害（atk × atk_scale 0.3）。现实为直接施加（非弹道落点区域），尚未完全匹配游戏“弹道人落点生成持续区域、干员离场留存”的细节。
- 工匠 craftsman（罗比萈塔）S2 全自动造型仪：RechargeToken 按干员代号通用匹配 token_*_<code>_* （罗比萈塔 -> token_10018_robrta_mach），技能释放时在攻击范围内部署装置 token；陷阱师夹子同步覆盖。
- 测试 tests/test_more_subprofessions.py 新增 alchemist DoT/debuff + craftsman 装置部署共 2 用例（现共 17 用例）。
- 尚存缺口：锡人 S2 治疗区域（hp_recovery_per_sec_ratio 的友方治疗区域）未验证生效，待下步调研。


## 2026-08-07 alchemist 炼金单元落点区域【已实现（锡人 S1）】

- 炼金单元区域：技能 blackboard 含 projectile_range 时，弹道命中后把项目版弹道 buff（如 tinman_s_1[dot]）施加给落点周围 Chebyshev 距离 <= projectile_range 的所有单元（敌方/友方由 buff 模杰内部分流）；并缓存 cached_atk = 施放时 atk × atk_scale，供 NoSourceDamage DoT 结算（锡人 S1 周期伤害 = atk × 0.3/s）。
- 实现：operator_skills._fire_burst 的弹道回调支持 projectile_range 区域应用 + cached_atk 写入 buff blackboard。
- 测试：test_more_subprofessions 锡人 S1 区域测试覆盖主目标+邻居 DoT、远敌不受影响。
- 尚存缺口：锡人 S2 的预设抽取缺 _projectileKey/_activeBuffs 字段（只有 AttackAbility + selector），区域治疗无法从当前数据接线；需重新提取该预设或手动补充。


## 2026-08-07 锡人 S2 区域治疗分流（IfTargetSide 节点）【已实现】

- 问题：炼金师锡人 S2 “大拉里”落点区域（projectile_range=2.0，持续 projectile_delay_time=10s）
  中，tinman_s_2[buff] 的 IfTargetSide 节点在模拟器没有实现 handler，run_actions
  对其按“跳过”处理且不改变 gate，导致 ENEMY 分支的
  NoSourceDamage 对友方也执行（友方每秒吃 189 法伤而非回血）。
- 修复：buff_templates.py 新增 _n_IfTargetSide：解析 _targetType（BUFF_OWNER）后按
  _sideMask=ALLY/ENEMY 判定阵营（side 0=敌方，1=我方），不匹配则
  gate=False 中断后续节点。与 AlwaysNext 纯透传配合后：
  - ON_BUFF_START：ALLY 获得 HP_RECOVERY_PER_SEC = cached_atk × hp_recovery_per_sec_ratio（atk×0.5×0.1/s）；
  - ON_BUFF_TRIGGER：ENEMY 受 cached_atk 法伤（经法抗，实测 151.6 = 189.5×(1-20%)）。
- 验证：友方回血（无区域法伤事件）、敌方受伤、敌方无回血修饰。
- 测试：test_more_subprofessions.py 新增 test_alchemist_s2_zone_heal_vs_damage
  （18 项全过）；受影响面回归 buff_templates/buff_triggers/operator_skills/
  skill_system/sp_mechanics/projectiles 共 61 项全绿。


## 2026-08-07 敌方 boss 行为验证（霜星等）+ ArcticBlast atk_scale 修复【已实现】

- 冰霜与真正的霜星：enemy_1042_frostd “寒霜”在数据库与关卡层均无技能（skills=[]、
  enemyDbRefs useDb+level0+无 overwrittenData），仅普攻——这是数据事实而非缺口。
  真正的“霜星”Boss 是 enemy_1505_frstar（ArcticBlast / IceShield）和
  enemy_1510_frstar2 “霜星，‘冬痕’”（5 技能）。
- 验证链（模拟器实测）：
  - 技能解析：IceShield（priority 2 / cd 30s / max_cnt 2）、ArcticBlast（priority 1 / cd 8.5s /
    atk_scale 1.5 / duration 8s / attack_speed -50 / range_radius 2.5）；冬痕 5 技能全部解析。
  - 时序：第一次 ArcticBlast ~11.6s（首冷却 8.5s+攻击计时相位），
    第二次间隔约 11.1s（cd+1 个攻击间隔+施放时长，游戏中敌人技能由攻击计时门控）；
    IceShield 在 ~30s+ 后施放。
  - 效果落地：ArcticBlast 对目标造成 atk×1.5 法伤，并给目标挂
    arctic_blast buff（攻速 -50）持续精确 8s=240 tick。
- 修复的真实 bug：EnemySkillRun._execute_effects 原来只要 prefab 有
  _damageType 就用 prefab._atkScale（1.0 默认值）覆盖 blackboard的 atk_scale（1.5）。
  现改为仅当 prefab atkScale 非默认 1.0 时才覆盖；否则优先 blackboard。
- 测试：新增 tests/test_boss_behavior.py 4 用例（技能解析 / ArcticBlast 施放循环
  与效果 / IceShield 施放 / 冬痕 5 技能）；受影响面回归
  skill_system/enemy_prefab_aliases/enemy_buffs/attack_timing/enemy_range/boss_behavior/displacement
  共 46 项全绿。


## 2026-08-07 UI 点击流自动化【已实现】

- 前端页面点击地图部署/点击干员释放技能/撤退，
  都是调用 LiveServer POST /action（deploy/withdraw/skill/pause/resume/step）
  。新增 tests/test_ui_click_flow.py 用与前端相同的 HTTP 点击流驱动模拟器：
  - step 充费 -> deploy 芬（instId 返回）-> skill（SP 未满返回 not_ready）
    -> withdraw（redeployIn 计时）；每步用 /snapshot + /events 验证。
  - 阿米娅 S2（手动）：SP 满时点击技能 -> skill_cast
    事件（skchr_amiya_2）+ snapshot.activeSkill（持续 25s）；
    游戏真实的自身眩晃 10s 也在 snapshot buffs 中可见。
  - 页面加载：/ 含 click-to-deploy/withdraw handler，/editor 含 buildLevel。
- 测试：3 用例全过（部署/技能/撤退点击流、手动技能施放、页面加载）。


## 2026-08-07 Boss 批量行为验证 + 共享 prefab 污染修复【已实现】

- 全量扫描：264 个有技能的领袖/首领敌人，catalog 匹配 100%（仅 5 个已知缺失由 loader 别名/override 合成：BoomAll->DeathBoomAll、Shining、DownAnim 动画引用）；946 条 Boss 技能 catalog 条目中 12 条 abilities 为空（1.3%，均有 blackboard/buffKeys，效果由 prefab 动作节点承载）。
- 批量施放冒烟（10 个代表性 Boss，60s 窗口，技能经解析->冷却/优先级->选目标->施放全链路）：塔露拉 4/4、爱国者 throwspear[Rage]（近战需相邻）、W C4、浮士德 CriticalHit+SummonBallis、泥岩 RefreshShield+occupy、霜星冬痕 4/5、“进化的本质” 11 技能、岁相 7/7、克丽斯腾 BecomeStar/BecomeStar2/Reborning、蔓拉 Reborn+SelfStun——全部成功。
- 修复真实 bug（共享 prefab 污染）：提取目录把多个敌人同名的 prefab 合并到同一 key（如 “Invincible” 34 个组件含 telex/faust/ymmons/xbmoth 等 10 个 CAB），EnemySkillRun 施放时会收集所有敌人的 buff 组件。新增 DataStore.enemy_prefab_components / enemy_prefab_ability_fields：按敌人代号匹配 buffKey 定位所属 cabin 后过滤组件；EnemySkillRun 改用 enemy 限定版本。
- 全量抽查：291 个共享 prefabKey、1065 次使用，owner buff 组件过滤后零丢失。
- 测试：tests/test_boss_batch.py 11 用例（10 Boss 施放 + 共享 prefab 过滤）；受影响面回归 43 项全绿。


## 2026-08-07 共享 prefab 过滤策略演进 + 全量回归 382 项【已实现】

- 过滤策略三步演进：
  1) cabin 过滤（按 buffKey 代号定位 cabin）：对独用 prefab 有效，但对超大共享 prefab（如假想敌技能 “1” 257 组件、伤害类型组件在别的 CAB）会过度剪裁。
  2) 按 buffKey 代号直接过滤 + 保留无 buff 能力组件：修复了伤害类型丢失，但发现两类误删：变体敌人（enemy_9013_acstmk_2）的代号提取带了变体后缀；当前敌人使用继承/共享命名的 buff（mpbarr 用 mpprme_spawn_mark）时被误删。
  3) 终版：代号提取去变体后缀（_2/_3/_a...）；当 prefab 中无法归属到当前敌人的组件时回退保留全部（避免误删继承命名 buff）；能力容器组件（_selfOption/_startEvent/_endEvent/_forceFinishBuffOnCastEnd）保守保留。
- 测试修正：test_damage_type 的 MAGICAL/PHYSICAL 用例原本基于共享 prefab 合并顺序的“碰巧”（dspred “1” 的 dt=2 组件实际属于 acduml），改为用独有 prefab：霜星 ArcticBlast（MAGICAL）、vtsk MultiCombat（PHYSICAL）、skzamy AOEAttackInit（TRUE）。
- 全量回归：54 个测试文件 382 项全绿（含新增 test_boss_batch 11 项）。


## 2026-08-07 全量 Boss 施放扫描 + 近战选目标距离修复【已实现】

- 全量扫描：264 个有技能的 Boss/领袖，在无波次自定义关卡 + 相邻干员 + SP 满 + 90s 窗口下，255 个（96.6%）成功施放至少一个技能；剩余 9 个（ristar/dqreid Rush/manfri 阶段技能/lrdead_2 Laser 触发型/skzfdd 阶段/wangw Motion/cosgia 进场动画/pilot 飞行状态机）全部是 cd≥9999 或特殊触发的阶段/进场/状态机技能，90s 静止场景不施放属正确数据行为。
- 修复真实 bug（近战选目标距离）：
  1) _find_target 用技能 bb 的 range_radius（0.8）作为选目标距离，辑近相邻格（1.0）都选不到——实际上 bb range_radius 是效果半径（溅射/AOE），选目标应跟随敌人攻击范围；现改为 max(技能 range_radius, 攻击范围)。
  2) resolve_attack_range 对 0.3~0.8 的正值近战半径（66 个敌人）原样返回，导致近战选不到相邻格；现统一按 1.5 处理。
  3) 确认 SP 门控正确：Bombard（SP 50）在 SP 低时不施放，满 SP 后施放（之前扫描的 NO_CAST 部分是 SP 自然回复未到。。
- 测试：test_boss_batch.py 改用无波次自定义关卡（消除主线关卡波次干扰），11→16 用例；全量回归 54 文件 387 项全绿。


## 2026-08-07 模组额外效果验证 + 数据层限制确认【已实现】

- 烛煌 X 模组（uniequip_002_blaze2）熔点引爆：通过 module_talent_upgrades 黑板上调已生效——灸燃爆发时元素伤害 ep_damage_scale 3.5→3.9、回血 hp_ratio 0.12；实测回血=maxHp×0.12、爆发目标灸燃 EP +=atk×3.9（无模组 atk×3.5）。
- 烛煌 Y 模组（uniequip_003_blaze2）绝处重燃：倒地回血率黑板上调 0.03→0.04（pot<4）。
- 数据层限制确认：前置条件性 Boss 技能（行星碎屑/火与钢 Rush/曼弗雷德阶段/引火的死魂灵 Laser/执白者 Motion/浮袭者飞行状态机）的 trigger 组件字段在当前解包数据中为空（pathID 引用未命中或字段被剥）；敌方 prefab 的 xLua 动作节点 SerializedState 大量为空（"[]"）——这些都是数据不可驱动项，需更新的提取或关卡级数据。
- 测试：test_modules.py 新增 X 熔点引爆增强 + Y 绝处重燃增强 2 用例（8 项全过）；全量回归 54 文件 389 项。


## 2026-08-07 关卡 runes（标签/危机合约）支持【已实现】

- 之前 stage_sim_bundle 的 runes 字段（~70 种关卡标签）被解析但 battle 完全未应用。现实现通用路径：
  - 全局：gbuff_lifepoint/global_lifepoint（生命点）、global_initial_cost_add/cbuff_initial_cost（初始费用）、cbuff_max_cost（最大费用）、global_cost_recovery_mul/cbuff_cost_recovery（费用回复）；
  - 敌方：enemy_attribute_mul/ebuff_attribute/enemy_attribute_add（属性乘/加）、level_enemy_replace（敌人替换）；
  - 我方：char_attribute_mul/cbuff_attribute/char_attribute_add（干员属性）、char_cost_mul/cbuff_char_cost/char_cost_add（部署费用）、char_respawntime_mul/cbuff_respawn_time/char_respawntime_add（再部署）、global_forbid_location（禁止位置）、cbuff_excluded/char_exclude（干员排除）、global_squad_num_limit（编队上限）；
- 难度可配置：Simulator(rune_difficulty=1|2|15)，默认 NORMAL(1)——游戏主线默认难度不应用 FOUR_STAR 的 runes；FOUR_STAR(2) 时 main_01-01 生命点 10→11、敌人属性 ×1.2。
- 测试：tests/test_level_runes.py 5 用例（生命点/敌方属性乘区、干员费用乘区、禁止位置、初始费用与最大费用、干员属性乘区）；全量回归 55 文件 394 项全绿。


## 2026-08-07 runes 继续扩展：部署数/攻击范围/重量/技能黑板【已实现】

- gbuff_placable_char_num / global_placable_char_num_add：可部署干员数调整（FOUR_STAR main_01-01 8→4）。
- enemy_attackradius_mul / ebuff_attack_radius：敌方攻击范围乘区（无范围/近战默认 1.5 先落到 1.5 再乘，实测 gopro 1.5×2=3.0）。
- ebuff_weight / enemy_weight_add：敌方重量加区。
- enemy_skill_blackb_mul/add：按敌人+prefabKey 过滤应用到技能 blackboard（实测 ltsmer_2 charge sp -2→-4；ltrock_2 Boom boom_value_ally 800→1600）。
- enemy_talent_blackb_mul/add / ebuff_talent_blackb_mul：键格式 '<skill>.<bbKey>'（实测 Boom.atk_scale ×2）。
- 测试：test_level_runes.py 5→10 用例；全量回归 55 文件 399 项全绿。


## 2026-08-07 map_tile_blackb 地块参数覆写 rune【已实现】

- tile_blackboard 现在合并：动态地块效果 → 地块 prefab 默认值（tile_blackboard_defaults） → 关卡 rune 覆写（先 mul 再 add 最后 assign）。
- map_tile_blackb_assign/add/mul 支持两种定位：地块类型（tile='tile_reed|tile_reedf'）或位置（location='(r,c)'）。
- 实测：act22side_01（ALL）tile_reed 地块 bb 覆写为 ignite_duration 15 / extinct_duration 20 / cooldown_duration 5 / damage 40 / ep_damage 40；act22side_ex04（FOUR_STAR）(1,10) 地块加 mode 1.0；act16d5_ex08 yinyang_road 地块 buff_yinyang[same].atk_scale 0.5。
- 测试：test_level_runes.py 10→13 用例；全量回归 55 文件 402 项全绿。


## 2026-08-07 预置物 rune：predefines_enable + random_spawn_on_tile【已实现】

- level_predefines_enable：隐藏预置物（hidden→pending）按 alias 激活——实测 act11d0_ex06 的 8 个 trap_014_tower 全部生效。
- level_predefine_tokens_random_spawn_on_tile：按地块类型（可 | 多种）在每个匹配地块放置预置 token（实测 rogue5_1-1 的 tile_dygmny_1 每格 1 个 trap_225_dysbox）；与关卡原始预置不冲突。
- 测试：test_level_runes.py 13→15 用例；全量回归 55 文件 404 项全绿。


## 2026-08-07 环境系统 rune：env_system_new / env_gbuff_new【已实现（解析+暴露）】

- env_system_new / env_gbuff_new / env_gbuff_new_with_verify 现被解析为 battle.env_systems（key + kind + attributes），并在快照暴露 envSystems 字段、在单位 spawn 时发出带 kind/attributes 的标记事件（供 AI/外部观察者读取）。
- 实测：act17side_tr01 的 env_gbuff_new heal_scale 1.5 进入快照；act25side_sp01 的 env_006_act25side_extra 进入 envSystems。
- 说明：每个 env_xxx 是高度定制的活动机制（天气/场地管理器），完整动作效果需逐 env 逆向；本轮先完成解析/暴露半接线，效果按需单独接线。
- 测试：test_level_runes.py 15→16 用例；全量回归 55 文件 405 项全绿。


## 2026-08-07 干员技能管线批量扫描【已实现】

- 抽样 32 个各职业干员（近卫/重装/先锋/术师/射手/医疗/辅助/特种）验证技能激活链：部署→SP填满→激活——全部正常。
- 失败模式全部是预期语义：部署触发技能（spType 8）不可手动激活（deploy_skill）；部署技能已自动激活占用时其他技能返回 already_active（游戏规则）。
- 测试：新增 tests/test_operator_scan.py（8 职业代表干员技能激活冒烟）；全量回归 56 文件 406 项全绿。


## 2026-08-07 真银斩多目标普攻修复【已实现】

- 银灰 S3 真银斩验证：atk +110%、def -70%已正确；但“同时攻击至多 N 个目标”（attack@max_target 3）未生效——普攻路径 _operator_attack 未读取 active skill 的 attack@max_target。
- 修复：_operator_attack 选目标时，若 active skill 的 attack_effects 含 max_target>1，则在攻击范围内选最多 N 个敌人（主目标优先、低血优先）；与 centurion/pusher/reaperrange 的 trait 多目标分支互不干涉。
- 实测：近战范围内 2 个敌人时一次攻击命中 2 个，每个 atk×2.1。
- 能天使 S3 过载模式的攻速：Lv1 无 base_attack_time 值（数据事实），Lv4+ 才有 -0.05/-0.08/-0.11，模拟器跳转与数据一致；不算缺口。
- 测试：test_operator_skills.py 新增真银斩用例（17→18）；全量回归 56 文件 407 项全绿。


## 2026-08-07 连击类技能验证与替换语义修复【已实现】

- 陈 S3 绝影（激活即十连斩 burst）：实测每段 atk×2.0 共 10 段，正确。
- 能天使 S3 过载模式（普攻模式切换）：发现真实 bug——普攻本体与 attack@times 连击叠加（1+n 段）。修复：_resolve_operator_attack 当 active skill 的 attack_effects 含 times>1 且 atk_scale>0 时跳过普攻本体（普攻即连击），由 apply_on_attack 打出 times 段。
- 实测：能天使 S3 一次普攻 5 段 atk×1.0（原 1+5=6 段）。
- 测试：test_operator_skills.py 新增绝影十连斩 + 过载五连射 2 用例（18→20）；全量回归 56 文件 409 项全绿。


## 2026-08-07 火山/治疗技能验证【已实现】

- 艾雅法拉 S3 火山：激活后 atk×1.55、攻击间隔 -1.1s（1.6→0.5）、普攻命中最多 3 个目标（attack@max_target）——全部正确（多目标为上轮修复的通用路径自动覆盖）。
- 塞雷娅 S2 药物配置：对最低血友方治疗 heal_scale×atk（0.8），实测精确。
- 测试：test_operator_skills.py 新增火山 + 治疗 2 用例（20→22）；全量回归 56 文件 411 项全绿。


## 2026-08-07 阶段前缀 stat buff + 强力击验证【已实现】

- 修复：_apply_prefixed_stat_buffs 原只处理 [self]/[ally] 等标签，二重唱的阶段前缀键（amgoat_s_1[a|b].attack_speed / .atk）未解析，激活后攻速/攻击无变化。现支持 '<skill>[a|b].stat' 作为自身 stat buff。
- 实测：二重唱激活后 atk +30%、attackSpeed +30（100→130）、攻击间隔 1.6→1.231。
- 银灰 S1 强力击：激活后 burst atk×1.9（实测 1205.9），正确。
- 测试：test_operator_skills.py 新增二重唱 + 强力击 2 用例（22→24）；全量回归 56 文件 413 项全绿。


## 2026-08-07 弹道穿透双重应用修复【已实现】

- 问题：Projectile.on_hit 和 battle._wrap_hit 默认分支先 calculate_damage（已含源穿透），再把 amount 传给 battle.apply_damage（内部又读源穿透重新计算）——穿透被应用两次。实测送董人（fixed 穿透 160）对 def 200 敌人伤害 826（= 906-40×2）而非正确的 866。
- 修复：弹道命中传原始 atk×atk_scale，穿透/减伤由 apply_damage 统一应用一次。
- 验证：送董人弹道物理穿透 866 = 604×1.5 - (200-160)；Pith 法穿 494.2 = 706×(1-(50-20)/100)。
- 测试：test_operator_skills.py 新增弹道穿透 + 法穿 2 用例（24→26）；全量回归 56 文件 415 项全绿。


## 2026-08-07 百分比穿透与叠加验证【已实现】

- 莱欧斯（char_4142_laios）百分比 defPenetrate 0.4：实测伤害 813.8 = 933.8 - 200×0.6，正确。
- 穿透+脆弱叠加：伤害 = (atk - def×(1-pen))×fragility_scale，实测 1017.2 = (933.8-120)×1.25，一致。
- 测试：test_operator_skills.py 新增百分比穿透 + 叠加 2 用例（26→28）；全量回归 56 文件 417 项全绿。


## 2026-08-07 伤害公式矩阵 + 弹道回调穿透一致性【已实现】

- 弹道回调抽检：_fire_burst 的自定义 hit_callback、rdoc S2 治疗弹、Ray S1 特殊子弹均走 battle.apply_damage（源穿透自动应用），无路径不一致。
- 新增 tests/test_damage_matrix.py（7 用例）：物理减防/最小伤害比、固定穿透、法抗封顶（120→100）、真实无视防御、元素不受防御影响、脆弱乘区、屏障先减伤后吸收——全部精确。
- 全量回归 57 文件 424 项全绿。


## 2026-08-07 伤害矩阵边界组合 + 近战穿透路径【已实现】

- 边界组合（7→12 用例）：最小伤害比×屏障（5-3=2）、法穿×法抗封顶（120-30=90→伤害 10）、百分比+固定双穿透（逐步验证）、脆弱×屏障（60-10=50）。
- 近战穿透路径：医生（instructor）特性 1.2 倍 + 固定穿透 120 完全抵消 def 100，伤害 661.2 = 551×1.2，与弹道共用 apply_damage 穿透路径一致。
- 全量回归 57 文件 429 项全绿。


## 2026-08-07 部署动画期间技能计时修复 + 持续时序验证【已实现】

- 修复真实 bug：部署动画期间 _update_operators 跳过整个 op 更新（含 sc.tick），导致技能 remaining 暂停——激活后的持续时间实际多出部署动画余量（火山 15s 在 tick 470 仍剩 0.167s）。现动画期间仅跳过攻击/天赋，技能计时照常递减。
- 连带修复：傀儡师替身还原时设 SP=0 后同一 tick 被自动回复覆盖（+1），现还原时重置 SP 回复累积器。
- 持续时序验证：新增 tests/test_skill_timing.py（火山 15s 窗口保持/恢复、二重唱 25s 窗口保持/恢复）；cast-end 测试时序与正确行为对齐。
- 全量回归 58 文件 431 项全绿。


## 2026-08-07 炼金单元 DoT 精确计时【已实现】

- 锡人 S1 区域 DoT（tinman_s_1[dot]）验证：trigger_interval=30（1s）、cached_atk=atk×0.3（实测 96.645）、区域寿命=projectile_delay_time 8s（240 tick，命中后实测到期移除）。
- 持续时序测试集完成：火山 15s / 二重唱 25s 窗口 + 炼金 DoT 1s 触发节奏。
- 全量回归 58 文件 432 项全绿。


## 2026-08-07 异常打断语义修复（空旋/冻结）【已实现】

- 修复真实 bug 1：敌方技能被空旋/冻结打断后 cd_remaining=0，犹象结束后会秒释放——现打断时进入冷却（不计触发次数、不耗 SP），防止连续施放。
- 修复真实 bug 2：_tick_abnormal 在异常结束时固定恢复 MOVE，导致原本 COMBAT 的敌人卡在移动态不再攻击——现保存异常前状态（_pre_abnormal_state）并恢复。
- 完整链验证：施放中空旋 → finish INTERRUPTED → cd 重置→ 犹象结束恢复 COMBAT → cd 结束后重新施放。
- 测试：test_skill_system.py 新增完整打断链用例；全量回归 58 文件 433 项全绿。


## 2026-08-07 干员被控制时停止攻击修复【已实现】

- 修复真实 bug：_update_operators 的攻击段未检查干员不可控状态（空旋/冻结/浮空/麻痩 flag 0/16/25/39），被空旋的干员仍继续普攻和持续技能输出。现不可控时攻击计时与前摇均挂起，结束后恢复。
- 语义确认：持续技能（真银斩）空旋期间无伤害输出，但技能剩余时间照常递减（与游戏一致）。
- 测试：test_abnormal.py 新增空旋停攻击/恢复 + 持续技能输出暂停不暂时 2 用例；全量回归 58 文件 435 项全绿。


## 2026-08-07 buff 提供的异常免疫（abnormalImmunes）【已实现】

- 修复真实缺口：解包数据中 1220 个 buff 携带 abnormalImmunes（如 invincible/状态抗性），但该字段仅在字段定义中出现、模拟器未消费——带免疫 buff 的单位仍会被施加对应异常。
- 实现：BuffSystem.apply 保留 abnormalImmunes 字段；materialise_buff 将其写入 entry；set_abnormal 新增 _buff_abnormal_immune 检查（支持枚举名与数值 flag）。
- 实测：挂携 ['STUNNED','FROZEN'] 免疫的 buff 后，空旋/冻结被免疫，沉默仍可施加；数值 flag [0] 同样生效。
- 测试：test_abnormal.py 新增免疫 2 用例；全量回归 58 文件 437 项全绿。


## 2026-08-07 元素爆发异常与免疫联动【已实现】

- 神经爆发（ep_type 0）施加空旋 + 1000 真实伤害；带空旋免疫 buff 的单位跳过控制（flag 不挂）但保留爆发伤害（-1000）——由上轮修复的免疫检查自动覆盖。
- 测试：test_abnormal.py 新增爆发免疫联动用例；全量回归 58 文件 438 项全绿。


## 2026-08-07 异常组合状态优先级【已实现】

- 确认 ABNORMAL_STATE 优先级：空旋 > 冻结 > 浮空 > 麻痩（按字典顺序第一个命中者赢）。
- 实测：空旋+冻结并存时状态=STUN；空旋先结束→FROZEN；冻结结束→恢复异常前 COMBAT。符合游戏语义。
- 测试：test_abnormal.py 新增组合优先级用例；全量回归 58 文件 439 项全绿。


## 2026-08-07 关卡加载冒烟 + 波次实例键修复【已实现】

- 抽样扫描：48+143 个各前缀关卡（main/hard/act/camp/memory/rogue/recalrune/sandbox/lt 等）加载 + 首 30 tick，1 个失败：level_rogue1_1-5 报“no enemy data for enemy_1056_ganwar#1”。
- 修复真实缺口：波次 SPAWN 的敌人键带 #N 实例后缀，resolve_enemy_key 未剥除。现先剥 #后缀再查数据库/名单。
- 测试：新增 tests/test_level_loading.py（15 个代表关卡加载 + 实例键解析）；全量回归 59 文件 441 项全绿。


## 2026-08-07 无地图元数据关卡加载修复【已实现】

- 补扫 15 个未覆盖前缀关卡，1 个失败：level_script_table91d938（脚本表元数据关卡）map=null 导致 merged_map 崩溃。
- 修复：merged_map 对无可玩地图的元数据关卡返回空网格（0×0），加载不崩溃。
- 测试：test_level_loading.py 添加该关卡；全量回归 59 文件 441 项全绿。


## 2026-08-08 波次 hiddenGroup rune（level_hidden_group_enable/disable）【已实现】

- 数据事实：641 个关卡存在带 hiddenGroup 的波次动作（SPAWN 4131 / ACTIVATE_PREDEFINED 772 / PREVIEW_CURSOR 44 / EMPTY 92 等），默认隐藏；494 个 level_hidden_group_enable + 34 个 level_hidden_group_disable rune 按难度（NORMAL=1 / FOUR_STAR=2 / ALL=15）控制哪些组生效。
- build_wave_timeline 现在把 hiddenGroup 保留到每条事件（原 bundle 的 waveTimeline 抽取时丢失该字段）；WaveScheduler 按 rune 过滤：
  - 事件带 hiddenGroup 时，仅当该组被当前难度的 enable rune 启用、且未被 disable rune 禁用才执行（SPAWN/PREVIEW_CURSOR/ACTIVATE_PREDEFINED 等全部动作类型统一过滤）；
  - 被跳过的动作发出 hidden_group_action_skipped 事件（type/key/hiddenGroup/t），快照新增 hiddenGroups{enable:[],disable:[]} 字段。
- 实测：level_act13side_sub-1-1 的 raid 组（enemy_1182_flasrt_2/enemy_1183_mlasrt_2）NORMAL 全跳过（4 条 skip 事件、0 生成），FOUR_STAR 全部生效（各生成 1 只）；存在 NORMAL/FOUR_STAR 互换编成的关卡（enable normal[1]+fstar[2] / disable fstar[1]+normal[2]）按同规则切换。
- 测试：test_wave_timing.py 新增 2 用例（时间线保留 hiddenGroup + 难度门控端到端）；相关回归全绿。

## 2026-08-08 波次 SPAWN routeIndex 缺省=0 修复【已实现】

- 数据事实：80,929 条 SPAWN 中 2034 条 routeIndex 为 None?FlatBuffers 对缺省值 0 省略字段，涉及 2034 个关卡，如 level_act11d0_01 / level_a001_01 等）；此前模拟器把 routeIndex=None 的 SPAWN 整条丢弃。
- build_wave_timeline 现在把 None 归一为 0?显式非 0 路由原样保留）； spawn_enemy 对 route_index=None 统一按 0 处理后再做边界校验。
- 实测：level_act11d0_01 首条 enemy_1007_slime（t=3.0）在 NORMAL 与 FOUR_STAR 下均正常生成（tick 91，routeIndex=0）。
- 测试：test_wave_timing.py 新增 2 用例?时间线 None->0 + 双难度端到端）；相关回归 117 项全绿。
## 2026-08-08 波次随机出生组 randomSpawnGroup*【已实现】

- 数据事实：643 个关卡使用随机出生组，共 3105 个组、10024 个候选动作；3562 个动作带 randomSpawnGroupPackKey 且不属于任何组（打包伴随动作，如 PREVIEW_CURSOR 或同包第二只怪）。
- 语义（dump.cs RandomGroupSchedulerPreprocessor + 社区工具确认）：随机组键 RandomGroupKey=(waveIndex, fragIndex, randomKey)，即同一波次、同一片段内、同 randomSpawnGroupKey 的动作构成互斥加权组；组内按 weight 加权选一；选中动作所在 randomSpawnGroupPackKey 打包组的所有成员（无组键的伴随动作）一起生效；失败候选所在打包组整体从调度表删除（m_actionPacksToDelete）。权重 None 按 0 处理（FlatBuffers 省略 0），全 0 组按等权回退。
- 实现：
  - build_wave_timeline(waves, rng=None) 新增 rng 参数：传入战斗 key RNG 时在构建期逐组加权选择（rng.next(total)），只保留获胜候选与其打包伴随动作，波次链式结束时间按解析后事件计算；不传 rng 时保留全部候选（静态/未解析视图，供数据浏览）。
  - 空候选（key 为 null，如肉鸽 bonus 组 weight 85）是合法的「不出怪」结果，保留为 isEmpty 事件；WaveScheduler 执行时发 random_group_empty 事件（type/groupKey/packKey/t）。
  - 事件新增 groupKey/packKey/weight/isEmpty 元数据；WaveScheduler.random_groups 暴露每组胜出信息（wave/fragment/groupKey/key/packKey/weight/isEmpty）。
  - 端到端：BattleController 构建时间线时传 self.rng，随机组与暴击/闪避等共用战斗关键随机流，同种子完全可复现。
- 实测：
  - level_lt01_01：g1(50/50)、g2(60/40)、g4(80/20) 按权重生效；1200 个种子下 g2 ucommd 命中率 55%~66%。
  - level_rogue3_1-3：dx/ns 组 SPAWN 与其 PREVIEW_CURSOR 通过 packKey 成对出现，败选包零残留；w1 bonus 组空候选（85 权重）多数种子不出怪。
  - level_rogue3_1-2：组候选仍受 hiddenGroup rune 门控——NORMAL 只出 n 组 dmgswd，FOUR_STAR 只出 h 组 dbskar/dmgswd，被禁组的胜者发 hidden_group_action_skipped。
  - 全量：2817 个含波次关卡全部解析无崩溃，3105 个组每组恰解析出一个候选。
- 边界：同一 packKey 被多个组共享（level_rogue5_b-4 的 s1/s2）时按「包内任一候选获胜则整包存活」处理（与 m_actionPacksToDelete 结构一致），该关卡的组合出怪可能叠加，属预期；randomType/refreshType（PER_DAY/PER_SEASON 等持久化语义）在单局模拟中一律按 ALWAYS 每局重掷。
- 测试：test_wave_timing.py 新增 9 用例（确定性/权重分布/空候选/pack 成对/pack-only 保留/链式时间随胜者/运行时空事件/端到端生成/隐藏组难度门控）；相关回归 129 项全绿。
## 2026-08-08 关卡分支 BranchData 阶段调度【已实现】

- 数据事实：2913 个关卡带 branches，共 2913 个分支、3515 个阶段；799 个关卡的分支阶段含动作（6037 SPAWN + 624 ACTIVATE_PREDEFINED）；4 个关卡的分支动作带 hiddenGroup，89 个关卡的分支动作带 randomSpawnGroupKey（2034 条，多为沙盒/肉鸽）。
- 语义（dump.cs Scheduler.BranchRuntime + Nodes.MoveNextLevelBranch 官方描述「move specific branch's cursor to next phase」）：每个分支持有一个阶段游标；每次触发把游标移到下一阶段，并把该阶段当作一个 fragment 处理（phase.preDelay + action.preDelay / count / interval，阶段内动作并发）；分支自身 preDelay 全量为 None。PickRandomBranchPhase 对应 TryPickRandomBranch*/TryPickRandomPhase（随机选阶段，notRepeat 不重复）。
- 实现：
  - execute_branch(branch_id, is_loop=False)：游标推进（is_loop 回绕），用 build_wave_timeline(rng=战斗 RNG) 把阶段动作构造成绝对时间线（随机出生组同规则解析），复用 WaveScheduler 执行（含 hiddenGroup rune 门控、空候选 random_group_empty、randomGroups 元数据）；返回调度事件数。
  - execute_branch_random(branch_id, not_repeat, block_game_finish)：随机选阶段并调度（rng 均匀；not_repeat 用已用集合，耗尽后重置）。
  - tick_once 步骤 1.1 更新活跃分支阶段调度器，完成后移除；胜利判定改为「主波次完成 + 敌人清空 + 无挂起分支阶段」（否则分支的 30s 后生成会被提前判胜切断）。
  - snapshot 新增 branches{cursors, activePhases}；level_branch 事件带 phase/count/randomGroups。
  - action_nodes 支持 MoveNextLevelBranch(is_loop) 与 PickRandomBranchPhase。
- 实测：
  - level_act38side_ex06 fire 分支：NORMAL 只生成 cnvfire（+1 vs 基线）、FOUR_STAR 只生成 cnvfire_1；balloon 分支按 action.preDelay 2/6/30s 精确生成（tick 61/181/901，含 cnvbln_2）。
  - level_rogue5_b-9-e dysuib_relic_branch（24 阶段）：连续触发依次调度阶段 0..3，is_loop 回绕到 0。
  - level_rogue5_b-9-a：分支阶段随机组 r1 按权重解析为单候选，同种子完全复现。
  - 挂起分支阶段会延迟胜利（合成空波次关卡 + t=60 分支生成验证）。
- 测试：新增 tests/test_branch_phases.py 7 用例；全量回归 60 文件 462 项全绿。
## 2026-08-08 场地机制审计与修复（tile 效果）【已实现】

- 数据审计：全量关卡 95 种 tileKey 在 data_tile_defs.json（[uc]tiles.ab 111 个 prefab）中 100% 有定义；60+ 种带行为（buff/dot/volcano/ice/quicksand/mire/reed/hole/deepsea/infection/yinyang/gravity/wood），35 种为纯地形/表现。6 个未分类脚本族（40 个 tile 的 8835298718773198526 等）在提取数据中无 buff/action，属视觉或模式专属（传送/兔洞/沙绳/合作/足球），无数据可驱动。
- 修复 1（targetSide 过滤）：tile 效果此前对任意阵营生效；按 SideType 枚举（1=ALLY 2=ENEMY 3=BOTH 7=ALL）过滤——草/治疗/防御/睡眠/阴阳等友方专用地块不再给敌方加 buff，流沙/深海/木道/感染等敌方专用地块不再影响干员；tick() 顶层统一过滤。
- 修复 2（buff 数值读取）：_apply_buff 此前直接用 prefab 修饰器默认值（loadFromBlackboard 的 0.0），从不读地块黑板，导致治疗/草/防御地块零效果；现优先读 battle.tile_blackboard（关卡参数 / map_tile_blackb rune），回退 prefab 默认。
- 数据事实：tile prefab 的 _data.blackboard 与关卡 tile blackboard 均不携带 gameplay 数值（火山/毒雾伤害、治疗量来自游戏代码/运行时填充），模拟器以 prefab action 的 _damageKey 与内置默认值驱动；已接入的数值路径（map_tile_blackb 注入）端到端验证通过。
- 实测：
  - 敌方站治疗/草地块无 buff；站深海地块获得 under_sea[tile]；干员站治疗地块获得 tile_healing 且注入 hp_recovery_per_sec=25 后 35 tick 回复 28 HP。
  - 敌方站火山地块 45 tick 扣 800 HP（PURE 周期伤害）；站毒雾地块扣血。
- 测试：新增 tests/test_tile_effects_e2e.py 4 用例；相关回归（advanced_features/skill_tiles/level_runes/level_loading/battle_integration/skill_system）76 项全绿。
