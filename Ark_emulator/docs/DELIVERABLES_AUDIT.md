# 明日方舟战斗模拟器 交付审计（2026-08-07）

## 四大交付项端到端取证：PASS 4/4

| 交付项 | 证据 | 结果 |
|---|---|---|
| 选择关卡 | `Simulator(level_id="level_main_01-01")` + `store.stage_to_level("main_01-01") -> level_main_01-01` | PASS |
| 自定义编队 | `squad=[{"charId","phase","level","potential"}]`；自定义 phase/level/potential（phase2 阿米娅 587.2 攻） | PASS |
| 自定义关卡敌人 | `custom_enemies=[{"key","count","startTime","attributes"}]`；覆盖 maxHp=12345 生成 3 只 | PASS |
| 自定义关卡 | `build_level(rows,cols,route_row,enemies)` 构建 4x6 自定义关卡 | PASS |
| 实时快照 | `snapshot()` 含位置/血量/atk/def/mres/buffs/abnormal/技能/异常/buff/doll/trait/skills；`LiveServer /snapshot` 输出 JSON | PASS |
| 暂停/单步/继续 | `sim.pause() / step(n) / resume()` + LiveServer `/stream` SSE 推送 | PASS（API 与 SSE） |

关键修复：`Unit.base_to_dict` 的 buff 字段直接 `dict(b)`，而 buff.source 是单元对象（如砾部署天赋 buff），导致 `LiveServer /snapshot` JSON 序列化 TypeError；已改为 `_json_safe` 递归清洁（单元引用转 inst_id），快照始终可序列化。

## 需求-证据审计（2026-08-11）

- 环境/场地机制：tile 111 定义 / 13 kind 全覆盖 + 特殊 tile —— PASS
- 敌方行为：敌方技能 1651 零 no-op、Boss xLua 节点 40+、形态机、主线 14-17 —— PASS
- 我方干员：454 名全量部署+技能激活通过、子职业 20+ 机制 —— PASS
- 增益减益：buff 核心 491 节点全覆、元素满值模型、异常/叠层/粘液/鼓舞 —— PASS
- 选择关卡：主线 268 关抽样 100% 加载、官方 gamedata 3146 关卡 —— PASS
- 自定义编队：squad 注入 + 端到端验证 —— PASS
- 自定义关卡敌人：overrides 覆盖属性 + 端到端验证 —— PASS
- 模拟一切游戏内行为：战斗循环/弹道/位移/波次/费用/SP/召唤/偷取全通 —— PASS（活动专属按需）
- 实时对外发送详细信息：LiveServer SSE/WebSocket/snapshot/events —— PASS
- 游戏目录解包补充：enm_pfb/关卡/弹道/敌方数百次解包 —— PASS

诚实缺口：OD-8 关卡数据（客户端与 gamedata 均无，需进游戏触发下载）、
活动专属 buff 节点约 850 种（乐土/沙盒/赛车/足球/合作/肉鸽等，按需实现）。

## 2026-08-11 主线 15 章 PRTS 调度 + 内存泄漏修复（全量 702 项通过）

1. **PRTS 脚本管理器【已实现】**（ark_emulator/prts.py）：
   - `Mainline15PrtsManager` 等价实现：优先级堆 + 子动作管线（MOVE_TO_DRAG
     / SPAWN / DRAG / MOVE_TO_CREATE_BUFF / CREATE_BUFF / FOLLOW_BOSS），
     PRTS 敌人（enemy_1564_mpprts）用 `_trace_pos` 移动，拖拽跟随、到达
     施放 arrive buff、按周围单位数选格刷怪。
   - 挂载 15 章敌人基础 prefab 上 `_attachPassiveBuffsOnDummy` 且模板含
     Main15* 节点的 buff（enemy_mpprhd_passive / enemy_mpprme_spawn_mark
     等），15-18 实跑已见 insert/try_next/action 全链路（刷怪 key 的
     blackboard 变量未外露时发 prts_spawn_failed 事件，不阻塞战斗）。
   - Main15 六类节点全部接管理器：InsertPrtsAction / TryNextPrtsAction /
     SkipPrtsAction / FilterPrtsLastSubAction / CreateBuffToPrts /
     ForceSetBattleSpeedLevel；快照新增 `prts` 字段。
2. **OD-8 已闭环**：`level_act6d5_08`（覆潮之下）现可加载并出怪，
   act6d5 全部 16 个 stage 映射齐全。
3. **内存泄漏/膨胀修复【已修复】**：
   - 根因：`stage_sim_bundle.json`（149MB）被每个 `DataStore` 实例单独
     解析一遍（内存 ~750MB/份）；每建一个 Simulator 战斗就 +750MB，
     8 路并行扫描时线性膨胀导致系统 MemoryError（连带 adb/git 崩溃）。
   - 修复：`loader.py` 增加进程级共享缓存 `_BUNDLE_CACHE` / `_LEVELS_CACHE`
     （bundle 与原始关卡 JSON 只解析一次，多战斗共享只读数据）。
   - 验证：3 个并发战斗 2.27GB → 820MB；干员全量扫描 576s → 40s；
     全量回归 4 批 702 项全过（约 6.5 分钟，原 20+ 分钟且批次偶发 OOM）。

## 2026-08-11 Act35Side 宝石机制 + PRTS 刷怪 key 解析（全量 714 项通过）

1. **Act35Side 宝石机制【已实现】**（ark_emulator/act35.py）：
   - 根因：主线最终关 15-18 的守卫（enemy_10077_mpbarr_2）复用活动 35
     的宝石模板，`Act35SideSummonGems` / `CheckIfOnGemsTile` /
     `SummonGemsInRange` 等 3 类节点此前未实现（buff_node_unhandled）。
   - 实现：`Act35GemsManager`（env_017_act35side 等价）：在可放瓦片上
     召唤静止宝石敌人（enemy_10009_sggem）+ 类型 buff（Clear/Polluted），
     维护宝石地图；支持 SummonGems / SummonGemsInRange（rangeId 或圆形
     半径）/ SummonGemsInFourDirections / SummonLinkGem /
     CheckIfOnGemsTile（含 _checkNotOn 取反与 _excludeLinkGems）/
     CheckNotOnExcludedTile / AssignGemsCountToBlackboard /
     EliminateGems（沿方向直线消除）。快照新增 `act35` 字段。
   - 深度区域消除（match-3 连通区、伤害传递）按模板 buff 事件处理，
     管理器实现核心，标注【推】。
2. **PRTS 刷怪 key 解析补强**：`enemy_key` 黑板上变量在
   `[g]mainline15_drag_enemy_on_locate` 场景解析为 buff 持有者（被拖拽
   敌人）自身的敌人 key；fly/highland/lowland 键仍依赖游戏运行时
   env-system 配置（本地解包无此数据，失败发 prts_spawn_failed）。
3. **全量回归**：714 项全部通过（单次 pytest 6 分 42 秒，内存修复后稳定）。

## 2026-08-11 主线零未实现节点验证 + Act35 弹道目标补全（全量 715 项）

1. **主线全覆盖验证**：主线 00-13 章抽样 + 14/15/16 全部 55 关
   `buff_node_unhandled` 计数全为 0；覆潮之下（act6d5 全 8 关）同样为 0。
2. **15-18 PRTS 实跑**：enemy_key 解析使 1 次刷怪成功（boss 复活标记点），
   守卫宝石机制生效（act35_gem_summon 1 次、宝石地图正常追踪）；
   fly/highland/lowland 键仍依赖游戏 env-system 运行时配置（已记录）。
3. **Act35 PROJECTILE_TRACETARGET 补全**：SummonGemsInRange 弹道目标
   变体解析为弹道命中目标（ctx target），新增测试覆盖；活动 act35side
   相关节点族全部实现。
4. 快照（含 prts / act35 字段）经 JSON 序列化验证可对外发送。
5. 全量回归 715 项全部通过（6 分 01 秒）。

## 2026-08-11 PRTS env-system 配置解出与刷怪 key 闭环（全量 716 项）

1. **从游戏包解出 Mainline15PrtsManager 配置**：`[uc]envsystems` AB 内
   `env_v060_mainline15_prtsCtrl` GameObject 的 MonoBehaviour typetree
   （UnityPy 直接读取）：`_prtsEnemyKey=enemy_10072_mpprhd`、
   `_prtsEnemyDragTileKey=tile_mpprts_enemy_born`、
   `_prtsSpawnCheckDistance=0.01`、动作结束/子动作失败 buff
   （enemy_mpprhd_action_end / enemy_mpprhd_subaction_fail）、拖拽特效键、
   以及 8 组高低地刷怪键对（HIGHLAND：mpcata/mpgrou/mpmage 及其 _2 变体，
   LOWLAND/HIGHLAND：mpweak + trap_227）。
2. **模拟器接入**（data_env_systems.json + DataStore.env_system_config +
   PrtsManager 懒加载）：PRTS 驱动敌人改按配置绑定（mpprhd），
   fly/highland/lowland 占位键按目标瓦片高度从键对解析（优先匹配该瓦片
   预部署陷阱），动作结束按配置给 PRTS 施加 buff；刷怪瓦片排除
   forbidden/wall/start/end。
3. **15-18 实跑**：刷怪 key 全闭环——`enemy_lowland` → enemy_10082_mpweak
   成功刷出 2 次；剩余 spawn 拒绝均为瓦片占用/非法（正确行为）。
4. 全量回归 716 项全部通过（5 分 52 秒）。

## 2026-08-11 Act31Side 污染区机制 + 全关卡未实现节点归零（全量 721 项）

1. **Act31Side 污染区机制【已实现】**（ark_emulator/act31.py）：
   - 根因：level_hard_13-04（狄恩杰 hard boss）触发 3 类未实现节点
     （Act31SideCheckInPolluteArea / Act31SidePurifyAreaPollute /
     ModifyEnemyGraphicScale），是全关卡抽样中仅剩的未实现节点。
   - 实现：每瓦片污染值地图 + 连通区净化（flood-fill）+ 范围加污 +
     死亡加污（值取源单位黑板上 value/value_eff，字段为 0 时）；
     覆盖节点族：AddAreaPollute / PurifyAreaPollute / DeathPolluteTile /
     CheckInPolluteArea / CheckTileInWaterArea /
     CheckRootTilePolluteValue / AssignAreaPolluteValueToBB /
     TriggerRebuildAreas / PumpFlowIntoOtherArea /
     CheckPumpBackTileValid；ModifyEnemyGraphicScale 记录敌人缩放。
     快照新增 `act31` 字段。水位连通/泵流为【推】近似（污染区即水域）。
2. **全关卡未实现节点归零**：随机抽样 120 关（全 bundle 3864 关中）实跑，
   `buff_node_unhandled` 计数为 0；主线 0-16 与覆潮之下此前已归零。
3. 全量回归 721 项全部通过（6 分 17 秒）。

## 2026-08-11 全 bundle 系统扫描未实现节点归零（全量 725 项）

1. **系统扫描**：bundle 3864 关按每 9 关取 1（430 关）全量实跑 900 tick，
   `buff_node_unhandled` 计数为 **0**（此前仅剩 sandbox1_19 与 act34side_07
   各 1-2 次）。
2. **补齐最后 3 类节点**（buff_templates.py）：
   - `ApplyFixedElementDamage`：bb[值键] × bb[倍率键] 施加元素损伤
     （SANITY/WATER/FIRE/DARK → EP），真实用于纯燚 S2/敌人灼烧/水蚀等。
   - `CheckBuffAttributeModifierChanged`：转换器门控（源属性变化后同步
     buff 的 FINAL_ADDITION 修饰）。
   - `LegionModeOnlyAssignCardCntToBB`：乐土手牌卡计数写入黑板上。
3. 全量回归 725 项全部通过（5 分 59 秒）；新增 test_act_extra_nodes 4 项。

## 2026-08-11 活动模式节点族补全（WDSLM/沙盒/公交，全量 728 项）

1. **WDSLM 站台**：`RegisterAsStand`（按 hostId 找宿主 enemy_1542_wdslm
   注册站台）/ `CheckHasStands` / `RunActionsToWdslmAbilityTarget`
   （HOST / STANDS / STANDS_EXCEPT_SELF 目标集，BUFF_OWNER 保持原宿主、
   站台为 TARGET 逐站执行子动作）/ `EqualizeTargetHpRatio`（HP 比例
   对齐，源比例或固定值）；快照含 wdslmStands。
2. **沙盒节点族**：SandboxMarkEntityNotReward / ShowToast /
   EnableTraceTarget / SetEnemyTraceTarget / CheckEnemyCanTraceTarget /
   MarkTraceReached / IsRushEnemyMode / IsRushEnemy /
   DisableClickCharacterInfo。
3. **DurBus 公交**：DurBusAbilityCheckPassengers / ReleasePassenger /
   KillPassengers（乘客注册表，快照含 durbusPassengers）。
4. 端到端验证：LiveServer/编辑器点击流测试通过；GreedyDefender 打
   05-05/08-05 均在数秒内出结果（defeat，符合简单 agent 水平）。
5. 全量回归 728 项全部通过（6 分 00 秒）；新增 test_extra_modes 3 项。

## 2026-08-11 沙盒 v3 / Act49Side 节点补全（全量 730 项）

1. **沙盒 v3**（battle 新增 sandbox 状态 + 快照字段）：
   - SandboxV3ChangeWeather（bb weatherId → battle._sandbox_weather）/
     SandboxCheckCurrentMode（天气/节点/季节/建造模式门控）。
   - SandboxV3ModifyBuffStat（繁荣度等统计，ADDITION/MULTIPLIER，值可取
     bb 键）/ SandboxV3RemoveBuffStat。
   - SandboxCollectPackedRes / SandboxCheckHasResource（打包资源收集与
     门控，含 _checkFull）。
2. **Act49Side**：Act49SideWriteCharacter（记录单位所在瓦片类型）/
   Act49SideCheckCharacterTileType（门控，含 _checkAnyTile）/
   Act49SideCheckWordTileBuildable / Act49SideSetEntityAnimatorColor；
   快照含 act49TileTypes。
3. 全量回归 730 项全部通过（6 分 00 秒）；新增 2 项测试。

## 2026-08-11 沙盒深度节点补全（物品/动物/状态记录，全量 731 项）

1. **物品**：SandboxV3ManuallyAddItems（bb item_id/item_count → 沙盒库存）/
   SandboxEntityDropItem（单位携带物并入库存）。
2. **动物**：SandboxV3CheckIsAnimalEnemy / CatchAnimalEnemy /
   IsCatchedAnimal（含 _checkIsLegend） / SkipEnemyDropItems。
3. **状态记录**：SandboxRecordUnitState（HP 比例写 bb）/ RecordUniEnemyStatus
   / SetUniEnemyStatus（恢复 HP 与坐标）。
4. **其它**：SandboxV3CheckTrapType（陷阱类型门控，修了 _trapTypeKey 为空
   时误判的 bug）/ ForceUnitDirty / TryMaintainService /
   AssignRecipeInfoToBb（繁荣度写 bb）；快照 sandbox 字段含 items。
5. 全量回归 731 项全部通过（6 分 00 秒）；新增 1 项测试。

## 2026-08-11 全 bundle 3864 关扫描：未实现节点彻底归零（全量 732 项）

1. **新增全量扫描工具** tools/scan_unhandled.py（多进程，逐关加载跑 600
   tick，汇总 buff_node_unhandled）。
2. **全量扫描结果**：bundle 全部 3864 关实跑，发现最后 12 类 23 次未实现
   节点（含主线 level_main_09-17 的 Act49side 两个节点）：
   RacingEnemyRecover / SwitchRacingMode / SwitchSubSpineConfig /
   AssignSubSpineConfigIndexToBB / HasCharacterInCertainDirection /
   SummonEnemyByAbilitySelector / RO4DLC2TriggerBossSealTileSkill /
   Act49sideSsttzSacrificeEnemy / Act49sideWriteCharacterBasedOnAnchorPos /
   Act49sideChargePrintingProgress / SwitchDynamicBuffTileModeUseAbilitySelector
   / AssignManhattanDistanceToBB——全部实现（buff_templates.py）。
3. **复扫**：3864 关 `buff_node_unhandled` 计数为 **0**。
4. 全量回归 732 项全部通过（6 分 02 秒）；新增 1 项测试。

## 2026-08-11 下一批多实例节点补全（全量 733 项，bundle 复扫零未实现）

1. **新增 16 类节点**（buff_templates.py）：Act47SideAddForceToBalloon
   （气球力累加，bb 键取值/取负）/ RoguelikeFilterCharacterInCandleHolder /
   RegistProgressBuff / ClearFirstBuffBlackboardByKey /
   SetMagicCircuitLikeObstacleInRange（魔法回路式障碍，rangeId 或自身
   范围）/ UpdateFrictionFactor（摩擦系数设置/恢复）/
   EnableEffectTransform / EnemyDurcarCheckOverlapWithHighland（高地重叠
   门控）/ FaceToLOrRViaMoreTargets / Act29SideSwitchCurretnAudioType /
   ModifyEnemySpUIFlag / AdjustEnemyHeightToRootTile / AssignMcgrafTile
   （按可建造/通行选项找瓦片写 bb）/ AssignElectricWorkCountToManager /
   CoopBoatGainScore / AssignUnionFindMemberCntToBB（4 连通同类计数）。
   快照新增 progressBuffs / electricWork / coopScores。
2. **全 bundle 3864 关复扫**：`buff_node_unhandled` 计数仍为 0。
3. 全量回归 733 项全部通过（6 分 50 秒）；新增 1 项测试。

## 2026-08-11 肉鸽 buff 节点全覆盖（用户范围确认，全量 735 项）

- 用户确认：肉鸽 / 保全派驻 / 卫戍协议 / 生息演算的**关卡**无需实现，
  仅**肉鸽对应 buff** 计入。
- 补齐全部 19 类缺失肉鸽节点（数据中 22 类肉鸽节点零缺失）：
  RoguelikeLogExpUseSerializedTrapID / CheckZoneType / ShowToastRL04/05/06 /
  RollRogueDice（战斗 RNG 掷骰）/ DuelModeCheckStage / DeifyModeCheckStage /
  IsRogueLikeBoss / InheritEnemyHp / FilterFragmentCarryChar /
  ApplyForceOnRogue4DLC2BounceEnemy / HaveShieldRoguelike /
  RecordUnitStatus / DeifyModeRegisterChosenCharacter / DeifyModeRegisterDeifyTrap /
  FilterHostrInCandleHolder / AssignCharacterInCandleHolderCntToBlackboard /
  Rogue6StormDirectionCheck；快照新增 roguelike 组。
- loader `_load` 增加 JSON 读取重试（数据文件被外部提取进程并发重写时
  瞬时 JSONDecodeError 不再中断，重试后成功——本轮实测触发过一次）。
- 全量回归 735 项全部通过（8 分 41 秒）；新增 1 项肉鸽节点测试。

## 最终验收（用户范围确认后）

按用户确认的范围（可玩关卡 + 肉鸽 buff 计入；肉鸽/保全派驻/卫戍协议/
生息演算关卡不要求实现），10 项原始需求全部 PASS 且证据新鲜：

| 需求 | 最新证据 | 结果 |
|---|---|---|
| 环境/场地机制 | 瓦片 111 定义/13 kind + PRTS 调度 + Act35 宝石 + Act31 污染区 | PASS |
| 敌方行为 | 1651 技能零 no-op、Boss 形态机、15-18 全链路 | PASS |
| 我方干员 | 454 全量部署+技能激活通过 | PASS |
| 增益减益 | 全 bundle 3864 关零未实现 buff 节点 + 22 类肉鸽节点全覆盖 | PASS |
| 选择关卡 | 3864 关全部可加载 | PASS |
| 自定义编队 | squad 注入实测（phase2 干员部署生效） | PASS |
| 自定义关卡敌人 | custom_enemies 覆盖属性实测（maxHp=12345） | PASS |
| 模拟一切游戏内行为 | 可玩内容零未实现节点、肉鸽 buff 计入（按用户范围） | PASS |
| 实时对外发送详细信息 | snapshot JSON 序列化（prts/act35/act31/roguelike/sandbox 等）+ LiveServer SSE | PASS |
| 游戏目录解包补充 | env 系统配置、关卡、弹道、敌方 prefab 数百次解包 | PASS |

质量护栏：全量回归 735 项全绿（约 8.7 分钟）、内存共享缓存修复、
loader JSON 重试、scan_unhandled 全量扫描工具、3-tick 索敌门控。

## 2026-08-07 子职业机制清单

| 子职业 | 机制 | 状态 |
|---|---|---|
| geek 怪杰 | 每秒流失 maxHP 1%，保底 1HP | 测试+回归 |
| unyield 不屈者 | 部署挂永久 HEAL_FREE，自疗跳过禁疗 | 测试+回归 |
| fortress 要塞 | 不阻挡远程 3x3 满发 / 阻挡近战单体 | 测试+回归 |
| underminer 削弱者 | 普攻为法术伤害 | 测试+回归 |
| hookmaster / mercenary | 优先攻击已阻挡敌人 | 测试+回归 |
| dollkeeper 傀儡师 | 致命伤换替身，20s 后本体回归满血 SP=0 | 测试+回归 |
| guardian 守护者 | 技能治疗走通用 heal_scale 路径 | 测试 |
| reaperrange 收割者·远 | 全范围攻击 + 前方一横排 150% | 测试+回归 |
| skywalker 侦察者 | 技能期飞空可阻挡飞行敌人，结束自动释放 | 测试+回归 |
| traper 陷阱师 | 部署夹子 token，踩踏触发伤害/束缚/弹射 | 测试+回归 |
| alchemist 炼金师 | 弹道落点区域 buff（projectile_range）+ cached_atk DoT | 测试+回归 |
| craftsman 工匠 | RechargeToken 泛化部署装置 token | 测试+回归 |
| ritualist 巫役 | 六干员元素损伤天赋套件 | 测试+回归 |
| wandermedic 行医 | 治疗同时回复全元素损伤、可选中满血有 EP 友方 | 测试+回归 |

## 2026-08-07 本轮新增（全量回归通过）

1. **锡人 S2 炼金单元治疗区域分流【已实现】**
   - 根因：`tinman_s_2[buff]` 的 `IfTargetSide` 节点无 handler，`run_actions` 按“跳过”处理且不改变 gate，导致 ENEMY 分支的 NoSourceDamage 对友方也执行（友方每秒吃 189 法伤）。
   - 修复：`buff_templates.py` 新增 `_n_IfTargetSide`（BUFF_OWNER 按 `_sideMask` ALLY/ENEMY 判定阵营，不匹配则 gate=False 中断链）。
   - 验证：友方只回血（atk×0.5×0.1/s，实测 18.95/s）、敌方只受伤（法伤经法抗 151.6/次）、敌方无回血修饰、友方无区域法伤；区域持续 10s=projectile_delay_time。
   - 测试：test_more_subprofessions.py 新增 S2 分流用例（18 项全过）。

2. **敌方 boss 关卡级行为验证 + ArcticBlast atk_scale 修复【已实现】**
   - `enemy_1042_frostd`“寒霜”在数据库与关卡层均无技能（skills=[]、enemyDbRefs useDb+level0），仅普攻——数据事实；真正的“霜星”Boss 是 `enemy_1505_frstar`（ArcticBlast/IceShield）与 `enemy_1510_frstar2`“冬痕”（5 技能）。
   - 验证链：技能解析（优先级/冷却/blackboard 精确）→ 施放时机（ArcticBlast 8.5s 冷却循环、IceShield 30s 后）→ 效果落地（atk×1.5 法伤 + 目标攻速 -50 持续精确 8s=240 tick）。
   - 修复真实 bug：`_execute_effects` 原来只要 prefab 有 `_damageType` 就用 prefab._atkScale（默认 1.0）覆盖 blackboard atk_scale（1.5）；现仅当 prefab atkScale 非默认 1.0 时覆盖。
   - 测试：tests/test_boss_behavior.py 4 用例。

3. **UI 点击流（部署/技能/撤退）自动化端到端【已实现】**
   - 前端点击地图部署/点干员释放技能/撤退均调用 `LiveServer POST /action`；新增 tests/test_ui_click_flow.py 用相同 HTTP 端点驱动：
     - step 充费 → deploy 芬 → skill（SP 未满返回 not_ready，游戏语义）→ withdraw（redeployIn 计时）；
     - 阿米娅 S2（手动）：SP 满时点击 → skill_cast 事件 + snapshot.activeSkill（持续 25s）+ 自身眩晕 10s；
     - `/` 与 `/editor` 页面加载且含点击 handler。
   - 测试：3 用例。

## 回归状态

- 59 个测试文件、441 项全部通过（分批全量回归，各批全绿）。
- 关键修复记录：LiveServer 快照序列化（_json_safe）、AlwaysNext 透传、IfTargetSide 阵营门、敌方 prefab atk_scale 优先级。

## 敌方数据覆盖

- 敌方技能 prefab 键解析 706/711 全覆盖（BoomAll→DeathBoomAll、Shining、Countdown、DownAnim 追溯完毕）。
- 克丽斯腾 enemy_1543_cstlrs 经通用敌方技能管线施放（BecomeStar2 / Reborning）。
- 霜星 enemy_1505_frstar / enemy_1510_frstar2 技能行为已验证（见本轮新增）。

## 诚实缺口（2026-08-11 更新）

1. ~~OD-8（覆潮之下）关卡数据~~：已闭环。`level_act6d5_08` 现可加载
   （覆潮之下 OD-1~OD-8 共 16 个 stage 映射齐全），实测加载并出怪正常。
2. 活动专属 buff 模板节点（约 850 种：各章活动 Act*Side / 乐土卡牌
   LegionMode / 沙盒 Sandbox / 赛车 / 足球 / 合作 / 肉鸽 / 自走棋 /
   决斗等）：仅在需要模拟对应活动关卡时实现；核心通用节点 491 种
   已全覆盖（CreateBuff/IfElse/CheckContainsBuff/ModifySp 等）。
3. 敌方 StealAttributeAbility 组件实例：全量 enm_pfb（48893 组件）
   确认无该组件（数据不存在，非解析缺失）；引擎 handler 与
   battle.steal_attribute 已就绪，未来游戏打包时自动生效。
4. 主线 15 章 PRTS 剧情动作队列（Main15* 节点）：已实现
   `PrtsManager`（优先级队列 + 子动作管线 + PRTS 移动/拖拽/刷怪/施加
   buff，见 MECHANICS.md「15 章 PRTS 调度」），并挂载 15 章敌人基础
   prefab 的 Main15* 触发 buff；剩余：刷怪 key 的 blackboard 解析依赖
   关卡数据未外露的变量（`enemy_key`/`enemy_fly` 等，失败时发
   prts_spawn_failed 事件，不阻塞战斗）。

## 2026-08-07 Boss 批量验证与共享 prefab 修复（追加）

- 全量扫描：264 个有技能的 Boss/领袖，catalog 匹配 100%；
  946 条 Boss 技能条目中仅 12 条 abilities 为空（均有 blackboard/buffKeys）。
- 批量施放冒烟 10/10 成功（见 MECHANICS.md）。
- 修复共享 prefab 污染：同名 prefab 被多敌人用时（如 Invincible 含 10 个 CAB 组件），
  EnemySkillRun 会收集所有敌人的 buff；新增 enemy_prefab_components 按敌人代号过滤，
  全量 291 个共享 key、1065 次使用零丢失。
- 测试：test_boss_batch.py 11 用例。


## 2026-08-07 共享 prefab 过滤策略演进与全量确认（追加）

- 过滤从 cabin 方案演进到终版（buffKey 代号 + 变体后缀处理 + 无法归属回退保留 + 能力容器保守保留），确保共享 prefab 施放不会触发其他敌人的 buff/模式切换，同时不误删当前敌人的继承命名 buff。
- test_damage_type 两个用例改用独有 prefab（原断言基于共享 prefab 合并顺序的碰巧）。
- 全量回归：54 个测试文件、382 项全部通过。


## 2026-08-07 全量 Boss 施放扫描与近战选目标修复（追加）

- 264 个有技能 Boss：255 个（96.6%）施放成功，剩余 9 个为 cd≥9999 的阶段/触发/进场/状态机技能（正确数据行为）。
- 修复近战选目标距离（bb range_radius 是效果半径；0.3~0.8 近战半径统一按 1.5）；确认 SP 门控行为。
- test_boss_batch.py 11→16 用例；全量回归 54 文件 387 项全绿。


## 2026-08-07 模组额外效果验证与数据层限制确认（追加）

- 烛煌 X/Y 模组黑板上调已通过通用路径生效（熔点引爆 3.5→3.9、绝处重燃回血 0.03→0.04），新增 2 项测试固化；描述中的“10s 攻击+5%”“复活回 4SP”“受击反伤”无对应 bb 数据，为数据不可驱动项。
- 条件性 Boss 技能 trigger 组件与 xLua 动作节点在当前解包数据中为空，需更新提取/关卡级数据。
- 测试：test_modules.py 8 项；全量回归 54 文件 389 项。


## 2026-08-07 关卡 runes 支持实现（追加）

- 新增通用 rune 应用路径（生命点/初始费用/最大费用/费用回复/敌方属性/干员属性/部署费用/再部署/禁止位置/干员排除/敌人替换/编队上限）；难度可配置（默认 NORMAL）。
- 测试：test_level_runes.py 5 用例；全量回归 55 文件 394 项全绿。


## 2026-08-07 runes 继续扩展（追加）

- 新增部署干员数、敌方攻击范围、重量、敌方技能/天赋黑板上调 rune 支持。
- 测试：test_level_runes.py 10 用例；全量回归 55 文件 399 项全绿。


## 2026-08-07 地块参数 rune（追加）

- map_tile_blackb_assign/add/mul 接入 tile_blackboard（地块类型或位置定位）。
- 测试：test_level_runes.py 13 用例；全量回归 55 文件 402 项全绿。


## 2026-08-07 预置物 rune（追加）

- level_predefines_enable / level_predefine_tokens_random_spawn_on_tile 接入预置物系统。
- 测试：test_level_runes.py 15 用例；全量回归 55 文件 404 项全绿。


## 2026-08-07 环境系统 rune（追加）

- env_system_new / env_gbuff_new 解析为 envSystems 并在快照/事件暴露；效果按需单独接线。
- 测试：test_level_runes.py 16 用例；全量回归 55 文件 405 项全绿。


## 2026-08-07 干员技能管线扫描（追加）

- 抽样验证各职业干员技能激活链正常，失败模式为部署触发技能语义（非缺口）。
- 测试：test_operator_scan.py 1 用例；全量回归 56 文件 406 项全绿。


## 2026-08-07 技能效果深度验证（追加）

- 修复真银斩多目标普攻（_operator_attack 读取 attack@max_target）；确认能天使 S3 攻速为等级数据事实。
- 测试：test_operator_skills.py 18 用例；全量回归 56 文件 407 项全绿。


## 2026-08-07 连击类技能（追加）

- 修复能天使 S3 过载普攻本体与连击叠加（替换语义）；验证陈 S3 绝影十连斩正确。
- 测试：test_operator_skills.py 20 用例；全量回归 56 文件 409 项全绿。


## 2026-08-07 火山/治疗验证（追加）

- 验证艾雅法拉 S3 火山（属性/攻速/多目标）与塞雷娅 S2 治疗量均正确。
- 测试：test_operator_skills.py 22 用例；全量回归 56 文件 411 项全绿。


## 2026-08-07 阶段前缀 stat buff（追加）

- 修复二重唱攻速/攻击加成未生效；验证银灰 S1 强力击 burst。
- 测试：test_operator_skills.py 24 用例；全量回归 56 文件 413 项全绿。


## 2026-08-07 弹道穿透双重应用修复（追加）

- 修复弹道命中穿透被计算两次的 bug；验证送董人物穿与 Pith 法穿。
- 测试：test_operator_skills.py 26 用例；全量回归 56 文件 415 项全绿。


## 2026-08-07 百分比穿透/叠加验证（追加）

- 验证莱欧斯百分比穿透与穿透+脆弱叠加一致性。
- 测试：test_operator_skills.py 28 用例；全量回归 56 文件 417 项全绿。


## 2026-08-07 伤害公式矩阵（追加）

- 新增 test_damage_matrix.py 7 用例（防御/穿透/法抗/真实/元素/脆弱/屏障全组合）；弹道回调穿透一致性确认。
- 全量回归 57 文件 424 项全绿。


## 2026-08-07 伤害矩阵边界组合（追加）

- 扩展最小比×屏障/穿透×封顶/双穿透/脆弱×屏障 + 近战穿透路径验证。
- 测试：test_damage_matrix.py 12 用例；全量回归 57 文件 429 项全绿。


## 2026-08-07 部署动画技能计时（追加）

- 修复动画期间技能时计暂停 bug；新增持续时序测试 test_skill_timing.py 2 项。
- 全量回归 58 文件 431 项全绿。


## 2026-08-07 炼金 DoT 计时（追加）

- 验证锡人 S1 区域 DoT 的 1s 触发节奏与 8s 区域寿命。
- 测试：test_skill_timing.py 3 用例；全量回归 58 文件 432 项全绿。


## 2026-08-07 异常打断语义（追加）

- 修复打断后秒释放与异常结束卡 MOVE 两个 bug；完整打断链测试。
- 全量回归 58 文件 433 项全绿。


## 2026-08-07 干员控制语义（追加）

- 修复空旋干员仍攻击 bug；持续技能输出暂停不暂时语义确认。
- 全量回归 58 文件 435 项全绿。


## 2026-08-07 buff 异常免疫（追加）

- 实现 buff abnormalImmunes 免疫检查；全量回归 58 文件 437 项全绿。


## 2026-08-07 元素爆发免疫联动（追加）

- 验证神经爆发空旋对免疫单位跳过、伤害保留；全量回归 58 文件 438 项全绿。


## 2026-08-07 异常组合优先级（追加）

- 确认空旋>冻结>浮空>麻痩优先级与依次结束恢复；全量回归 58 文件 439 项全绿。


## 2026-08-07 关卡加载冒烟（追加）

- 修复 wave 敌人实例键 #N 解析；新增 test_level_loading.py 2 项。
- 全量回归 59 文件 441 项全绿。


## 2026-08-07 无地图关卡修复（追加）

- 修复脚本表元数据关卡加载崩溃；关卡加载冒烟覆盖扩大。
- 全量回归 59 文件 441 项全绿。


## 2026-08-08 波次 hiddenGroup rune（追加）

- level_hidden_group_enable/disable 已实现：build_wave_timeline 保留 hiddenGroup，WaveScheduler 按当前难度 rune 过滤（默认隐藏、enable 放行、disable 优先）；快照暴露 hiddenGroups；被跳过动作发 hidden_group_action_skipped 事件。
- 覆盖数据：641 个关卡带 hiddenGroup 动作，494 enable + 34 disable rune，全部难度掩码支持（NORMAL/FOUR_STAR/ALL）。
- 测试：test_wave_timing.py 6 用例（含 2 项新增）；相关回归（test_level_runes/test_level_loading/test_battle_integration/test_skill_system/test_skill_timing/test_abnormal/test_damage_matrix/test_boss_behavior/test_boss_batch/test_operator_skills）全绿。

## 2026-08-08 波次 SPAWN routeIndex 缺省=0 修复（追加）

- build_wave_timeline 将 routeIndex None 归一为 0?FlatBuffers 缺省值 0 省略字段），spawn_enemy 对 None 按 0 处理；此前 2034 条 SPAWN（涉及 2034 个关卡）被整条丢弃。
- 实测：level_act11d0_01 首条 enemy_1007_slime t=3.0 NORMAL/FOUR_STAR 均生成；测试：test_wave_timing.py 2 用例。
- 相关回归（level_runes/level_loading/battle_integration/skill_system/skill_timing/abnormal/damage_matrix/boss_behavior/boss_batch/operator_skills）全绿。
## 2026-08-08 波次 SPAWN routeIndex 缺省=0 修复（追加）

- build_wave_timeline 将 routeIndex None 归一为 0（FlatBuffers 缺省值 0 省略字段），spawn_enemy 对 None 按 0 处理；此前 2034 条 SPAWN（涉及 2034 个关卡）被整条丢弃。
- 实测：level_act11d0_01 首条 enemy_1007_slime t=3.0 NORMAL/FOUR_STAR 均生成；测试：test_wave_timing.py 2 用例。

## 2026-08-08 波次随机出生组 randomSpawnGroup*（追加）

- 互斥加权组 + 打包组已接入：build_wave_timeline(waves, rng) 构建期逐组加权选择（RandomGroupKey=(wave,fragment,key)），胜者打包组（randomSpawnGroupPackKey 伴随动作）整组生效，失败候选连同打包组删除；空候选发 random_group_empty；事件带 groupKey/packKey/weight/isEmpty，WaveScheduler.random_groups 与 snapshot.waves.randomGroups 暴露胜出信息。
- 数据：643 关卡 / 3105 组 / 10024 候选 / 3562 打包伴随动作；全量 2817 含波次关卡解析零问题。
- 测试：test_wave_timing.py 新增 10 用例；相关回归 129 项全绿。

## 2026-08-08 关卡分支 BranchData 阶段调度（追加）

- 分支游标逐步推进（Scheduler.BranchRuntime / MoveNextLevelBranch 语义）：每次触发调度下一阶段（fragment 式时序），is_loop 回绕；PickRandomBranchPhase 随机选阶段（not_repeat 不重复）；分支动作同样走 hiddenGroup rune 门控与随机出生组解析；挂起分支阶段延迟胜利判定。
- 数据：2913 分支 / 3515 阶段；799 关卡分支含动作（6037 SPAWN + 624 ACTIVATE_PREDEFINED），4 关卡分支带 hiddenGroup，89 关卡分支带随机组。
- 实测：act38side_ex06 fire 分支按难度只出对应敌人、balloon 分支 2/6/30s 精确生成；rogue5_b-9-e 24 阶段游标推进+回绕；rogue5_b-9-a 分支随机组按种子可复现。
- 测试：tests/test_branch_phases.py 7 用例。

## 2026-08-08 LiveServer 实时链路强化（追加）

- 修复 /new 重载后首次 /status、/snapshot 请求卡死数秒：Simulator.battle 为惰性构造，reload 后第一个访问 battle 的请求线程同步构建 BattleController；reload/reload_custom 现在主动预热 battle，/new 请求内完成构建。
- 新增 tests/test_live_server_chain.py 2 用例：/levels 列表、/new 重载、/config 自定义编队+自定义敌人重建、暂停/步进验证自定义敌人生成、HTTP 部署、/events、SSE /stream 快照推送、/editor 与 /enemies 搜索；快照中的 randomGroups/branches/hiddenGroups 经 HTTP JSON 可序列化。
- 回归状态：61 个测试文件、464 项全部通过（分批全量回归，各批全绿）。
## 2026-08-08 场地机制审计与修复（追加）

- tile 效果接入 targetSide 阵营过滤（草/治疗/防御友方专用，流沙/深海/木道/感染敌方专用）；buff 数值改从地块黑板读取（map_tile_blackb 可注入），治疗地块回血端到端验证。
- 全量 95 种 tileKey 100% 有 prefab 定义；6 个未分类脚本族无提取数据（视觉/模式专属），已记录限制。
- env_system_new / env_gbuff_new 为 GlobalEnvSystem 预制体驱动的自定义系统（多数为音频/相机/UI），其 buff 数值不在解包数据中，维持解析+快照暴露，不盲接。
- 测试：test_tile_effects_e2e.py 4 用例；回归状态更新为 62 个测试文件、468 项全部通过。

## 2026-08-08 法术伤害 5% 保底（追加）

- damage.py 法术分支补上 5% 保底：`max(atk_eff*0.05, atk_eff*max(0, 1-mres/100))`，
  与物理一致（NGA/PRTS 公式：法抗 100 仍打 5% 抛光伤害）。
- 穿透顺序不变：先固定穿透后百分比穿透，法抗仍上限 100；保底基于 atk_eff
  （攻击力 x 攻击力倍率），先于脆弱/屏障结算。
- 测试：test_damage_matrix.py 更新 test_magical_vs_mres_cap（120 法抗 0 -> 5），
  新增 test_magical_min_ratio_floor（1000 攻 vs 100/120 法抗 -> 50；vs 20 -> 800）。
- 回归：test_damage_matrix / test_skill_system / test_operator_skills /
  test_abnormal 全绿（65 项）。

## 2026-08-08 敌方技能生效帧按 prefab 标定（追加）

- 数据依据：skill_behavior_catalog / skill_prefab_catalog 中
  EasyToStartAbility._waitForAttackEvent（711 个技能：wait=1 x413、
  wait=0 x150、混合 x41、缺失 x107；45 个 wait=0 技能带校准 OnAttack）。
- skills.py：EnemySkillRun 读取 prefab `_waitForAttackEvent`，
  AbilityRun 仅当 wait=1 时按 OnAttack 帧延迟 `_execute_effects`；
  wait=0 时在 preDelay 结束当帧生效（修复前多等 0.4~3.8s，例如
  霜星 ArcticBlast 1.5s -> 0.933s、W 的 C4 4.4s -> 0.6s 发弹道）。
- 快照 skill_states 新增 waitForAttackEvent 字段。
- 测试：test_skill_system.py 新增 2 项（ArcticBlast wait=0 在 preDelay
  当帧生效且不再等 OnAttack；Faust CriticalHit wait=1 保持 40 帧）。
- 回归：test_skill_system / test_skill_timing / test_boss_behavior /
  test_boss_batch / test_damage_type / test_enemy_buffs /
  test_attack_timing 全绿（54 项，含 2 项新增）。

## 2026-08-08 敌方技能 spell_on 时序补全（追加）

- spell_on 统一语义：wait=1 时 action node、自身 buff、目标效果全部
  在首个校准 OnAttack 帧执行（如浮士德 SummonBallis 分支激活 27 帧），
  wait=0 时在 preDelay 结束当帧执行；生效时刻取 max(preDelay, OnAttack)
  （Lasso preDelay=OnAttack=0.4s -> 0.4s 生效，此前为 0.8s）。
- 修复：preDelay=0 且 wait=1 时首帧等待被误置 0（命中帧立即触发）；
  wait 判定优先读按敌人的行为目录 abilities（共享 prefab 合并污染）；
  黑板解析补 valueStr（SummonBallis branch_id=faust_ballis 此前丢失，
  分支事件 branch 为 None）。
- 测试：test_skill_system 新增 2 项（Lasso max 语义、SummonBallis
  分支 27 帧）；test_enemy_buffs 自身 buff 用例改为推进到首个命中帧
  （wait=1 的 spell_on 语义）。
- 全量回归：62 文件 473 项全部通过。

## 2026-08-08 敌方技能无攻击组件不再打空伤害（追加）

- 全量统计 711 个敌方技能：443 个（62%）无攻击组件（prefab 无
  _damageType 且黑板无 atk_scale*/atk/damage* 键），此前按默认
  atk x 1.0 结算了空伤害（如 SummonBallis 纯召唤/分支技）。
- skills.py `_execute_effects` 新增 has_damage 判定：prefab
  _damageType 或黑板攻击键才结算伤害；stun/ep/prefab buff 与
  action node 不受影响；弹道仅在 has_damage 时发射。
- 测试：test_skill_system 新增 test_no_attack_component_skill_deals_no_damage
  （SummonBallis 无伤害 + CriticalHit 正控仍打 atk x 2.0）。
- 全量回归：62 文件 474 项全部通过。

## 2026-08-08 敌方技能行为目录 buffKeys 接线（追加）

- skill_behavior_catalog 的 buffKeys（1298 个条目 / 524 技能）此前被
  完全忽略，只读了共享 prefab 组件的 _activeBuffs/_buffs；现 EnemySkillRun
  将自指向模板（BUFF_OWNER/BUFF_SOURCE）的 buffKey 接入 self_buffs，
  在 spell_on 施加到施法者（如 Shine -> enemy_trtrsl_s、Eat ->
  enemy_trwlpl_s），治疗/恢复类 buff 模板（HealViaMaxHpRatio 等）经
  BuffSystem 自动触发。
- 安全过滤：buffKeys 是 prefab 级聚合（共用 prefab = 所有使用者的并集），
  只应用键名含本敌方代号（含变体后缀剥离）的条目，避免把其它狼/怪的
  switch_mode / instant_kill 类 buff 错挂到施法者；无模板或仅 TARGET
  语义的键（如 arctic_blast）跳过，仍走 prefab _activeBuffs/黑板。
- 遗留：部分行为 buff 的数值（如 Devour 治愈比例的 ratio 键）不在本地
  buff 表，按 0 处理；组件 _activeBuffs 中个别本属自身的 buff（如
  enemy_trwlpl_s）仍按目标 buff 施放，待 selector/template 分类完善。
- 测试：test_enemy_buffs 新增 2 项（Shine 行为 buff 落到自身；ArcticBlast
  目标 debuff 不上施法者）；原窗口自身 buff 用例改为只断言组件
  BuffToOwnerDuringAbility 缓冲（remove_on_end=True）。
- 全量回归：62 文件 476 项全部通过。

## 2026-08-08 敌方技能 prefab buff 自身/目标分类修正（追加）

- EnemySkillRun 提前解析按代号过滤的自身行为 buff 键集
  (_behavior_self_keys)，prefab _activeBuffs/_buffs 中同键条目不再
  当目标 buff 施放（修掉 enemy_trwlpl_s 被挂到干员身上、以及
  enemy_mupenb_start_count_down 被当目标 debuff 的旧分类）。
- 行为目录按模板 BUFF_OWNER/BUFF_SOURCE 判定自身语义；Countdown 标记
  模板经 TriggerEnemySkill(BUFF_OWNER) 确认确属自身 buff。
- 测试：test_enemy_buffs 新增 1 项（enemy_trwlpl_s 只落自身不落目标）；
  test_enemy_prefab_aliases Countdown 用例改为断言自身 buff。
- 全量回归：62 文件 477 项全部通过（含更新后断言）。
- 遗留：Devour 等共享 prefab 仍残留其它敌人代号的目标 buff 泄漏
  （enemy_nhkodo_devour 等挂到目标），待组件级按 buffKey 归属再过滤。

## 2026-08-08 敌方治疗实际生效（追加）

- buff_templates._n_HealViaMaxHpRatio 默认黑板键修正：优先读
  hp_ratio（游戏节点缺省键），否则回退 ratio。此前敌方治疗模板
  （Heallarva hp_ratio=0.02、CostHealHit 0.05、ChangeType 0.2 等）
  全部按 0 回血。端到端：Heallarva 施放后治疗 6500x0.02=130 精确命中。
- 行为 buffKeys 过滤扩展：无代号但为自指向治疗模板（HealViaMaxHpRatio /
  FixedValueHeal + BUFF_OWNER/BUFF_SOURCE）的共享键也挂到施法者
  （如各吞噬者的 bldkgt_t_devour），不再只收本代号键。
- 验证与限定：_atkScale==0.0 属共享 prefab 合并噪声（52 个真实伤害
  技能如 Shining/Fireball/BloodPool 均为 0.0），不据此判无伤害；
  治疗技能附带弹道的伤害部分仍按现状（atk x 1.0），待后续用
  selector/条件逻辑细分。
- 测试：test_enemy_buffs 新增 test_enemy_heal_via_max_hp_ratio。
- 全量回归：62 文件 478 项全部通过。

## 2026-08-08 动态 buff 地块模式切换（追加）

- SwitchDynamicBuffTileMode 从观察者事件升级为真实状态变更：battle
  按 (row,col) 记录 tile 模式（_tile_modes），INDEX 设置 modeIndex、
  FLIP_BOOL 翻转；REED_TILE 全图芦苇切换（0=熄灭/1=燃烧，来自
  tile_reed dynamicBuffs 两档）。切换时移除格上单位旧模式 buff，
  下一帧地块效果按当前模式重挂（buff_reed_extinct -> buff_reed_flaming）。
- tile_effects._apply_tile_template_buffs 改为只挂当前模式的
  dynamicBuffs 条目（此前两档全挂，芦苇同时带熄灭+燃烧）。
- 快照新增 tileModes；事件按格输出 tile_mode_switch。
- 测试：test_tile_effects_e2e 新增 reed 模式切换端到端（熄灭->燃烧、
  tileModes）；test_skill_system action-node 用例改按类型断言。
- 全量回归：62 文件 479 项全部通过。

## 2026-08-08 IgniteAllReedTile 真实点燃（追加）

- IgniteAllReedTile 从观察者事件升级为真实状态变更（“领袖”Arson
  纵火）：全部芦苇地块切到 mode 1（燃烧），复用上一轮的
  switch_tiles_mode；tiles_ignite 汇总事件保留。
- 测试：test_tile_effects_e2e 新增 ignite 端到端（熄灭->燃烧、
  tileModes）。
- 全量回归：62 文件 480 项全部通过。

## 2026-08-08 敌方弹道技能径向 AoE（追加）

- 弹道技能命中时按 blackboard range_radius 做径向溅射（命中点周围
  所有干员同时结算伤害/stun/EP/prefab buff）。88 个技能带效果半径，
  其中 30 个为弹道型（霜星 ArcticBlast 2.5、W 的 C4 2.5、Fireball 20、
  MistBomb 2.0、Chain 2.0、Bubble 5.0 等）。
- 非弹道直击型（塔露拉 DragonFire 100、Electrify 15、ShieldBurst 3 等
  58 个）仍按单目标近似：龙火为全图型、ShieldBurst 以自身为中心、
  EnemyLine/AllyLine 为线型，需 selector/条件逻辑细分，已记录。
- 测试：test_boss_behavior 新增 frost star AoE 用例（2.5 内两干员同时
  受伤、圈外干员不受击）。
- 全量回归：62 文件 481 项全部通过。

## 2026-08-08 敌方全图型直击 AoE（追加）

- 直击（非弹道）技能 range_radius >= 10 视为全图：命中所有干员
  （塔露拉变体 DragonFire 100、磐蟹 Electrify/Roar 15、Punch 13、
  EnemyLine 10 等 8 个技能）。小半径直击仍需 selector 区分
  自身中心（ShieldBurst）/线型（AllyLine）等，已记录。
- 备注：DragonFire 的 dragon_fire.* 点按 buff 尚未建模（其 baseDamage/
  addOnDamage 键带大写 Damage，has_damage 判 False，直伤不触发），
  待 buff 事件接线；bb 'atk' 键的倍率/加值语义仍按默认 1.0。
- 测试：test_boss_behavior 新增 map-wide 用例（Punch 全图三干员同受击）。
- 全量回归：62 文件 482 项全部通过。

## 2026-08-08 塔露拉龙火持续伤害 + 空模板键修复（追加）

- DragonFire DoT 全链路接通：dragon_fire buff（DB 表 + 计时模板）
  创建 dragon_fire[damage]，ON_BUFF_TRIGGER 执行新增节点
  BleedingDamagePerSec（PURE 伤害 = baseDamage + addOnDamage 按
  addOnDuration 线性爬坡）与 BleedingDamageIncreasingReset（占位）。
  实测 200+200/15s 爬坡：213.3 -> 226.7 -> 240.0 精确命中。
- materialise_buff 支持 stripBlackboardParamsWithBuffKey：skill 黑板
  的 <buffKey>. 前缀键（dragon_fire.duration/baseDamage/...）去前缀
  后供 buff 读取。
- 修复 DB 合并 bug：prefab buff 的 templateKey='empty' 占位不再覆盖
  DB 真实模板键（_apply_buff_data，aura 路径同步），此前 DB 加载类
  prefab buff 全部静默失效。
- test_live_server 改为轮询到 tick>=200 再断言（原固定 3s 睡眠在
  满缓存时可能推进到漏怪失败线，属时序抖动）。
- 测试：test_boss_behavior 新增龙火 DoT 爬坡用例。
- 全量回归：62 文件 483 项全部通过。

## 2026-08-08 敌方技能 bb atk 键按攻击倍率解析（追加）

- 攻击型技能（prefab _damageType 或带弹道）的 blackboard 'atk' 键
  作为攻击倍率（Electrify 0.5、Roar2 0.2、PowerHit 0.8、dsbish 1.5），
  此前全部按 1.0 结算；负值（AtkDesWeaken -0.5、SandStorm -0.7）是
  攻击减益而非倍率，不采用。
- _has_attack_component 细化：纯 buff 技能（AtkUp/InspireEnemy 等
  无 damageType 无弹道、仅 bb 'atk'）不再打空伤害。
- prefab _atkScale 回退保留真实非默认值（GaeBulg_Attack 2.5 唯一
  依赖）；0.0 合并噪声仍按 1.0。
- 测试：test_skill_system 新增 bb atk 倍率用例（Electrify/Roar2 精确
  倍率、AtkUp 零伤害）。
- 全量回归：62 文件 484 项全部通过。

## 2026-08-08 敌方技能负 atk 键接为攻击减益（追加）

- blackboard 'atk' 负值接线为目标攻击减益：直击与弹道命中都在
  目标上施加 atk mul 层（x(1+value)，-0.5 -> x0.5）；若 prefab
  减益 buff 已落地（AtkDesWeaken lfkght_s[weaken]、SandStorm
  mousek_s_2[debuff]，经上轮空模板键修复后已可物化）则不再兜底，
  避免双重施加。
- 实测：AtkDesWeaken 524 -> 262（x0.5）、SandStorm 524 -> 157
  （x0.3），窗口内精确。
- 测试：test_skill_system 新增负 atk 减益用例。
- 全量回归：62 文件 485 项全部通过。

## 2026-08-08 敌方治疗类技能目标选择（追加）

- blackboard 带 heal_scale 的敌方技能（圣堂保育员 RangeHeal
  heal_scale 2/3、range_radius 2.5、max_target 3/5）不再按伤害
  处理：施放时治疗施法者周围 range_radius 内、血量比例最低的
  至多 max_target 个友军，每人 atk x heal_scale（封顶至满血）；
  干员与范围外敌人不受影响。
- 测试：test_enemy_buffs 新增 healer 用例（范围内友军回满、范围外
  与干员不受影响）。
- 全量回归：62 文件 486 项全部通过。

## 2026-08-08 敌方攻击型小半径 AoE（追加）

- 攻击型（prefab _damageType）直击技能 range_radius 在 (0,10)
  时按命中点径向溅射：范围内所有干员同时结算伤害/stun/EP/prefab
  buff（Roar1 5.0、CombatAoe 1.6、BigBomb 2.0、fishing 4.0、Prey
  1.5 等），此前只命中单一目标。
- 仅对攻击型技能扩展：纯 buff/召唤类（AddEnergy、ChangeType、
  CaptureLrssia 等对友军/自身生效）保持单目标，避免错投；自身中心
  （ShieldBurst）与线型（AllyLine）仍待 selector 细分，已记录。
- 备注：combat_atk_scale 等 atk_scale 变体键仍按默认 1.0（数据中
  少量出现，语义待确认），已记录。
- 测试：test_boss_behavior 新增小半径 AoE 用例（CombatAoe 圈内两
  干员受击、圈外不受）。
- 全量回归：62 文件 487 项全部通过。

## 2026-08-08 敌方 atk_scale 变体键回退（追加）

- 无普通 atk_scale/atk 键时，取黑板首个干净的 atk_scale 变体键作为
  攻击倍率（magic_atk_scale 3.0、combat_atk_scale 2.0、
  atk_scale_boom 2.0、atk_scale_main 1.2、blockee_atk_scale 2.8 等
  59 个技能）；排除 dot 键（DoT 倍率）与命名空间键（如
  enemy_trcerb_s3_debuff.atk_scale_cur 减益参数）。
- 实测：M0SplashCannon 1000 攻 -> 3000 法术伤害（magic_atk_scale
  3.0）命中弹道精确。
- 测试：test_skill_system 新增变体倍率用例。
- 全量回归：62 文件 488 项全部通过。

## 2026-08-08 死亡触发 buff 事件 ON_OWNER_KILLED（追加）

- BuffSystem 新增 on_owner_killed：单位死亡（apply_damage 结算后）
  对其所有带 template_key 的 buff 分发 ON_OWNER_KILLED 模板事件。
  覆盖 202 个死亡触发模板（梅菲斯特无人机死亡治疗 enemy_cnvbln[killed]、
  死亡召唤 enemy_dead_spawn、死亡回费 die_to_add_cost 等），此前全部
  静默失效。
- 实测：带 die_to_add_cost（bb cost 5）的敌人死亡后部署费用 +5。
- 测试：test_enemy_buffs 新增死亡触发回费用例。
- 全量回归：62 文件 489 项全部通过。

## 2026-08-08 死亡分裂：FilterDeathReason + SummonEnemiesFollowMyRoute（追加）

- 死亡原因标记：普通击杀 KILLED、落穴 FALLDOWN（落穴死亡也触发
  ON_OWNER_KILLED）、进蓝门 REACH_EXIT；FilterDeathReason 门控
  按其匹配。
- SummonEnemiesFollowMyRoute：死亡分裂按 owner 格召唤 enemyKey x
  count（节点或黑板提供，如 enemy_dcolle_bonore[action] 召唤
  enemy_1367_dseed）。
- 实测：正常击杀分裂 1 只种子；FALLDOWN 死亡不分裂（分裂类敌人
  掉洞不再产生小怪）。
- 测试：test_enemy_buffs 新增死亡分裂跳过落穴用例。
- 全量回归：62 文件 490 项全部通过。

## 2026-08-08 buff 模板节点批量补齐（追加）

- 新增节点：CheckAbnormalFlag / CheckUnitAlive / CheckBlocked /
  CheckEnemyId / CheckFilterTag / FilterByBlackboardValue /
  AssignValueToBB / InstantKill / FinishBuffsById / ModifySp。此前这些
  高频门控/动作节点在 buff 链中被跳过（gate 保持 True），导致后续
  动作无条件触发或整链失效。
- InstantKill 目标解析修正：buff 在施放期间触发时 TARGET 解析到技能
  当前目标（吞食类击杀对象，如 bldkgt_t_devour 击杀被吞噬者），无
  施放上下文时回退 BUFF_OWNER（自杀类 buff）；修复新启用 InstantKill
  后吞噬类 buff 误杀自身的问题。
- 测试：test_buff_templates 新增门控/动作节点用例（沉默门控、黑板
  值比较、赋值、SP 修改、删 buff、击杀）。
- 全量回归：62 文件 491 项全部通过。

## 2026-08-08 buff 门控节点第二批（追加）

- 新增：IsBlackboardZero / IfTarget / FilterByBuffStackCount /
  FilterByTargetHpRatio / Dice（battle RNG 概率门）/ CheckContainsDerviedBuff /
  CheckUnitCurrentMode。此前这些门控被跳过（gate 恒 True）会让后续
  动作无条件触发，现按真实条件判定。
- 测试：test_buff_templates 新增门控用例（零值、buff 层数、血比、
  派生 buff、模式、目标存活、概率 0/1）。
- 全量回归：62 文件 492 项全部通过。

## 2026-08-08 buff 黑板操作节点（追加）

- 新增：BlackboardAdd（链黑板加值，可选 maxKey 钳制）、
  FinishDerivedBuffById（删 buff）、AddBuffBlackboard /
  AssignBuffBlackboard（读写目标 buff 的 blackboard，支持叠加计数
  如 dsdevr_swallow_counter）。此前这些节点被跳过，叠加计数类 buff
  链失效。
- 测试：test_buff_templates 新增黑板节点用例。
- 全量回归：62 文件 493 项全部通过。

## 2026-08-08 buff 杂项节点（追加）

- 新增：LogExtraBattleInfo（battle_log 观察事件）、FixedValueDamage
  （固定值伤害，damageKey 或 atk x atkScaleKey）、
  AssignBuffBlackboardFromOthers（跨 buff 黑板值拷贝）、
  TriggerEnemySkill（按 prefabKey 触发敌方技能，skill_trigger 事件
  + EnemySkillController.force_trigger 真实施放）。
- 测试：test_buff_templates 新增杂项节点用例。
- 全量回归：62 文件 494 项全部通过。

## 2026-08-08 buff 节点第三批（追加）

- 新增：IsDamage / IsHeal（事件类型门控）、DamageViaMaxHpRatio
  （maxHp x 比例伤害）、FilterByTargetSpRatio（SP 比例门控）、
  AssignBuffCountIntoBlackboard（buff 层数写入黑板）、
  AssignAttributeToBB（单位属性写入黑板）、ChangeMotionMode
  （WALK/FLY 切换）、TriggerBuff（当前 buff 强制触发 ON_BUFF_TRIGGER）。
- 测试：test_buff_templates 新增 batch3 用例。
- 全量回归：62 文件 495 项全部通过。

## 2026-08-08 buff 节点第四批（追加）

- 新增：AOEDamage（按 targetSide 与 range_radius 范围伤害）、
  FinishDerivedBuff（结束当前 buff）、CreateBuffStacked（内嵌叠加
  buff 物化）、ModifyBlackboard（链黑板设值/叠加）、InterruptAbility
  （中断当前施法）。
- 测试：test_buff_templates 新增 batch4 用例（范围伤害、自结束 buff、
  黑板叠加、施法中断）。
- 全量回归：62 文件 496 项全部通过。

## 2026-08-08 buff 节点第五批（追加）

- 新增：CheckAbnormalFlags（多异常任一命中门控）、
  CreateBuffToCertainSideUnits（按阵营给全场单位挂内嵌 buff）、
  FilterDamageModifer（伤害类型门控）。
- 测试：test_buff_templates 新增 batch5 用例。
- 全量回归：62 文件 497 项全部通过。

## 2026-08-08 buff 节点第六批（追加）

- 新增：AtkScaleUp（攻击倍率黑板写入）、AttributeModifierWithBB
  （按 bb 值施加属性修饰，走 buff 系统以同步 maxHp）、
  SummonEnemyWithRuntimeRoute（传送/运行时路线召唤，支持 FLY 与
  unharmful，如 lrccon transport）。
- test_ui_click_flow HTTP 客户端超时 5s -> 20s（全量回归负载下
  /action 步进+快照可能超 5s，属时序抖动非玩法回归）。
- 测试：test_buff_templates 新增 batch6 用例。
- 全量回归：62 文件 498 项全部通过。

## 2026-08-08 buff 节点 CancelModifier（追加）

- 新增 CancelModifier：移除目标单位所有带 stat 修饰的 buff（add/mul/
  final 层），纯标记类 buff 保留。
- 顺带核对：干员侧主要分支（skywalker/traper/alchemist/craftsman）
  与珊比天赋、锡人 S2 均已有集成测试（文档旧标注已过期）。
- 测试：test_buff_templates 新增 CancelModifier 用例。
- 全量回归：62 文件 499 项全部通过。

## 2026-08-08 buff 节点 SummonEnemiesFollowMyRouteWithBuff（追加）

- 新增：死亡分裂带 buff 召唤——按 bb/节点键召唤敌人并立即挂载
  内嵌 _noSourceBuff（_addNoSourceBuffImmediately），支持 unharmful
  标记；与 SummonEnemyWithRuntimeRoute 共同覆盖带 buff/传送类召唤。
- 测试：test_buff_templates 新增带 buff 召唤用例。
- 全量回归：62 文件 500 项全部通过。

## 2026-08-08 buff 节点第七批（追加）

- 新增：ModifyAbilityBlackboardAndCast（把链黑板值写入指定能力
  黑板并施放，如 buff 缩放的 Poison）、CheckCharSkillAffecting
  （近似门控：目标身上是否存在干员技能来源的 buff）。
- 测试：test_buff_templates 新增 batch7 用例。
- 全量回归：62 文件 501 项全部通过。

## 2026-08-08 buff 节点 CreateBuffUseAbilitySelector（追加）

- 新增：CreateBuffUseAbilitySelector（剩余最大计数节点，231 次）——
  把内嵌 buff 施加到解析目标（selector 近似：目标/施法者，如
  charge_gunctrl 的 sp_reduce buff）。
- 测试：test_buff_templates 新增 selector buff 用例。
- 全量回归：62 文件 502 项全部通过。

## 2026-08-08 buff 节点 EmitProjectile 增强（追加）

- EmitProjectile 由简单存根升级：支持 bb projectile_key 回退与
  _buffDataList 命中挂 buff，来源/目标按节点解析。
- 测试：test_buff_templates 新增弹道挂 buff 用例。
- 全量回归：62 文件 503 项全部通过。

## 2026-08-08 buff 节点第八批（追加）

- 新增 11 个节点：ModifyLifePoint / HpRatioTrigger / MoveNextLevelBranch /
  CheckEnemyUnbalanced / IsCharacter / IsCharacterOrTokenOrTrap /
  ClearCharacterSp / CheckCharacterDefaultDirection / CheckTargetProfession /
  CheckModifierContainsKey / ModifyAbilityBlackboard。
- 冰面 tile_icestr[cold] 的 IsCharacterOrTokenOrTrap 门控现正确生效：
  敌方走 c2e_cold 分支（旧测试在门控未实现时误判为 e2c_cold，已按
  模板数据修正断言）。
- 测试：test_buff_templates 新增 batch8 用例。
- 全量回归：62 文件 504 项全部通过。

## 2026-08-08 buff 节点第九批（追加）

- 新增：DamageViaAttr（按属性值伤害，如 DEF）、CreateBuffToToken
  （给召唤者 token 挂 buff）、CheckSkillIndex（装备技能序号门控）、
  AddGlobalBlackboard / AddCharacterSharedBlackboard（全局/共享黑板
  写入，链黑板近似）。
- 测试：test_buff_templates 新增 batch9 用例。
- 全量回归：62 文件 505 项全部通过。

## 2026-08-08 buff 节点第十批（追加）

- 新增：FixedValueHeal（固定值治疗）、CheckAbnormalImmune（异常免疫
  门控）、ReleaseFromBlocker（解除阻挡）、IfEnemyIsMovingBySelf
  （自主移动门控）、CreateBuffToBlockee（给阻挡者挂 buff）、
  CheckEntityDisappeared（消失/死亡门控）。
- 测试：test_buff_templates 新增 batch10 用例。
- 全量回归：62 文件 506 项全部通过。

## 2026-08-08 buff 节点第十一批（追加）

- 新增：CreateBuffInCircleRange（圆范围阵营 buff）、
  CreateBuffUseTargetAsSource（目标作来源挂 buff）、AddAbilityBlackboard
  （能力黑板加值）、AttachAsDerivedBuffById（按键挂派生 buff）。
- 测试：test_buff_templates 新增 batch11 用例。
- 全量回归：62 文件 507 项全部通过。

## 2026-08-08 buff 节点第十二批（追加）

- 新增：TriggerAbilityUseSelector（按名触发能力）、
  CheckHasEnemyInRange（范围内有敌门控）、ModifierScaleUp（占位）、
  SpShowBuff / CreateCardBuff（观察事件，卡牌系统未建模）。
- 测试：test_buff_templates 新增 batch12 用例。
- 全量回归：62 文件 508 项全部通过。

## 2026-08-08 buff 节点第十三批（追加）

- 新增：InterruptCharacterSkill（中断干员技能）、IsElementDamage
  （元素伤害门控）、SetBodyDirection（朝向设置）、
  IsBlackboardEqualWithString（字符串黑板比较）、CheckCurrentTileKey
  （地块键门控）、CheckMotionMode（运动模式门控）、
  FilterByGlobalBlackboard（全局黑板比较）、TriggerSkill（技能触发）。
- 测试：test_buff_templates 新增 batch13 用例。
- 全量回归：62 文件 509 项全部通过。

## 2026-08-08 buff 节点第十四批（追加）

- 新增：IfTargetEqual（目标相等门控）、Evade（伤害类型闪避门控）、
  CreateBuffToHost（宿主挂 buff）、CompareCharSkillAvailableCnt
  （可用技能数比较）、VertifyTarget（阵营目标校验）、
  FilterAbilityName（能力名门控）、UpdateAbilityCoolDown（技能冷却
  写入）。
- 测试：test_buff_templates 新增 batch14 用例。
- 全量回归：62 文件 510 项全部通过。

## 2026-08-08 buff 节点第十五批（追加）

- 新增：CheckUnitEnemyId（敌人键门控，委托 CheckEnemyId）；核对确认
  DamageScale / EpDamageScale / AdvancedApplyDamage 已有完整实现，
  并新增 DamageScale 伤害上下文缩放用例（isOneMinus 100 -> 80）。
- 全量回归：62 文件 511 项全部通过。

## 2026-08-08 buff 节点第十六批（追加）

- 新增：CheckHasAllyInRange（范围内友军门控）、
  InsertCheckPointInRuntimeRoute（WAIT_FOR_SECONDS 路径等待点插入，
  暂停敌人 _time 秒）。
- 测试：test_buff_templates 新增 batch16 用例。
- 全量回归：62 文件 512 项全部通过。

## 2026-08-09 ???? buff ????????

- ?????`skchr_rdoc_2` ????????????+200?????
  `rdoc_s2[heal]` ??? `_projectileKey` ???? Ability ???
  `_activeBuffs` ???????????? on_start ???????
  abnormalFlags?heal ?????????????????????
  AdvancedApplyHeal?
- ??????????????? key ??????_projectile_belongs?
  ???? _damageType?? _activeBuffs ??????????????
  ???????_fire_burst._cb / _rdoc_s2_fire????
- ?????1512 ???? prefab ? 97 ??????????
  _activeBuffs??? S2/S3 stun??? S1 ?? heal????? S2?
  ??/??/??/?????????????8 ????????? S1
  mberry_s_1??? S1?turdus S2 ?????????????
- ???test_rdoc_skills + test_buff_templates 39 ????
  ???? 62 ?? 513 ??????

## 2026-08-09 buff ?????/????FilterByTargetAttribute / Loop / SummonEnemiesFollowBranchRoute / InverseDamage????

- FilterByTargetAttribute?24 ???????????BLOCK_CNT/MASS_LEVEL/
  MOVE_SPEED/MAX_HP?LE/GE/LT/GT/EQ?_useFloat ?? _valueFP/_value??
- Loop?18 ???_keyMappingList ???? source bb ??? target bb ?
  ?? body?_stopWhenPreviousSucceed ????? bool True ?????
  ????"skipped" ???????????????? _loopCntKey ? bb
  ?????????????????? 100 ?????
- SummonEnemiesFollowBranchRoute?27 ???owner ??????key ?
  _overrideEnemyKey / bb enemy_key / summon_enemy_key?count ? bb??
  ?? _unharmful ??? _buffToEnemy ???trap_bgarmn sync_hp ???
- InverseDamage?26 ???ON_TAKE_DAMAGE ???????????? T2
  ???????????????? atk?15% ?????enemy_ltnclo ??
  ???????_damageType/_damageTypeKey ?????????????
  ????? _sideMask?????????=1/??=0?? _hasSource?
  ???? bb[_damageValueKey]?_fixValue=false ????????
- ???test_buff_templates ?? batch18/19 ???????? 62 ??
  515 ??????

## 2026-08-09 buff ???????HealViaDamage / CheckHasSp / KillTokens / AOEHeal / FinishManagedProjectiles????

- HealViaDamage?6 ?????????? ON_AFTER_OUTPUT_DAMAGE ????
  ?battle.apply_damage ????? ON_OUTPUT_DAMAGE ?????? owner =
  ?????? x bb[vampire.heal_scale / heal_scale / heal_ratio]?
  ??????????? talentBlackboard vampire.heal_scale=1.5?
  PRTS ???????????????????? 150% ??????
- CheckHasSp?23 ???SP ?????_checkHasSp 1/0??? 0 or 1 ????
- KillTokens?14 ?????????? token??? buffKey ????
- AOEHeal?5 ?????????? S2??????????? 8 ??????
  ?? ltnhap ?????_sourceSideType ???? ALLY ???????
  ???? ALLY ????????? _rangeId / ???? / ?? 3x3?
  _excludeTarget ?????ignoreHealFree ???
- FinishManagedProjectiles?22 ?????????????enemy_mpprme
  ?????
- ?????module_stats.json / trust_prts.json ???
  ark_parser/character/data??? damage_calculator/data ???????
  ?? test_modules 4 ??????????????? loader ????
  ?496 ?? / 412 ????????????????
- ???test_buff_templates ?? batch20 ??????? 62 ?? 516 ?
  ?????

## 2026-08-09 TRY_SET_HP_ZERO ???????????

- ?? ON_BEFORE_TRY_SET_HP_ZERO / ON_POST_TRY_SET_HP_ZERO ???
  battle.apply_damage ?????blaze2 ?? / dollkeeper ?????
  take_damage ????????????? BEFORE ??damage ctx ??
  _hp_zero_consumed / _hp_zero_blocked ???
- ConsumeTrySetHpZeroModifier?29 ?????????????
  _dontConsumeWhenUndeadable ??????????_blockThisHpSet
  ??????????? battle ????? hp-1 ??? POST ??
- IsConsumerOfTrySetHpZeroModifier?19 ???POST ????????
  ?????????CreateBuff / FinishBuff??
- ????????? T2????????? -> ????? -> HP ?? 1
  -> ON_POST ? surtr_t_2[undeadable]?UNDEADABLE ???-> FinishBuff
  ????????????????????????????????
  ??????? T1 / ??????? POST ? MAX_HP/?? buff??
- ???test_buff_templates ?? batch21????? 62 ?? 517 ???
  ???

## 2026-08-09 ???? + ????????

- RewriteTileOptions?33 ?????????????TileData ??
  _passable_override?__slots__ ????GameMap.rewrite_tile_passable /
  restore_tile_passable ??????????????????????
  ?????????_isObstacleLike=true ????????/?????
  ????_restoreTileOptions=true ???
- AssignRootTileToBB?25 ??????/???? tile_key ?????
- AssignGridPositionToBlackboard?24 ?????????????
  ?aglina_m23[record_position] ???
- IsBlackboardEqualWithFloat?23 ???bb ? == ?????
- FilterByTargetHp?19 ??????? HP ?????LE/GT ???
- AssignDirectionToBB?18 ????????????_isReverse ???
- ???test_buff_templates ?? batch22/23????? 62 ?? 519 ?
  ?????

## 2026-08-09 buff ?????????/??/SP/??????????

- CheckDirection?19 ???source ? target ???????EQUAL/OPPOSITE?
  blower_s_character??
- CheckFaceDirection?16 ??????? == ?????UP/RIGHT/DOWN/LEFT?
  enemy_cliff_blink ??????
- UpdateEnemyCurrentTile?20 ???????????? row/col?????
  ?? enemy_durokt[fly] / enemy_mheagl_fly??
- AssignDamageValueToBlackboard?18 ???????/??????
  _scaleKey ????? bb['value']?hbisc2_tr ???????
- AssignCurSpToBB?12 ??????? SP ? SP ???????
- AssignModifierValueIntoBlackboard?19 ?????????????
  ?enemy_muwiz_t[shield] ???enemy_lrtsia ????
- CheckTargetInRange?16 ?????? source ? rangeId ?????
  ?acdrop_t_1 / ceylon_trait ????????
- ???test_buff_templates ?? batch24????? 62 ?? 520 ???
  ???

## 2026-08-09 ??????????

- ???????TileData._overlap_enabled?????????Unit
  ??._overlap_source_ids????????? id ????
- SetTilesEnableOverlap?10 ????? owner ????? offsets ???
  ?????trap_ftshad ?? / mylyss ???ostn ?? 8 ???
- ModifyOverlapSourceId?41 ??????????/???????? id
  ?trap_102_mhwrbg ????????trap_trpot ?????ubodst?
  ?? winfire ??????
- ????battle._check_enemy_overlap ???????????????
  ???????? ? ??? key ? ??????? ? ????????
  ??? ON_ENTITY_WILL_OVERLAP / ON_OWNER_OVERLAPPED ??????
  ?source/target ???????? trap_trpot_mark ????????
  trap_tjggt[passive] ????? highland_common[block] ???
- ???test_buff_templates ?? batch25????? 62 ?? 521 ???
  ???

## 2026-08-09 SwitchSide ????????

- SwitchSide?8 ???????????? ALLY/ENEMY?????
  enemy_trspsb_eating????? trap_mptxs_mark????? burn ?? /
  extinguish ???wpnsts_change_side ???
- ?????side 0->1?? update_enemy_ai ?????????/???
  ??????????_markEnemyKilled ???????buff ??/??
  ?enemy_trspsb_mark ON_BUFF_FINISH???? ENEMY ?????
- ??buffs.remove ??? ON_BUFF_FINISH?????????????
  ?????????
- ???test_buff_templates ?? batch26????? 62 ?? 522 ???
  ???

## 2026-08-09 buff ??????????/??/??/????????

- IfDamageTargetSide?14 ?????????????? S2 / folnic S2
  ?????????? side???=0/??=1??
- RandomSetter?12 ???battle RNG ????????amgoat T2 ?? SP?
  enemy_xdbird ???????? SystemRandomClone.next_float ????
  ?????
- AssignModifierRealDeltaToBB?19 ?????????????
  ?trap_ftshad[ep_damage] last_damage?pyczog loss_hp??
- CheckTargetGridPositionRowOrColWithBB?28 ??????/?? bb ???
  ???agbmes_t12_s1 ??????
- DamageByDistance?18 ??????????????? S3 ????
  rupture?bb value x ???????interval 0.066s?_isInit ????
  ???????????????????
- CreateBuffToUnitId?19 ?????? key ?????? buff
  ?enemy_ubbplwq ?????? / ??????
- ???test_buff_templates ?? batch27????? 62 ?? 523 ???
  ???

## 2026-08-09 buff ??????????/SP/??/UID ??????

- SetDisappear?11 ???????/?? DISAPPEAR ???enemy_mpplai
  passive P0 ????????????????
- ClearEnemySp?11 ????????? SP?enemy_dhnzzh P2?agpack
  ??????
- PickRandomBranchPhase?11 ????? battle.execute_branch_random ??
  ?????????csdoll ??????/???branch id ? bb ? owner
  ???_notRepeatInOneLoop ???????
- AssignUidToBlackBoard?11 ????? inst_id?_assignAsInt?? key
  ?????agbmal/agbomb ?? modifier source??
- CreateBuffWithOverrideEffect?11 ????? CreateBuff ???_effectKey
  ??????horn S2 ??? s2_effect buff ???
- FilterByTargetSPType?11 ??????? SP ?????INCREASE_WHEN_
  ATTACK=2?? SP ????????odda S1 / archet ????
- CheckMainBuffId?11 ???????????? ON_OTHER_BUFF_START ??
  ???recat/necras ?????
- ???test_buff_templates ?? batch28????? 62 ?? 524 ???
  ???

## 2026-08-09 ON_OTHER_BUFF_START ?? + CheckMainBuffId????

- ?? ON_OTHER_BUFF_START ???buffs.apply ???? buff ????
  ON_BUFF_START ?????????????? buff ??
  ON_OTHER_BUFF_START?extra_bb ?? _other_buff_key ? buff key??
- CheckMainBuffId?11 ????? bb._other_buff_key == _idToFilter
  ?halo2_t_2 ???? T2 ?? sluggish ????? buff?recat ?? /
  necras ?????
- ??????e ? halo2_t_2 ?? sluggish buff -> halo2_t_2[attack_speed]
  ????????? key?stun??????
- ???test_buff_templates ?? batch29????? 62 ?? 525 ???
  ???

## 2026-08-09 buff ????????????/HP ??/????????

- EpDamageScale?19 ???????????? S2 / element_resistance?
  _isOneMinus ?? 1-x??
- DamageViaCurHpRatio?12 ????? HP x bb hp_ratio ?????
  ?? S2 ??????????? 50% ?????akafyu ?????
- CheckUnitInRebornState?17 ?????/???????mhrors ???????
- CheckUnitInDisappearState?15 ???DISAPPEAR ?????cripple/
  mmjump ??????
- CheckBuildableType?17 ???????? buildableType ??
  ?MELEE=1/RANGED=2?zebra ??????
- CheckEntityEquals?11 ????????????????? token ?
  ??????bgball ??????
- FilterModifierTargetType?11 ?????????????HP/SP??
- CheckEnemyLevelType?15 ????????????NORMAL/ELITE/BOSS??
- FilterByShieldValue?8 ??????barrier???????mcnist ??
  ????
- CreateBuffToUid?8 ???? bb uid ??? inst_id ????? buff
  ?misery ?? / ubprison ???
- EqualizeTargetHpRatio?8 ????? HP ?????bgarmn ???? HP?
  fttreant ?????
- MarkCurrentHpRatio?14 ??????? HP ?????/????
  ?smephi ??????
- CheckCost?14 ????????????strong/notin ????
- HpRatioToAttributeAdd?14 ???? HP ?????????/? T1 ??
  ????????bb value x ratio add ???
- ???test_buff_templates ?? batch30????? 62 ?? 526 ???
  ???

## 2026-08-09 buff ????????????/??/??/????????

- CheckAbnormalCombo?18 ??????????SLEEPING=DOZE flag 43 ??
  _isUnset ?????/??????????
- CheckIfSourceGridPosFaceTargetGridPos?20 ?????????????
  ??/???enemy_mhkryk ????????
- UpdateBuffAttributeModifier?19 ???????????blkswb ??
  ???bb ???????
- AssignBuffBlackboardFromAbility?17 ???????????? buff ??
  ?enemy_mjcdog GetChar ??/????
- CheckHasCharacterInRange?9 ???????????/token?hlslp ???
  aglina ??????? token/?????????
- ForceSetToTilePosition?9 ????????????cjdoor ????
  cjtaot ?????????????
- CheckEnemyDirection?10 ??????????_useBB ??????
- RandomCreateBuff?8 ?????? buff ??????haak T1 ????
  tomimi S2??
- SwitchDirection?8 ???????????????????? ally/trap??
- SaveHpToDynamicVar?8 ??????? HP ??????lrtsia ??????
- CheckTriggerable?8 ????????brownb S2 / c2e_cold ???
- ModifyCharacterLimit?8 ????????????farm S1 / hlnpcm ???
  ??? battle ????
- ???_source_unit ???? MODIFIER_SOURCE/MODIFIER_TARGET???
  ?? owner??????????????
- ???test_buff_templates ?? batch31????? 62 ?? 527 ???
  ???

## 2026-08-09 buff ????????????/????/????/????????

- SetSharedFlag?16 ???????????????? T2 ???????
  ??? T1 undeadable ??????
- CheckIfDamageHasSharedFlags?16 ????????????bbrain ??
  ???? INSTANT_KILL_LIKE_DAMAGE??
- AttributeModifierWithCertainBuffCount?16 ?????? buff ?????
  ???takila TR atk/??enemy_cbshld def ????? maxCnt ?
  writeToBB??
- CheckAbnormalFlags?64 ????????????????
- CreateBuffToCertainProfession?17 ???????????/token ? buff
  ?enemy_murad ???? SP ???smephi ??????
- AssignAttributeAsDynamicVarToBB?29 ???????x ?? scale???
  bb['value']?ncrmcr ???sgactr ????
- AssignAttributeRawDataIntoBlackboard?14 ?????????????
  ?duskld/duskls ???? max_hp??
- SetWithdrawCostRecoverRatio?15 ????????????bpipe/wildmn
  gaincost??
- ResetAbilityAtkScale?11 ????????????? atk_scale
  ?tinker Missile?acdums AOE??
- CheckTraitAbilityBlackboard?15 ??????????????coldst
  ?????
- FilterByAbilityFinishReason?12 ????????????hlsnip S1 SP
  ???spbell ??????
- DamageScaleBaseOnDistance?10 ?????-?????????glaze/
  cuttle ???bb max_scale??? _reverseDistance??
- ???test_buff_templates ?? batch32????? 62 ?? 528 ???
  ???

## 2026-08-09 buff ????????????/????/??/????????

- ?? battle ? _global_bb / _char_shared_bb ???AddGlobalBlackboard /
  AddCharacterSharedBlackboard ??????????? battle ???
- AddTileBlackboard?10 ??/ ModifyTileBlackboard?10 ??/
  FilterTileBlackboard?11 ???per-tile ?????????????
  lrtsia ?????fthlgj ????????
- AssignGlobalBlackboardToBlackboard?23 ??/ AssignCharacterSharedBBTo
  Blackboard?11 ?????/??????????cjdoor ?????
  aglna2 ??????
- CreateBuffToUnitInCurrentMapLayer?16 ???????????? buff
  ?pbank ??? buff????=??????
- CheckUnitInMoveState?8 ??/ CheckUnitInAttackState?12 ?????/
  ???????_isUnset ???spmode ????
- ModifyAttackMaxTarget?7 ?????????????dsdevr ????
  hsgma2 S3??
- ModifyEnemySkillMaxTarget?6 ??????? max_target?smdeer Lasso??
- FinishBuffsOfEveryCharacterById?20 ?????????/token ??
  ?? buff?murad ?????acelem ??????
- CheckEnemySkillAffecting?10 ????????????sgcat ????
- FinishSeveralBuffsById?10 ????????? buff?minima ????
  durcar ??????
- CreateBuffToHostAsSource?10 ?????? buff????????
- ???test_buff_templates ?? batch33????? 62 ?? 529 ???
  ???

## 2026-08-09 buff ??????????????/????/???????

- SwitchDynamicBuffTileMode?20 ??+ OneLine ???11 ????? buff
  ???????????????????dssalr ?????? owner ?
  ??????? battle.switch_tiles_mode?INDEX/FLIP_BOOL + tile ??
  ????
- ModifyAbilityAttackTime?7 ?????????????????
  ?pope S1 M1/M2 ?? s_duration??
- CalculateTraitAbilityBlackboard?30 ??????????
  ?targetKey = fromKey +/- addKey?coldst ???????? trait bb
  ?????
- FilterByTargetDataLevel?9 ????????????xbbarir/xbfdtion
  mesh ????
- AssignValueToTraitBB?10 ???trait ?????coldst RELOAD_FLAG??
- CheckEnemyCurrentCheckpoint?8 ??????????????
  ?xdmush ????
- CheckEnemyFaceAndMoveDir?8 ????????????????
  ?mhkryk ???? SAME/OPPOSITE??
- ModifyBlackboardFromTrait?9 ???trait ?????/??????
  ?leizi2 max_stack_cnt / atk ????
- ModifyBoomberangMaxCnt?8 ???????????caper S2??
- AddEnemyBlockVolume?16 ????????????dssalr??
- ???test_buff_templates ?? batch34????? 62 ?? 530 ???
  ???

## 2026-08-09 buff ??????????/????/????/??/??????

- CheckHeightTypeOfCharacterRootTile?23 ????????????
  ?None ?? LOWLAND?chnut/aegiret ????
- CompareModifierValueWithTargetType?23 ????????? HP??
  maxHp x ratio????blkngt ?????ristar ?????
- ChangeCharBlockMode?22 ??/ CheckBlockMode?21 ?????????
  ??/???aglna2 ???murad ????
- FilterId?21 ????? id ?????aegiret ???dsblock ????
- ChangeEnemyRouteMotionMode?18 ??????????????????
  ????init_route ?? route ?? motion ???????
  build_flow_field?dugago/cjstel ????
- FilterCharacterLastDeathReason?15 ????????????
- AlwaysExecuteNodeList?15 ???????????????aglna2 S2??
- CreateBuffs?14 ???buff ????mudrok T1 ???
- AssignPlayTimeToBB?13 ????????????xbpffr ??????
- WithdrawTokens?12 ????? owner ? token?kalts_t/necras??
- FetchHpToBlackboard?9 ??/ RecordCurrentHpRatio?9 ???HP/???
  ????dhdcr ???mandra ??????
- CheckDistance?7 ????-???????bb range_radius??
- FilterByTargetMassLevel?6 ??????????glady/poca ????
- KnockBackWithDirection?9 ????????????????displace??
- ???test_buff_templates ?? batch35????? 62 ?? 531 ???
  ???

## 2026-08-09 buff ????????key ??/????/????/????????

- FilterCharacterKey?5 ??/ CheckCharacterData?5 ????? key ??
  ?trap_148_amblls?ironmn ???
- ReplaceAbilityDamageType?5 ????????????ftshad ??????
- ModifyAttributeRawDataByEntity?16 ???? source ?????????
  ?ftshad ??????? _useRatio ?????
- HpRatioToAttributeMul?5 ???? HP ???????noirc2 T1?limit_
  bonus def??
- CheckCharSkillAvailable?6 ??????????trap_rift??
- AssignAbilityBlackboardFromOthers?5 ???????????xdagt
  summon ????
- CheckEntitySuicide?5 ????????slent2 S3 / bddg S1??
- InterruptCharacterAbility?5 ??????????ash S2 / bena ???
  ? skill_controller.interrupt_active??
- EnsureDmgOrHeal?5 ???????????acdrop atk_scale ????
- SetIgnoreMissFlag?5 ?????????????????/????
- RecordDamageModifier?19 ???????????empgrd ???mirbst??
- CharacterHasValidToken?5 ???????? token ??????/????
- FinishBuffsByIdByBuffSource?5 ???????? buff?bbrain ???
  ristar boss buff??
- FinishAllStatusResistableBuffs?5 ????????????? buff?
- HasTileAlongDirection?5 ??????????? tile?ristar ????
- RechargeTokenByKey?5 ???token ????????pycblk ????
- AssignProfessionCntToBlackboard?5 ??????????????
- CheckConatinsMapTags?5 ??????????act25side/main_12??
- CheckEnemyTalentContainsKey?5 ???????????rogue ????
- ?????????1/??2/??4/??8/??16/??32/??64/???
  128/??512?CreateBuffToCertainProfession ?
  AssignProfessionCntToBlackboard ??????? MEDIC ?? 16??
- ???test_buff_templates ?? batch36????? 62 ?? 532 ???
  ???

## 2026-08-09 buff ?????????/????/SP ??/?????????

- AmmoSkillCountModifier?22 ??????????hlegle ???
  hlnpcb ???_recoverEventCount ????
- FinishTokenBuffsById?14 ????? owner ?? token ? buff
  ?mylyss S3??
- CheckEnemyLevelMask?14 ????????????NORMAL/ELITE/BOSS/
  ELITE_AND_BOSS?demetr S3?vvana T2??
- ModifySpData?13 ????? SP cost ???trcerb ???marcil ????
- FinishOneBuffById?12 ??????? buff?ymgscm ??????
- AssignCharacterSkillBlackboardToBB?12 ??????????????
  ?thorn2 T1 ?????haruka ??????
- ApplyElementDamageBasedOnDamageValue?10 ?????????????
  ?aegiret S1 ??act38side ??bb ratio??
- AssignAmmoSkillRemainingCountToBB?10 ???????????
  ?hlegle/angel2 S1??
- AssignTokenCntToBB?10 ??????? token ??????necras??
- FinishBuffsOfEveryEnemyById?10 ??????????? buff
  ?blaze2 S2 on_tile??
- CheckHostContainsBuff?9 ????? buff ?????mylyss ????
- InterruptEnemyCombat?9 ??????????vtmstr ??????
- Knockback?9 ????????source ???displace??
- CheckTargetSkillDurationType?9 ????????????AMMO??
- CheckRouteMotionMode?8 ????????????ymdgct ????
- AssignHostAttributeToBB?8 ????????x scale?????
  ?phatm2 ??? atk?entlec def??
- CheckDirectionWithBB?8 ???????? bb ???????????
- CheckEnemyWhetherReachedSomeCheckPoint?7 ??????????
  ?mhrors ??????
- CheckCharacterOnTile?7 ??????????yrjump ????
- UpdateAttributeRawData?7 ??????????duskld ?? max_hp??
- ???test_buff_templates ?? batch37????? 62 ?? 533 ???
  ???

## 2026-08-09 buff ????????token ??/????/??/????????

- EnemyKillToken?5 ??????? token?redace ???wdsmgc??
- SetCharacterMaxEs?5 ????? ES ?????rogue/humus???????
- AssignMapPositionToBlackboard?6 ??????????? X/Y ?
  ?ymgpck ????????
- CheckEnemyIsTracingTarget?6 ????????????pycrol/mnctur??
- EnemyChangeRouteToEndTile?6 ????????????aglina M2?
  vtarsn ????
- CheckCharacterInBornState?6 ???BORN ?????
- CheckDynamicBuffTileModeInEnum?6 ???????????
  ?ltrock ???_exclude ????
- CheckFaceLOrR?5 ??????/????aglna2 S3?siege2 token??
- FixedValueElementHeal?6 ???????????agoat2/highmo T2?
  scaleUp ?????
- AssignHostBlackboardToBuffBlackboard?6 ????? buff ?????
  ?prosts Mon3tr atk?mcgraf hp_ratio??
- IfTargetFromDirection?5 ????????????bgball ??????
- CheckGamePlayedTime?7 ??????????sfsui/racing??
- VerifyTargetWithCertainSource?5 ??????????night_map??
- IsIgnoreForSp?5 ????? SP ?????csdcr/csdoll??
- EnemyDurcarChangeDirection?5 ???????????durcar??
- CheckSpecificEnemyCount?5 ????????????wdslm ????
- FilterIsDummy?5 ????????svash2 token ??????
- CheckUnitSideOfMap?5 ????????????dyshhj??
- NoSourceDamageNew?6 ???????????sgass/crfilm ????
- ???test_buff_templates ?? batch38????? 62 ?? 534 ???
  ???

## 2026-08-09 buff ????????token ??/??/??/??????

- SpawnTokenOnRangeTile?6 ????????????? token
  ?stmkgt/mpgrou ???? trap_055_tileblock??
- ModifyCharacterAttackTriggerRangeId?6 ???????????
  ?trap_ftshad ??/????
- CheckEnemySkillSelectorHasTargets?1 ????????????
  ?xbfiry ????
- AssignEnemySkillCoolDownToBB?1 ???????????
  ?ubbplwq Destroy??
- SetBossCountDown?1 ???boss ??????ubbplwq destroy_cd??
- CheckCharacterInIdleState?1 ??????????tmslot S2 ????
- ForceEnterSkillOverloadProgress?1 ????????????tmslot S2??
- InterruptEnemyAbility?2 ??????????xi S2 ??ltsmer?
  ????????
- CheckCharacterInMagicCircuit?2 ????????????????
  False ??????
- ModifyRuntimeRouteUseBranchRoute?2 ??????????????
  ????????cjstel ???rabbithole??
- ???test_buff_templates ?? batch39????? 62 ?? 535 ???
  ???

## 2026-08-09 ?? buff selector ?????? + atk_scale_dot ??????

- ?????? buff ??????? buff ??? BUFF_OWNER/BUFF_SOURCE
  ? ON_BUFF_START ??????InstantKill/AdvancedApplyDamage/
  NoSourceDamage/AOEDamage/DamageVia/ApplyElementDamage????? key
  ???????????????_behavior_self_keys????? 1048 ?
  ?????mode switch / run ??? enemy_xbdeer[start_run]?
  enemy_trtrsl_s?enemy_skodo_switch_mode????????
- ??????????? ON_BUFF_START?enemy_trtrsl_s ? ON_BUFF_
  FINISH InstantKill ???????????????bldkgt_t_devour
  ? ON_BUFF_START InstantKill ??????????
- atk_scale_dot ???????Fireball?shchmr?atk_scale_main=1.2 ?
  ?? + atk_scale_dot=0.15 DoT?AdvancedApplyDamage ??
  _atkScaleVar ? bb ? tick ???0.15 x atk ???????????
  ???
- ???test_buff_templates ?? batch40????? 62 ?? 536 ???
  ???

## 2026-08-09 ?? buff targetOptions ????????

- ?? _passes_target_options(u, opts)????? selector _targetOptions
  ????targetSide?ALLY=1/ENEMY=0??targetMotion?WALK/FLY/ALL??
  targetCategory?DEFAULT/TRAP_OR_ITEM/OBSTACLE?token ??????
  professionMask????????????????exclude/contain
  abnormalFlags?STUNNED/SILENCED/UNMOVABLE/FROZEN/LEVITATE/DOZE??
- ?? CreateBuffInCircleRange???????+???????
  CreateBuffInRange????/??????????/???? buff ???
  ????????????????
- ???test_buff_templates ?? batch41??? MEDIC ???????
  FLY ???????STUNNED ??????/????????? 62 ??
  537 ??????

## 2026-08-09 targetOptions ???? AOEDamage????

- AOEDamage ?? _passes_target_options???????? targetSide /
  professionMask / targetMotion / abnormal ??????????+????
- ?????targetSide ????????????????????
  targetSide=ENEMY ???????AOEHeal ?? _sourceSideType ??
  ?????????????/????????????????????
- ???test_buff_templates ?? batch42?MEDIC ?????????
  ??????????AOEDamage ??? _damageType=TRUE ??????
  ??????????? 62 ?? 538 ??????

## 2026-08-09 ???????? + buff ??????????

- ????????????apply_damage ????ON_BEFORE_APPLYING_
  MODIFIER??????ON_APPLYING_MODIFIER?pre-settle??
  ON_APPLIED_MODIFIER???????????ON_APPLYING_SKIPPED_MODIFIER
  ??? 0/?????ON_OUTPUT_MODIFIER????????????
  124/55/25/25/18/80 ?????????????????
- buff ???????buff ?????????AssignValueToBB/
  BlackboardAdd/???????? buff entry ? blackboard???????
  BuffData????????
  1) ???? _ ????????_buff_entry ?????_remaining_ticks
     trigger ?????? snapshot ???? + RemainingRatioToAttribute
     Modifier ?????gravel def_atten ??????
  2) ?? enemy_empgrd_damge_buffer ON_APPLIED_MODIFIER ?
     RecordDamageModifier ?????? bb value ????
- ???test_buff_templates ?? batch43????? 62 ?? 539 ???
  ???

## 2026-08-09 ??????????????

- ???????????????
  - ON_OWNER_BORN?44????????
  - ON_OWNER_REACH_EXIT?36?+ ON_OWNER_FINISH?240?????? /
    ?? / ??????? buffs.on_owner_finish?? ON_OWNER_KILLED
    ????
  - ON_OWNER_BEFORE_DEAD?12??????buffs.on_owner_before_dead??
  - ON_TARGET_KILLED?87?????? buff?apply_damage ????
    source ????
  - ON_SKILL_START / ON_SKILL_FINISH?115/94???? on_start/on_expire
    ??? _start_cast / casting.finished?
  - ON_AFTER_ATTACK?27????????????
  - ON_BEFORE_TARGET_APPLY_MODIFIER?25??????????
- ???????ray S3 ???? SP ???????????
  ray_s_3[sp] ????ON_TARGET_KILLED ? mark -> ON_BUFF_FINISH
  ModifySp???????? +10????? refund????????
  ?? owner buff ???? ON_BUFF_FINISH??????BuffAbility
  remove ?? finish??????? SP ???
- ???test_buff_templates ?? batch44?BORN SP / ??? buff /
  SKILL_START atk buff?????? 62 ?? 540 ??????

## 2026-08-09 ????? + CreateBuffToBlockee????

- ???????
  - ON_OWNER_BLOCKEE_CHANGED?62???????/????_update_blocking
    ????????
  - ON_ABILITY_SPELL_ON?36?????????_start_cast??
  - ON_EVADE_DAMAGE?15?????? miss ??apply_damage ???????
  - ON_OWNER_LOCATE?35????????? spawn ????????
- ?? CreateBuffToBlockee?35 ???? owner ?**????**
  ?blocked_enemies???? buff????? blocked_by ????bomscr
  ???dhnzzh ???dhshld ????
- ?????????? damageHitrate 0 ???100% ?????????
  `or 100.0` ??????? 0??? miss??????????????
  ?? 100 ?????? additive trait?0+50=50 ???????????
  ????ON_EVADE_DAMAGE ???? 50 ????
- ???test_buff_templates ?? batch45???? buff??????
  blockee ? dot?????? 62 ?? 541 ??????

## 2026-08-09 ???????????/??????/???????

- ON_ABNORMAL_FLAG_DIRTY?35??????/????buffs.set_abnormal /
  clear_abnormal ?????mheagl ??????? S3 ???mjcdog
  cooldown ???
- ON_ABILITY_START?15?/ ON_ABILITY_CAST_ON_TARGET?22?/
  ON_ABILITY_FINISH?19????????/????/????_start_cast ?
  casting.finished?? SKILL_START/FINISH ????
- ON_BEFORE_ATTACK?13????????????ai._start_normal_attack
  ????
- ???test_buff_templates ?? batch46????????? atk buff?
  ???? stop-weaken?????? 62 ?? 542 ??????

## 2026-08-09 ????????/???/??????

- ON_ABILITY_INTERRUPTED?5????????????operator_skills.
  interrupt_active?interrupt ???? on_expire??
- ON_AFTER_CALCULATE_DAMAGE?3??????????apply_damage
  calculate_damage ???blkswb DEF ?????bossrush buff??
- ON_OWNER_HP_FULL?2????????apply_heal healed>0 ?
  hp>=maxHp?titi S3 ?????
- ??enemy_syudg_t[stun] ? CreateBuff ? gate ??????IfElse
  SP>0 ?????????????? SP>0 ?????
- ???test_buff_templates ?? batch47????? 62 ?? 543 ???
  ???

## 2026-08-09 ????????????????

- snapshot ?? globalBlackboard?_global_bb??sharedBlackboard
  ?_char_shared_bb??tileBlackboard?_tile_bb?? "row,col" ????
  ? buff ??????????????/??????????????
  LiveServer /snapshot ? /stream ?????
- ?? prefab ???????EnemySkillRun ?????????
  ?_preDelay/_waitForAttackEvent/_atkScale/_damageType/_epDamageRatio/
  _projectileKey/_elementDamageType ???_forceAsDmgOrHealAbility=true
  ???????????has_damage ??????????????/??
  ?????????
- ???test_buff_templates ?? batch48??????? + JSON ??????
  ???? 62 ?? 544 ??????

## 2026-08-09 SwitchMode ?? + ????????

- ?? SwitchMode?1100+ ?????????????????????
  ?? mode_index?_modeIndex / _loadModeFromBlackboard / _restoreDefault??
  ??? ON_UNIT_SWITCH_MODE?16??
- ON_DIRECTION_CHANGED?11??SwitchDirection ????????
- IfElse gate ??????dump.cs ActionNode.Execute ?? bool ? gate?
  IfElse ? IActionNodeSource ????????? gate ????????
  enemy_syudg_t[stun] ? SP ?????????????????
- ???test_buff_templates ?? batch49?SwitchMode ? bb ? mode ???
  SwitchDirection ???????? 62 ?? 545 ??????

## 2026-08-10 ?????????? + ???????????

- ?????1651 ??? x ?????5711 ????? + update??
  ???? Simulator ?? spawn/??/????????????
- ?? enemy_10101_crgun biu ???blackboard ??? [{}]?? dict??
  EnemySkillRun.__init__ ? b["key"] ? KeyError ???????????
  ?? blackboard ???skill + catalog_entry?? b.get("key") is not None
  ???
- ??????? 0 ?????????? AttributeError ?????
  API?????????
- ???test_enemy_buffs ?? crgun ????? spawn+?????
  ???? 62 ?? 546 ??????

## 2026-08-10 ?????? + ES/????/??????????

- ?? tests/test_enemy_skill_smoke.py??????????1651 ?? x
  ???????? + update????? Simulator????????????
- ?? tests/test_level_smoke.py???/??/???????????
  ??? + 60s ?????? buff_event_error??
- ????????? rdoc_t2[listener]/humus_t_1/enemy_white_s
  [resonance]/trap_magiccircle_t/chiave_t_1[deck]??
  - ES????????????ON_ES_OVER_ZERO ?? DamageViaEs ????
    ?????? barrier ???????????
  - ??????????????ON_ENTER/LEAVE_MAGICCIRCUIT??????
  - ????????? buff/???CreateCardBuff/DeckBuff??????
- ???? 62 ?? 550 ??????

## 2026-08-10 ???????? + ??????????

- ???? range-gated targeting?????????????????
  ???????????????????? scripted agent ??
  ?GreedyDefender/BeamAgent/examples Bot??? legacy fallback ???
  6 ??????????????targeting.py ?????? agent/bot
  ??????_best_direction??????????
- test_battle_integration ????? direction=3????????????
  ??????????fallback ???????
- ???????? docs/TEST_SCOPING.md??????????????
  ????????????????????62 ??? 37 ????
- ???? 40 ????agent/??/??/??/????


## 2026-08-10 buff 节点补齐 batch50 + 定向测试流程落地

- 新增 11 个 buff 节点实现（累计约 348 种）：
  AtkToHpRecovery / ModifyCostIncreaseTime / ModifyMaxCost /
  CheckManhattanDistance / IsElementHeal / IsUnharmfulEnemy /
  CheckHasUnitInRange / SetEnemyCanNotExit / AssignIDToBlackboard /
  CheckEnemyAbilityName / RecordAbilityRemainingTime
- 新增 tests/test_buff_templates.py::test_buff_batch50_misc_nodes 覆盖上述节点。
- 定向测试验证：batch50 单测 1 项 + test_buff_templates.py 全文件 67 项通过（约 4 分钟）。
- 本轮改动影响面：仅 buff 模板引擎 + 对应单测，未触碰战斗集成/关卡/敌方冒烟，
  按 docs/TEST_SCOPING.md 只跑 buff 领域，未触发全量 62 文件回归。

## 2026-08-10 buff 节点 batch51 + 派生 buff 生命周期 + 范围格位重写

- 新增 5 个 buff 节点实现（累计约 353 种）：
  - CreateNoSourceBuff：无来源创建 buff（env_act46side[no_skill] 等场地机制）
  - CreateBuffUseHostAsSource：以宿主为来源创建 _buffData（loadFromDB 合并同 CreateBuff）
  - AttachAsDerivedBuff：派生 buff，derived_from=父 buff，父移除/过期时级联移除
  - RewriteTileOptionsInRange：范围格位 buildable 重写（dysuib 禁部署 + 夜图 advanced mask 状态）
  - TriggerSpecifiedAbility / TriggerAbilityMergeBB：命名能力触发（owner/target 解析 + 事件）
- buffs.py：remove() 支持派生级联（derived_from 父->子单向）；map.py：TileData 新增
  _buildable_override/_advanced_buildable_override 运行时覆盖 + GameMap.rewrite/restore_tile_buildable。
- 定向测试验证：batch51 单测 1 项 + test_buff_templates.py 68 项 + 相邻领域
  （test_buff_triggers/test_level_loading/test_tile_effects_e2e/test_level_runes）26 项全部通过。
- 命名能力（blacksteel_energy / SpawnToken / blaze2 状态切换等）当前为可观测事件：
  具体行为由 battle/operator Python 驱动实现（blaze2 reborn 已有专门实现），
  未在 buff 模板路径重复执行以避免双重触发。

## 2026-08-10 HpNoLessThanCertainPercentModifier + 煌 T1 紧急除颤端到端

- 新增 buff 节点 HpNoLessThanCertainPercentModifier（累计约 366 种）：
  ON_TAKE_DAMAGE 时把伤害夹到 owner HP 不低于 max_hp*ratio（bb 优先读
  huang_t_1[lock].min_hp_ratio，回退 min_hp_ratio/hp_no_less_than_percent/
  hp_percent/ratio，默认 0.5）。
- 煌 T1「紧急除颤」完整驱动（talents.py）：HP 首次低于 25%（hp_ratio）时仅一次
  触发——huang_t_1[heal] buff 经 HealViaMaxHpRatio 回复 50% 最大生命 +
  huang_t_1[lock] buff（duration 3/4/6/7s 按精英/潜能，锁 HP>=50%）。
  参数来自 characters.json 天赋 blackboard（hp_ratio 0.25 /
  huang_t_1[heal].hp_ratio 0.5 / huang_t_1[lock].min_hp_ratio 0.5）。
- 定向测试：batch52 单测 2 项 + buff 全文件 68 项 + 天赋/技能领域
  （test_element_talents / test_t2_reborn_talents / test_operator_skills）合计 104 项通过。
- 已知近似：触发判定在 tick 内逐帧检查（比游戏 ON_TAKE_DAMAGE 即时触发晚 1 tick，
  约 33ms）；触发那一击不会被锁夹住（锁在触发后才生效），与游戏一致。

## 2026-08-10 buff 节点 batch53：弹道发射 + 攻击可用性门控

- 新增 4 个 buff 节点实现（累计约 370 种）：
  - CheckCanUseAtkOrCbt：攻击/战斗可用性门控（stun/frozen/levitate/palsy
    控制位 0/16/25/39 + EnemyState 状态检查）
  - TriggerAbilityUseSelectorMergeBB：并入共享命名能力触发器（mergeBB 语义）
  - EmitProjectileUseAbilitySelector：按 selector 目标发射弹道，命中时执行
    _actions 子链（AdvancedApplyDamage 等）+ _buffDataList；支持
    _excludeTarget/_emitCount；无 key 时回退 op_<charId> 或敌方技能弹道
  - EmitProjectileOnSourceRootTile：源根格位弹道（ON_HIT_OBJECT/ON_HIT_TILE，
    观测事件 + 空动作链不结算伤害）
- 已知近似：selector 类能力名（MissileSelector/s2range/SplashSelector）未建模
  真实选择逻辑，目标用 _targetType 解析近似；无 key 的敌方弹道回退到其技能
  弹道，找不到则发 skipped 事件。
- 定向测试：batch53 单测 1 项 + test_buff_templates.py 72 项 + test_projectiles.py
  5 项，合计 77 项通过。

## 2026-08-10 buff 节点 batch54：计数门控 + 追踪/闪现/波次释放

- 新增 8 个 buff 节点实现（累计约 378 种）：
  - CheckBuildCnt：部署干员数对比（LE/GE/LT/GT/EQ/NE，首/二次部署天赋）
  - ModifyBlackboardStr：黑板字符串赋值/复制
  - CreateTileEffect：场地特效观测事件
  - DisableEnemySwitchFaceByMove：敌方移动转向禁用标记 + 事件
  - CheckRootTileAdvBuildableMask：根格位 advanced buildable mask 门控
    （NIGHT=1 覆盖标记/DEFAULT，基础值透传）
  - EnemyForceTracePosition：强制追踪目标/位置（移动钩子 + 到达半径 +
    目标死亡停止 + 给追踪目标上 buff）
  - ReleaseEnemyFromCurrentWave：波次释放标记 + 事件（时间轴模型为标记态）
  - BlinkNode：闪到下一检查点/地图坐标/黑板行列（+ toEndIfNoCheckpoint）
- entities.py：Enemy 新增 _trace_target/_trace_pos/_trace_reach 等追踪字段，
  update_movement 在 FEARED/ATTRACTED 之后插入追踪分支（默认未设置时行为不变）。
- 定向测试：batch54 单测 1 项 + test_buff_templates.py 73 项 + 敌方/Boss 领域
  （test_enemy_buffs/test_boss_behavior/test_boss_batch）合计 112 项通过。
- 已知近似：BlinkNode 的 _useNewRouteBeforeBlink 换路/分支切换未建模；
  ReleaseEnemyFromCurrentWave 在时间轴波次模型下为标记 + 事件。

## 2026-08-10 buff 节点 batch55：token 获取 + 移速下限 + 偷取属性黑板

- 新增 4 个 buff 节点实现（累计约 382 种）：
  - GainToken：玩家侧 token 库存（act36side/多索雷斯），bb token_key
    （支持 _spiltTokenKey 逗号拆分），battle._gained_tokens + token_gained
    事件 + snapshot gainedTokens
  - ModifyAttributeDataRangeOverride：属性区间覆盖（当前支持 MOVE_SPEED
    下限 clamp，move_speed_range_override 复活敌人移速保底；_doClear 清除）
  - AssignStealAttributeAbilityTotalValueToBB：偷取属性累加器写入黑板
    （steal_<attr> 当前值 / max_steal_value 上限，上限默认取单位对应属性）
  - IgnoreAllButMoveCp：忽略 WAIT/PATROL/DISAPPEAR 检查点直接沿流场行走
- battle.py：新增 _gained_tokens/_gained_token_timings/_steal_values/
  _steal_max 状态 + snapshot gainedTokens/stealValues；entities.py Enemy
  新增 _move_speed_min/_ignore_all_but_move_cp 及移动钩子。
- 定向测试：batch55 单测 1 项 + test_buff_templates.py 74 项 +
  test_live_server_chain.py 5 项 + test_enemy_buffs.py 12 项，合计 91 项通过。
- 已知近似：偷取属性为占位累加器（默认 0），完整 StealAtk/StealHp/StealDef
  能力执行器未实现；GainToken 只登记库存，未接入自定义编队部署 UI。

## 2026-08-10 buff 节点 batch56：敌方召唤三节点

- 新增 3 个 buff 节点实现（累计约 385 种）：
  - SummonEnemiesWithRuntimeNearestEndPointRoute：在源单位格位按运行时最近终点
    路线召唤 _summonCount 个敌人（dhnzzh reborn / trap_trbox_s / legion 陷阱 /
    dysbox 等 16 处）；支持 FLY 模式 / unharmful / _buffs 附魔
  - HalfIdleSummonEnemyAtTargetMapPos：在目标格位召唤 _enemyId（半挂机事件
    陷阱 16 处），支持 _hasBuffToEnemySource 给召唤物上 buff
  - SummonEnemiesOnTargetTile：目标格位召唤（enemy_ltniak deathmark /
    xbthdr / enemy_dycant 等），支持随机偏移（battle.rng）/ _excludeRootTile
- 敌方 key 统一解析：节点 _enemyKey/_enemyId 优先，回退黑板
  enemy_key/enemyKey/enemy_id/enemyId（序列化节点 key 多为 null，运行时注入）。
- 与 prefab 动作路径（action_nodes.py）不重复：本批是 buff 模板引擎路径。
- 定向测试：batch56 单测 1 项 + test_buff_templates.py 75 项 +
  test_enemy_skill_smoke.py 全部通过。

## 2026-08-10 buff 节点 batch57：卡牌/卡组系统最小真实模型

- 新增 11 个卡牌系节点实现（累计约 396 种）：
  CreateCardBuff / CheckContainsCardBuff / FinishCardBuff /
  FinishCardBuffsByKey / CreateDeckBuff / CheckContainsDeckBuff /
  FinishDeckBuffByKey / FinishDeckBuffByCardUIDAndKey /
  AssignCardUIDToBlackBoard / CreateCardBuffToMyToken /
  HideCardByTokenOrHostUid / CreateCardBuffFilterByDeckBuff
- 数据模型：Unit.cards = [{uid, key, lifeType, hidden, inHand, layers,
  isDeck, cardEffectType}]（entities.py 初始化 + base_to_dict 快照外显）；
  card uid 由模块级计数器分配；CreateCardBuff 默认把当前 buff 自身转成卡
  （nearl2_s_2[withdraw] 等），_useCardBuffKey 显式指定；card_uid 写入
  bb 供后续 Finish/Assign 使用；deck 建模为 isDeck 卡片条目。
- 覆盖耀骑士/伊内丝 S3/魔刃狗/小丘郡等 ~230 个模板中的核心卡牌流程；
  FilterByTag/FilterByProfession（肉鸽招募券抽卡）留待后续。
- 兼容：无 key 的 CreateCardBuff 保留旧 card_buff 观测事件（batch12 回归）。
- 定向测试：batch57 单测 1 项 + test_buff_templates.py 76 项 +
  test_more_subprofessions.py + test_live_server_chain.py，合计 95 项通过。

## 2026-08-10 buff 节点 batch58：卡牌变体 + 演出 + 迷雾 + 集结点

- 新增 13 个 buff 节点实现（累计约 409 种）：
  卡牌变体：CreateCardBuffFilterByTag / CreateCardFilterByProfession /
  ExcludeDeckCardFromBattle / AssignCardRemainingCntToBlackboard /
  FinishTokenCardBuffByKey / CheckCharacterIsFreelySpawnedFromDeck
  演出：CreateLineEffect / SetSpineSkin / PlayUnitAnimation
  迷雾：MarkFogView（range/global 标记格位 in/out of view，快照 fogView）
  集结点：SwitchRallyPointCategory / RallyPointReborn / OnRallyPointLikeReborn
- 状态：battle._rally_category/_rally_points/_fog_view/_excluded_deck_cards
  + 快照 rallyCategory/rallyPoints/fogView/excludedDeckCards；entities
  Unit._spine_skin/_freely_spawned_from_deck + spineSkin 快照外显。
- 已知近似：tag 过滤因单位未存 tags 而放行（不可验证）；集结点需外部注册
  _rally_points（蔓德拉/苇草等重生算子尚无注册节点）；fog 目前只做状态+
  事件，targeting 未消费迷雾；RallyPointReborn 传送+满血。
- 定向测试：batch58 单测 1 项 + test_buff_templates.py 77 项 +
  test_live_server_chain.py + test_more_subprofessions.py +
  test_enemy_buffs.py，合计 112 项通过。

## 2026-08-10 buff 节点 batch59：控制/计分/重生/掉落 + 集结点自动注册

- 新增 21 个 buff 节点实现（累计约 430 种）：
  控制：TriggerHostsBuffsByKeys（按 key 触发宿主 buff 的 ON_BUFF_TRIGGER，
  支撑 vigil 重生链）/ KillCharacterOnTileIfExists / InterruptCharacterAttack /
  SetCharacterDontOccupyDeployCntFlag / ForceCharacterFaceDefaultDirection
  重生：RespawnCharacter（bb 坐标/原位，满血 + respawnCnt）/ IsRallyPoint /
  AssignRespawnCntToBlackboard
  门控：FilterByBlackboardStrIsValue / FilterModifierCancelReason /
  CheckBuildableTypeOfCharacterRootTile / CheckContainsEnvSystem
  计分：UpdateScoreManually / GameCityUpdateScore（battle._scores + 快照）
  结束：FinishGame（WIN/LOSE）
  掉落：HalfIdleDropResource / HalfIdleDropBattleItem（_dropped_loot + 事件）
  演出：HideEntityGraphicOrNot / ShakeCamera / EnableShadowController /
  ModifyCharacterSpineColor（状态 + 事件）
- 集结点闭环：battle._register/_unregister_rally_point——玩家 token/trap
  生成时自动注册为 TRAP_OR_ITEM 集结点，死亡/撤退移除；RallyPointReborn
  现在在真实流程可用（蔓德拉/苇草等重生链数据完整时）。
- entities：_respawn_cnt/_dont_occupy_deploy_cnt/_force_face_default/
  _graphic_hidden/_spine_color/_shadow_enabled + 快照外显；
  battle：_scores/_dropped_loot + 快照 scores/droppedLoot。
- 定向测试：batch59 单测 1 项 + test_buff_templates.py 78 项 +
  test_live_server_chain + test_enemy_buffs + test_operator_skills，
  合计 123 项通过。

## 2026-08-10 buff 节点 batch60：卡牌扩散/拖拽/技能CD/格位阵营

- 新增 14 个 buff 节点实现（累计约 444 种）：
  CreateCardBuffToAllCard / CreateDeckBuffByCnt / DragTowardSource /
  SetStackCountViaBlockNum / ReInitEnemySkillCoolDown /
  EnemySkipWaitCheckPoint / DamageViaEs / CheckCharacterSkillType /
  HideEntityInFogAndManageBuff / EmitProjectileToTileUseSelector /
  ApplyCacheAtkDamageFromBuff / HalfIdleUpgradeTrap /
  Act27sideModifyTileCachedSideType / SummonEnemiesFollowBranchRouteWithTileBlackboard
- entities：Enemy._skip_wait_checkpoint（WAIT 检查点直接跳过，默认关闭行为不变）；
  battle：_tile_side_cache + 快照 tileSideCache。
- 已知近似：DragTowardSource 为简化 1 格拉拽；DamageViaEs 的 ES 系统仍为
  占位（伤害读 bb damage/atk*scale）；HalfIdleUpgradeTrap 通过 retire+spawn
  替换陷阱 token。
- 定向测试：batch60 单测 1 项 + test_buff_templates.py 79 项 +
  test_enemy_buffs + test_displacement + test_force_weight，合计 115 项通过。

## 2026-08-10 buff 节点 batch61：演出/日志/动画 + 少量真实小节点

- 新增 23 个 buff 节点实现（累计约 467 种）：
  演出/动画（记录为可观测事件 + 状态）：ChangeAnimatorMeshRenderer /
  ChangeAnimatorMeshRendererViaIndexList / ModifyAnimatorHookerReplacePair /
  AddHeightOffsetToSpine（spineHeightOffset 快照）/ ForceCharacterAnimatorFaceFront /
  DisableEnemyHud（hudDisabled 快照）/ ActiveCameraEffect / PlayBGM /
  ShowGameCityUiPluginText / SandboxShowToast / CollectTargetInfoFunLiveModeOnly /
  Act29SideCheckCurrentAudioType / Act49sideBossUpdateWarningEffect
  日志：LogExtraBattleInfoForBossRush / LogExtraBattleInfoWithNoTarget
  （battle._extra_log 累计 + 快照 extraLog）/ LogExtraBattleInfoForModifierRealDelta
  门控：IsTargetInDialog（记录并失败）/ CheckFirstRallyPointMode
    （_rally_switch_count == 1）/ Act29SideCheckCurrentAudioType（放行）
  真实：AssignResCountToBB（读掉落资源计数）/ CharSearchBlockeeImmediate /
  SwitchDynamicBuffTileModeInRange（_tile_modes + 递减 bb 计数）/
  RewriteDynamicBuffTileOptionsOneLine（_tile_bb 行写入）/
  HalfIdleTriggerTrapUpgradeCheck
- battle：_rally_switch_count/_extra_log + 快照 extraLog；entities：
  _animator_face_front/_hud_disabled/_spine_height_offset + 快照。
- 定向测试：batch61 单测 1 项 + test_buff_templates.py 80 项 +
  test_live_server_chain + test_level_runes + test_tile_effects_e2e，
  合计 103 项通过。

## 2026-08-10 敌方 prefab 动作执行器回退委托 buff 引擎

- action_nodes.py：未本地处理的 prefab 动作节点回退调用 BuffTemplateEngine
  的 _n_<Type> 处理器（source/target/技能黑板适配为 buff ctx），异常安全。
  敌方技能 prefab 动作图（AdvancedApplyDamage/NoSourceDamage/CreateBuff/
  EmitProjectile/...）从此获得完整语义而不是 no-op；本地已处理的
  IfElse/Summon*/Blink/Transport 等保持优先，无重复执行。
- 覆盖：prefab 目录 76 种动作节点中 55 种缺口中大部分自动补齐。
- 定向测试：新增 test_prefab_action_delegation_to_buff_engine（委托
  AdvancedApplyDamage 造成 200 PURE 伤害）+ 敌方技能全量冒烟
  （1651 敌人 x 5711 次施放不崩）+ test_buff_templates 81 项 +
  enemy_buffs/boss_behavior/boss_batch，合计 121 项通过。

## 2026-08-10 buff 节点 batch62：足球/军团/肉鸽状态簇 + 未处理通知

- 新增 33 个 buff 节点实现（累计约 500 种）：
  足球/狂热：IsInFever / IsFeverFull / AddFeverBySourceIfNotFull /
  TryActiveFeverIfFull / IsCloseToFootball / StopBall（battle._fever/
  _football_pos/_football_stopped）
  军团：LegionModeOnlyGainGold / GainTrap / DrawNextCard / SelectCard /
  CheckCardInHand / MarkCardReturnToHand / AddProfessionLevel /
  AssignDangerLevelToBB（_legion_gold/_legion_hand/_legion_traps/...）
  肉鸽：CompareRogueDiceNumber / RoguelikeLogExp（_rogue_exp/_rogue_dice）
  真实小节点：SkipStage / AOEElementDamage（EP 灼燃）/ HasCertainCharacterInFrontOfMe /
  FilterTargetWithPlayerSide / AssignEnemyLastMoveDirectionToBB /
  CheckDistanceToTileCenter / CheckEnemyIsStayStill / ExtendAbilityCooldown /
  SetCastSkillCost / AssignEntityEsIntoBlackboard（ES 占位 0）/
  CheckCharacterIsMannuallySpawned / Act46SideAddAreaSP /
  SwitchToRebornState / RandomAction（battle.rng 分支）/ 
  CreateBuffToCharacterInSpecifiedArea / ClearCharacterOnTileIfExists /
  KnockBackWithCharacterDirection / AddExcludeCharacterToDynamicBuffTile /
  FinishSpecifiedTileHoldingEffect
- catch-all：run_actions 对未实现节点每类型去重发一次 buff_node_unhandled
  事件（不刷屏），剩余 ~850 种活动/演出节点全部在事件流可见。
- battle：_fever/_football/_legion_*/_rogue_exp/_dynamic_tile_excludes/
  _tile_holding_effects + 快照 fever/football/legion/rogueExp/...；
  entities：_last_move_direction/_manually_spawned。
- 定向测试：batch62 单测 1 项 + test_buff_templates.py 82 项 +
  test_live_server_chain + test_enemy_skill_smoke + test_enemy_buffs，
  合计 100 项通过。

## 2026-08-10 迷雾 targeting 接入（MarkFogView 闭环）

- battle.is_fogged(unit)：单位所在格位被 MarkFogView 标记为 out-of-view
  （_fog_view[(r,c)] == False）即视为迷雾隐藏；无标记格位恒可见。
- targeting.operator_target：干员普通攻击/技能选择目标前过滤迷雾中的敌人
  （正常关卡无迷雾标记，行为不变）。
- 定向测试：新增 test_fog_hides_enemies_from_operator_targeting（迷雾中
  不可选中，揭示后可选中）+ test_buff_templates.py 83 项 +
  test_battle_integration + test_agents + test_operator_skills，
  合计 127 项通过。

## 2026-08-10 range-gated targeting 启用（干员范围外待机）

- targeting.operator_target：删除 legacy 全列表 fallback——范围内无目标时
  干员待机（真实游戏行为）。
- 配套完成 TEST_SCOPING 前置条件：
  1) GreedyDefender._plan：vanguard 按 route_cells 靠近出生点落位（不再
     硬编码 mid_r 列），blocker 靠近出口/咽喉点；ranged 沿用 _best_direction。
  2) test_agent_env 击杀关卡部署改到路线单元格 (2,5)；test_custom_levels
     Bot 编队扩到 8 人（+plosis/snakek/beagle/kroos）可稳定胜利 1-1。
- 定向回归：test_agents/test_agent_env/test_custom_levels/
  test_battle_integration/test_buff_templates 合计 114 项通过。
- docs/TEST_SCOPING.md 已知限制已更新（移除 range-gated 待启用说明）。

## 2026-08-10 行医索敌修正：元素值最低优先（PRTS 实测）

- 核对结论（PRTS 四处独立来源一致）：行医普通攻击索敌顺序为
  「生命比例最低 > 当前损伤元素的元素值最低 > 更早部署」；标注
  「优先治疗元素损伤最严重的目标」的技能实际实现为
  「元素值最低 > 生命比例最低」——游戏把“最严重”实现成“元素值最低”
  （PRTS 备注明确记载的反直觉行为）。来源：蜜莓/桑葚/纯烬艾雅法拉
  分支信息、纯艾 S3 火山回响备注（含更早部署 tie-break）、PRTS 差异页
  （"该目标元素值最低的种类"的元素值最低）。
- 修复（targeting.py）：
  1) 行医 EP 度量从“最严重（最高条）”改为 `_wm_ep_metric`＝目标当前
     受损元素条（非零）中的最低值，无 EP 为 0；普通攻击排序
     `(hp_ratio, ep_metric, deploy_tick)`。
  2) 技能期翻转：`_WM_EP_PRIORITY_SKILLS`（蜜莓 S1/S2、桑葚 S1/S2、
     哈洛德 S2）激活时排序 `(ep_metric, hp_ratio, deploy_tick)`。
  3) 新增排除：生命已满且元素值已满的单位不作治疗目标（`_wm_ep_full`）。
  4) 新增更早部署 tie-break（`deploy_tick` 升序）。
- 测试：test_wandermedic_trait.py 重写 1 项（等比例改为同角色避免
  浮点 1e-16 差异）+ 新增 3 项（技能翻转/更早部署/满血满元素排除），
  12 项全过；领域回归 test_operator_skills + test_buff_templates +
  test_traits + test_more_subprofessions + test_arts_subclasses 154 项通过。
- 已知限制（已在下轮闭环）：ep_max 对 level>0 单位为 2000
  （模拟器既有模型，未在本次核对范围内）。

## 2026-08-10 行医/医疗多目标治疗（蜜莓 S1/S2）

- 需求：蜜莓 S1 精神护理“下次治疗以元素损伤最严重的 2 名干员为目标”、
  S2 振奋 attack@max_target=2（高等级 3）的每次治疗应命中 2~3 名干员；
  此前每次治疗只结算 1 个目标。
- 实现：
  1) targeting.py 抽出 `_heal_candidates`（过滤+排序的有序候选），
     新增 `HateSystem.operator_targets(op, count)` 取前 N（按行医
     hp/元素/部署顺序；其他医疗按 hp 比例）。
  2) operator_skills.py 新增 `ActiveSkillEffect.heal_max_target()`：
     blackboard `attack@max_target`>1 优先，否则查 curated
     `_HEAL_MULTI_TARGET`（蜜莓 S1=2，目标数只存在于描述/prefab）。
  3) battle._operator_attack：医疗干员激活多目标技能时，在 windup 时
     快照前 N 个治疗目标；_resolve_operator_attack 治疗分支遍历全部
     快照目标，每个都结算 HP 治疗 + 行医全元素恢复，ATTACK 事件带
     targets 列表。非医疗的 attack@max_target 敌人多目标逻辑原样保留。
- 语义核对：S1 的 2 个目标按“元素值最低优先”选取（PRTS 怪癖：
  “最严重”实际实现为“元素值最低”），元素值最高的干员反而不在列。
- 测试：test_wandermedic_trait.py 新增 3 项（operator_targets 前 N
  顺序 / S2 双目标 HP+EP / S1 双目标按元素最低选取），15 项全过；
  领域回归 test_operator_skills + test_buff_templates +
  test_arts_subclasses + test_more_subprofessions + test_attack_timing +
  test_attack_all_blocked 140 项通过。
- 更正上轮误记：桑葚 S2 安全区域为单目标“优先治疗元素损伤最严重的
  目标”（非多目标），已由元素优先翻转覆盖；多目标技能只有蜜莓 S1/S2。

## 2026-08-10 元素爆发阈值 maxEp 修正（默认 1000）

- 核对：dump.cs AttributesData 含 `maxEp`（ObscuredInt，0x284，
  UnitData.get_maxEp）；游戏内干员/敌人元素损伤条默认上限 1000，
  部分 Boss 可覆盖。干员表 maxEp 字段对已抽样干员均为 None（默认 1000）。
- 原实现 bug：`ep_max(unit)` 按 `level>0 时 1000+1000` 启发式，导致
  level>0 的干员/敌人上限变成 2000——与游戏不符（元素爆发/满元素
  判定全部受影响）。
- 修复：
  1) attributes.py FIELDS 增加 `maxEp`（数据侧可流入）。
  2) buffs.ep_max：优先读 `attributes.maxEp`（>0 即用），否则默认
     1000.0，删除 level 启发式。
- 测试：test_ep_break_templates.py 新增 2 项（level-50 干员 999 不爆/
   1000 爆发；maxEp=2000 覆盖生效），7 项全过；元素/伤害/异常领域
   （test_element_talents/ritualist_talents/t2_reborn/phatm2_s3/
   thumpy_talents/wandermedic/damage_type/abnormal/damage_matrix）
   69 项通过。
- 新发现的已知限制：当前敌方表二进制 `enemy_database3cc1f2.bin` 已换
  格式（无 name 长度头，疑似与 character_table 同款 128B 头），旧提取器
  （硬编码 enemy_databasea5b667.bin + name 头解析）无法解析；现有
  enemy_database.json 未导出 maxEp（ENEMY_ATTR_NAMES 无该字段），
  敌方 maxEp 覆盖无法核实——列为后续工作（重写敌方表解析器并补
  maxEp 字段导出）。

## 2026-08-10 数据新鲜度核对 + 新表格式逆向结论

- 数据新鲜度核对（决定性证据）：从游戏目录当前 anon 解包中提取
  character_table / enemy_database / skill_table 的 TextAsset，其
  头部 count@140 分别为 **1323 / 2079 / 1795**，与 characters.json /
  enemy_database.json / skills.json 的键数**逐一精确相等**；且当前表内
  全部 char/enemy/skill id 均 ⊆ 现有 JSON。结论：三份 JSON 就是当前
  内容构建的（提取器硬编码 hash 与当前资产名一致），模拟器数据无
  “缺新”风险；JSON 中的多出条目仅是客户端已移除的旧事件敌人/角色。
- 已从游戏目录复制最新 4 个表 CAB 到 data/tables（character_table
  9fc534 / enemy_database a5b667 / skill_table afb859 /
  enemy_handbook_table 493349），覆盖旧解包产物；运行时图鉴解析
  验证正常（1693 条）。
- 新表 TextAsset 格式逆向结论（供后续解析器落地）：
  - data/tables/*.bin 是 Unity CAB，需 UnityPy 抽 TextAsset 得到
    `.bytes`（资产名即旧提取器硬编码的 hash）。
  - TextAsset 布局：[0-127 混淆头][u32 4 @128][u32 0x3f3f3f3f @132]
    [u32 4 @136][u32 count @140][count × u32 数据偏移 @144+]
    [字符串区（~8K-146K，含键/名/黑板键）][条目数据区（文件尾）]。
  - count@140 与现有 JSON 键数精确一致（敌方 2079/干员 1323/技能 1795）。
  - 旧提取器（name_len@0 解析）与当前 TextAsset 格式不兼容，需要
    更新 FB 头/索引解析 + 补 ENEMY_ATTR_NAMES 的 maxEp。
- 剩余缺口（后续工作）：新格式完整解析器 + maxEp 按敌导出；届时
  可核实是否存在 maxEp≠1000 的敌方单位。

## 2026-08-10 纯艾 S3 火山回响：5连发治疗 + 全图范围

- 需求（PRTS）：S3 "攻击范围扩大至整个战场，治疗变为
  {attack@heal_scale} 治疗量和元素损伤回复量的 5 连发，优先治疗不同的
  目标"。S1 无声润物 "每次可额外治疗一名单位"。
- 实现：
  1) operator_skills.py：`_HEAL_SHOT_COUNT`（skchr_agoat2_3=5，连发数
     只存在于描述）、`_HEAL_MULTI_TARGET` 增补 skchr_agoat2_1=2；
     `ActiveSkillEffect.heal_shot_count()/heal_attack_scale()`
     （attack@heal_scale=0.25 每发）。
  2) on_start 对 skchr_agoat2_3 把 range_shape 扩为全图（保存
     _base_range_shape，on_expire/interrupt 恢复）。
  3) battle._operator_attack：快照 max(多目标数, 连发数) 个候选；
     _resolve_operator_attack 治疗分支 shots>1 时按
     `ordered[i % len(ordered)]` 循环（动作内先选未选过的，候选不足
     时按优先序回到列表头），每发 apply_heal(amount=atk×heal_scale,
     ep_scale=heal_scale)（元素回复量与治疗量同步缩放）。
  4) apply_heal 新增 ep_scale 参数（默认 1.0，向后兼容）。
- 测试：test_wandermedic_trait.py 新增 3 项（5连发循环 HP+EP 精确
  2/2/1 分配、全图范围激活与结束恢复、S1 额外目标），18 项全过；
  领域回归 test_operator_skills + test_buff_templates +
  test_arts_subclasses + test_more_subprofessions + test_attack_timing +
  test_attack_all_blocked + test_phatm2_s3 144 项通过。
- 已知未接：S3 "丢失全部视野" 与第二天赋 2 倍（火山灰疗愈
  maxHp/元素减伤 aura 未实现）——后者需在 talent aura 系统补
  "range" 作用域 + talent_scale 倍率，留待后续。

## 2026-08-10 纯艾 T2 火山灰疗愈 aura + S3 翻倍/视野

- 需求（PRTS）：T2 "攻击范围内的友方单位生命上限+6%，且受到的
  元素损伤降低12%"；S3 火山回响期间效果 2 倍（talent_scale=2.0），
  且"自身丢失全部视野"。
- 实现：
  1) talents.aura_specs：char_1016_agoat2 T2 输出两条 range 作用域
     spec（maxHp mul 0.06 / epDamageResistance add 12.0，黑板上
     ep_damage_resistance 0.12 转百分数）；S3 激活时 ×2。
  2) battle._aura_targets：新增 "range" 作用域（owner 攻击范围格位，
     包含自身格位）；aura buff key 加入数值（talent_aura:inst:stat:val），
     数值变化（0.06↔0.12）时旧 key 由同步循环清理——解决 apply()
     同 key 刷新不更新数值的问题。
  3) operator_skills：S3 激活时置 op._vision_lost（快照 visionLost），
     结束/中断恢复；治疗索敌不受影响（行医不需要敌方视野）。
- 测试：test_wandermedic_trait.py 新增 1 项（基准 +6%/+12 →
  S3 +12%/+24 → 结束后恢复，含 visionLost），19 项全过；天赋/技能
  领域回归 test_operator_skills + test_arts_subclasses +
  test_more_subprofessions + test_pallas_talents + test_ritualist_talents
  + test_t2_reborn_talents + test_buff_templates + test_phatm2_s3
  149 项通过。

## 2026-08-10 纯艾 T1 氤氲 HoT + dynamic 变量修复

- 需求（PRTS）：T1 "普通治疗使目标每秒额外受到一次治疗量和元素损伤
  回复量为 8/10% 的增益治疗，持续 4/6 秒（最多叠加 3 层）"；使用缓存
  攻击力，叠加时重置持续时间并更新缓存攻击力。
- 接线真实模板 agoat2_t_1（data_buff_templates.json 内置 ON_BUFF_TRIGGER
  AdvancedApplyHeal + FixedValueElementHeal）：
  1) buff_templates._n_AssignAttributeAsDynamicVarToBB：改为写入
     bb["dynamic"]（同时保留 bb["value"]）——此前只写 "value"，而全部
     28 个使用模板（nowell/turdus 治疗、大量护盾 BlockDamage、
     papyrs/yu_t_2 等）都读 "dynamic"，属潜在 bug。
  2) _n_AdvancedApplyHeal：支持 `_useDynamicVar`（读 bb["dynamic"] 缓存
     攻击力）与 `_scaleUpByBlackboardKey`（乘 stack_cnt）。
  3) 修双重元素回复：模板驱动的治疗（AdvancedApplyHeal）不再触发行医
     天赋 atk×50% EP 钩子（apply_heal 新增 trait_ep=False）；HoT 的
     元素回复由模板自带 FixedValueElementHeal（dynamic×stack_cnt×
     ep_heal_ratio×heal_scale）负责，否则每跳重复回复全额 EP。
  4) battle._apply_agoat2_t1：普通治疗命中时应用/刷新缓冲（缓存 ATK、
     heal_scale 0.10（E2）、ep_heal_ratio 0.5、1s 触发、6s 时长、层数
     上限 3；刷新重置时长并更新缓存 ATK）。
- 测试：test_wandermedic_trait.py 新增 2 项（HoT 6 跳+过期、3 层叠加+
   封顶），21 项全过；领域回归 test_buff_templates + test_operator_skills
   + test_arts_subclasses + test_more_subprofessions + test_phatm2_s3 +
   test_t2_reborn_talents + test_enemy_buffs + test_ritualist_talents
   161 项通过。

## 2026-08-10 实证收尾：主线关卡不触发未实现 buff 节点

- 静态计数：1341 种节点类型，502 已处理 / 850 未处理；高频未实现几乎全是
  沙盒/活动系（RunActionsToWdslmAbilityTarget 29、SandboxMarkEntityNotReward
  23、Act49Side* 16/12、Sandbox* 系列 9~12、DurBus 9）。
- 两轮独立实证（5 关 + 6 关主线，每关 60s，事件流确认刷怪/攻击在跑）：
  `buff_node_unhandled` 计数全部为 0 → 剩余未实现节点集中在活动/沙盒/肉鸽，
  静态追高频的收益低，该调查方向暂停；后续按活动复刻/用户实测继续补。

## 2026-08-10 行医技能/天赋补全（哈洛德 T1/S2、桑葚 S2、纯艾 S1）

- 需求（PRTS）：
  - 哈洛德 S2 重症优先："治疗元素损伤累计超过一半的目标时，元素损伤回复量
    提升至 120%~250%（trait_scale）"；HP 治疗不变。
  - 哈洛德 T1 我即军营："攻击范围内元素损伤累计超过一半的目标受到的元素
    损伤降低 12/15/18%（E1/E2/潜能）"。
  - 桑葚 S2 安全区域："攻击范围内所有友方单位受到的元素损伤降低
    15%~35%（ep_damage_resistance）"。
  - 纯艾 S1 无声润物："攻击范围内所有友方单位每秒回复攻击力 2%~8% 的
    元素损伤，持续时间无限"。
- 实现：
  1) targeting.py：新增 `_unit_ep_max`（显示条 = 各类型最大值；PRTS CH-6/7
     "多种元素损伤只显示最严重的一种"）与 `_unit_ep_over_half`（> maxEp/2）。
  2) battle.apply_heal：行医 EP 回复乘 `active.wandermedic_ep_scale(target)`
     （仅 skchr_harold_2 且目标过半时返回 trait_scale）。
  3) talents.aura_specs：哈洛德 T1 注册 range 作用域 epDamageResistance
     aura + cond "ep_over_half"；battle._aura_target_ok 新增该 cond。
  4) operator_skills.on_start：桑葚 S2 注册 `op._skill_aura_specs`
     （epDamageResistance 值 ×100 转百分数）；battle._update_talent_auras
     合并技能 aura（key 前缀 skill_aura:，随技能结束/撤退由同步循环清除）。
  5) operator_skills.tick：纯艾 S1 激活对齐每 1s（30 tick）对攻击范围
     （含自身格位）内所有友方+召唤物 recover_ep = 当前 ATK ×
     agoat2_s_1[aura].ep_heal_ratio；跳过 prefab owner 版
     agoat2_s_1[aura]（ep_heal_when_trigger）——模拟器把它只挂到施法者且
     按 maxEp×ratio（20/s）结算，与描述（ATK×2%）不符，统一由范围 aura 实现。
- 测试：test_wandermedic_trait.py 新增 4 项（T1 阈值减伤含进出范围、S2
  trait_scale 只对过半目标、S2 减伤 aura 生效/结束清除、S1 每秒回复含
  范围外/自身/HP 不变），25 项全过；领域回归（operator_skills/buff_templates/
  buff_triggers/arts_subclasses/more_subprofessions/element_talents/
  ritualist_talents/t2_reborn_talents/pallas_talents/phatm2_s3/thumpy_talents/
  enemy_buffs/ep_break_templates/damage_type/abnormal/attack_timing/
  attack_all_blocked）203 项通过。
- 已知遗留：ApplyElementHeal（ep_heal_when_trigger 共享模板）的
  `_maxEpHeal` 语义未核实（当前仅纯艾 S1 使用且已被范围 aura 取代）；
  哈洛德 WDM-X 模组（特性 ep_heal_ratio 0.6、天赋 20/23%）未接。

## 2026-08-10 哈洛德 WDM-X 腿部护理套装（模组特性/天赋强化）

- 需求（PRTS）：WDM-X 模组 lv1+ 特性更新为"回复攻击力 60% 的元素损伤"
  （ep_heal_ratio 0.5→0.6），lv2 天赋「我即军营」20%（潜能 23%）、
  lv3 23%（潜能 26%）；属性 生命+70/80/90、攻击+20/27/32。
- 实现：
  1) loader.module_trait_upgrades：解析 battle_equip
     overrideTraitDataBundle（phase.parts[].6.0[].3 黑板 DataPair），
     与 module_talent_upgrades 同相位选择。
  2) TraitSystem.apply_module_upgrades：按基础特性黑板键序覆盖
     （哈洛德：ep_heal_ratio=0.6）；多候选时潜能≥5 取末位。
  3) battle.deploy：挂模组时对 trait_system 同样应用模块特性升级。
  4) 顺带修复 test_modules.py 结构性 bug：test_module_trait_elite_ep_scale
     的断言此前被误塞进 sim_run_ticks 辅助函数（pytest 下为空壳不执行），
     已归位为真实测试。
- 测试：test_modules.py 新增 2 项（loader 特性值、端到端 lv1 特性 0.6 +
  lv3 天赋 23%/潜能 26% + 属性加成），10 项全过；领域回归（modules/
  wandermedic/operator_skills/buff_templates/arts_subclasses/
  more_subprofessions/element_talents/ritualist_talents/t2_reborn_talents/
  pallas_talents/enemy_buffs/ep_break_templates/damage_type/abnormal）
  219 项通过。

## 2026-08-10 敌方领袖元素爆条阈值 2000（maxEp 规则修正）

- 规则（PRTS 元素页 https://prts.wiki/w/元素 + CH-7）：默认 MAX_EP=1000；
  领袖级敌人实际最大元素值最终 +1000（=2000）；普通/精英敌人 1000；干员 1000。
- EnemyDatabase.AttributesData（dump.cs:168913，31 字段）无 maxEp 字段，
  enemy_database.json 亦无；EnemyLevelType（dump.cs:169386）
  0=NORMAL / 1=ELITE / 2=BOSS。
- 实现：buffs.ep_max 按 unit.side==0 且 level_type==2 → 2000，其余 1000；
  attributes.maxEp>0 仍优先。此前删除的「level>0→2000」错误启发式不恢复
  （level 是等级，level_type 才是敌人阶级）。
- 测试：test_ep_break_templates.py 新增 3 项（普通/精英 1000 边界、领袖 2000
  边界、领袖 maxEp 属性覆盖），10/10 全过；定向回归 10 文件 82 项全过。


## 2026-08-10 元素爆条效果敌我分流 + 全局锁定 + 按类型冷却（PRTS 元素页）

- 需求（PRTS 元素页 https://prts.wiki/w/元素）：元素值从满值扣减、爆发冷却
  期间所有元素值锁定（不可损失/不可回复）、结束时全部恢复满值；爆发效果按
  阵营分流，2026-04-07 后敌人类单位无论阵营统一用敌方效果。
- 实现（buffs.py / battle.py）：
  1) _burst_effect 重写为 PRTS 精确分流：神经-敌方 3 层麻痹(每层5s=15s，受
     麻痹免疫检查)/我方 10s 眩晕+1000 真伤；侵蚀-敌方 -120 防永久可叠(8s
     爆发期)/我方 -100 防永久可叠+800 物伤；灼燃-双方法抗-20(10s)+敌方
     7000/我方 1200 法伤；凋亡-敌方 15s 50% 虚弱(随剩余时间线性衰减)+每秒
     800 元素伤/我方 15s 阻回+静默+每秒-1 SP+100 法伤。敌方爆发的元素伤害
     施加在已锁定的自身条上，实际无效果（游戏同款）。
  2) 爆发冷却按元素类型：神经 10s/侵蚀我方 10s·敌方 8s/灼燃 10s/凋亡 15s
     （原统一 30s 修正）；冷却期间 _ep_lock_active 全局锁（update_ep 与
     recover_ep 均拒绝）；冷却结束 _ep_burst_end 恢复全部元素条满值并发出
     ep_burst_end 事件。
  3) battle.apply_damage 新增 _weaken_scale：虚弱源造成的所有伤害×
     (1+weaken.mul)，mul 每 tick 按剩余时间比例衰减到 0。
- 测试：test_ep_burst_effects.py 新增 9 项（敌我分流四元素、8s/10s/15s 冷却、
  全局锁定、结束恢复、虚弱衰减、凋亡 DoT）；test_abnormal.py 神经爆条断言
  改为 PRTS 语义（麻痹+无 HP 伤）。领域回归 11 文件 91 项全过。
## 2026-08-10 索敌刷新间隔 SEARCH_TARGET_TICK=3（dump.cs 逆向）

- 证据：SelectorTrigger.SEARCH_TARGET_TICK = 3（dump.cs:437169，攻击/技能
  目标选择器每 3 逻辑 tick 重搜一次，30Hz 下 0.1s；_overrideSearchTargetTick
  可覆盖；Search(force) 绕过）；TileTrigger.SEARCH_TARGET_TICK = 5
  （dump.cs:437439）；CompoundPeriodicTicker 双 ticker 计数。
- 实现（targeting.py / ai.py / battle.py）：
  1) targeting.search_gate：通用搜索门，缓存 _ai_target/_search_tick，周期内
     保留仍有效的旧目标，force 立即重搜。
  2) HateSystem.operator_attack_target：干员/医疗普攻索敌走搜索门，缓存目标
     仍可选（存活/在射程/被阻挡/可治疗）时沿用；_still_selectable 做廉价校验。
  3) 敌方普攻 _start_normal_attack 走 search_gate；缓存目标失效（死亡/部署
     动画）时 force 重搜。
- 测试：test_search_tick.py 5 项（门单元测试、医疗 3-tick 保持/切换、敌方
  最近目标保持/切换、force 重搜、爆发控制不干扰缓存）。领域回归 13 文件
  141 项全过。


## 2026-08-10 属性偷取引擎（StealAttributeAbility，dump.cs:543106）

- 逆向：StealAttributeAbility 字段/方法（_stealOnceBBKey/_stealMaxBBKey/
  _stealMaxScaleBBKey、_keepTargetAttributeAtLeastOneAfterSteal、
  _refreshStealValuesBeforeCast、m_stealTargetBuffKey/m_stealSelfBuffKey、
  TriggerByTarget/CastToTarget/CastDirectly/OnDetached）；攻击/技能目标
  选择走通用 SelectorTrigger，偷取 buff 随能力卸载回收。
- 实现（battle.py / operator_skills.py）：
  1) battle.steal_attribute：单次偷取 = min(单次值, 目标剩余值-下限(默认1),
     源总预算-已偷总量)；双端累计 add buff（steal[{key}][target]/[source]），
     总量写入 _steal_values/_steal_max 并进快照（stealValues）；发 steal 事件。
  2) _clear_steal_buffs：撤退/死亡/技能结束回收该源造成的全部偷取 buff 并
     重建属性修正（StealAttributeAbility.OnDetached 语义）。
  3) _apply_attack_steal：命中时按技能黑键执行偷取——伊内丝 S2 每次攻击
     偷 4 攻速(上限40)、薇薇安娜 S2 偷 20 攻速(上限20)、寻澜 S2 洞悉每次
     攻击偷 10 防(上限100)。
  4) 新约能天使 S2 开火成瘾症：施放时偷取攻击范围内 1 名友方干员 70 攻速
     （持续至技能结束或离场），on_expire/_clear_steal_buffs 回收。
- 测试：test_steal.py 6 项（伊内丝/寻澜/薇薇安娜/新约能天使/撤退回收/引擎
  下限与预算边界）。领域回归 13 文件 211 项全过（test_advanced_features 旧爆条断言已改为 PRTS 语义）。


## 2026-08-10 敌方 maxEp 实证收口 + GainToken 部署链路

- 敌方 maxEp 实证（关闭旧审计缺口）：
  - EnemyDatabase.AttributesData 31 字段无 maxEp（dump.cs:168913 与
    extract_enemy_data.py ENEMY_ATTR_NAMES 一致）；enemy_database.json
    全部敌方条目均无 maxEp。
  - 敌方天赋黑板（talentBlackboard）与技能/敌方 prefab 目录（skill_prefab_
    catalog / data_enemy_prefab_catalog_current）全量扫描 maxEp/max_ep
    = 0 命中 → 不存在按敌覆盖的 maxEp。
  - 结论：领袖敌人爆条 2000 是纯 levelType 规则（levelType 分布：普通
    None/0=1209、精英 1=824、领袖 2=305），模拟器 bufs.ep_max 的
    side==0 且 level_type==2 → 2000 已完备。
- GainToken 部署链路（battle.py / api.py / live_server.py）：
  - battle.deploy_gained_token：消耗库存计数部署 GainToken 获得的玩家方
    token（快照 gainedTokens 暴露），无库存返回 not_gained；成功发
    token_deployed 事件。
  - Simulator.deploy_gained_token 代理 + LiveServer /action 新增
    deploy_gained 动作，Web UI 可部署库存 token。
- 测试：test_gain_token.py 3 项（节点登记库存、部署消耗、LiveServer
  动作端到端）。领域回归 4 文件 111 项全过。

## 2026-08-10 缪尔赛思流形 token 偷取（缺口关闭）

- 此前判定"流形 token 偷 10 攻防无数值键"是基于 token 技能黑键
  （sktok_mlyss_wtrman_*）；实际数值在 token 天赋黑板
  （token_10030_mlyss_wtrman talents）：steal_atk 10 / steal_atk_max
  250 / steal_def 10 / steal_def_max 250。
- 实现（battle.py）：
  1) _token_steal_bb：提取 token 天赋候选里带 steal 键的最高相位黑板，
     三个 Token 创建点（deploy_token / spawn 路径 / 预置物）均挂载
     token.token_steal_bb。
  2) _apply_attack_steal 并入 token 来源（steal_atk/steal_def，各上限
     250）；_resolve_operator_attack 对无主动技能的 token 攻击同样触发
     偷取（流形经 GainToken 库存部署）。
- 测试：test_steal.py 新增 1 项（token 每击 -10 攻/防，自身 +10），
  7/7 全过。

## 2026-08-10 敌方模式状态机（进化的本质 初生/进化/完美，闭环审计缺口）

- 逆向（dump.cs + prefab）：enemy_1519_bgball 的 11 个技能是"形态机"——
  SwitchToMode2/3 携带 C{n}_Die -> C{m}_Idle 动画键（形态 n 死亡、形态 m
  登场）；M1/M2/M3 AttackWarning->Effect->RealAttack 是各形态的"蓄力击"
  链（warning 是 CompositeAbility，_abilities 引用后续阶段）。PRTS：
  初生/进化/完美形态周期性对全场我方造成 900/1000/1200 真伤，完美形态
  攻击频率大幅加快。
- 旧行为：控制器把 11 个技能当独立 CD 技能，SwitchToMode3（cd 0）无限
  重复施放，形态机完全不转、蓄力击链不触发。
- 实现（skills.py / entities.py）：
  1) EnemySkillRun 解析 mode_from/mode_to（C{n}_Die/C{m}_Idle）、
     mode_skill（M{n} 前缀）、mode_chain_stage/mode_chain_only。
  2) EnemySkillController.mode_index（0 起）：形态技能按当前形态门控；
     SwitchToMode 需离开形态的 M{n}RealAttack 至少释放过一次（PRTS：
     各形态先蓄力击再进化）；M{n}Effect/RealAttack 仅作为链式延续施放，
     不独立选取。
  3) 施放完成时切形态并发 enemy_mode_switch 事件；快照暴露 modeIndex。
  4) 链式施放：warning 结束立即接 effect -> real（CompositeAbility
     always-next 语义）。
- 实测时序：初生形态 35.5s/70.5s 两次蓄力击链 -> SwitchToMode2 进化 ->
  进化形态蓄力击链 -> SwitchToMode3 完美 -> M3 链每 5s 快速连击（对应
  baseAttackTime 5.0 + 完美形态加速描述）。测试：test_boss_behavior.py
  新增 1 项（形态解析、链序、进化顺序、完美快速连击、快照 modeIndex），
  9/9 全过。
- 已知近似：各形态蓄力击伤害按 prefab 黑板（M1/M2/M3RealAttack damage
  600/700/800）经 _activeBuffs 模板结算，PRTS 描述 900/1000/1200 为
  现网标称值；切换触发用"上一形态蓄力击已释放 + 技能 CD"，PRTS 表明
  实际按 HP 阈值进化，精确阈值待 prefab trigger 组件解析后校准。

## 2026-08-10 进化的本质 蓄力击全场结算（追加）

- 缺口：M{n}RealAttack 的 _activeBuffs（instant_damage_pure 模板，
  FixedValueDamage 打 buff 目标）只施加到单个施放目标，PRTS 明确蓄力击
  对全场我方单位造成真伤。
- 实现（skills.py AbilityRun._execute_effects）：mode_real_attack 技能
  的效果目标列表扩展为全部存活干员（模板从技能黑板 damage=600/700/800
  取伤害，逐个施加 bgball_m{n}[fix_damage]）。
- 实测：初生形态蓄力击同一 tick 对两名干员各造成 600 真伤（damage 事件
  type=TRUE amount=600 各一条）；M2/M3 同理按 700/800 结算。
- 测试：test_boss_behavior.py 新增 1 项（全场真伤断言），10/10 全过。

## 2026-08-10 远程攻击附带元素损伤延迟到弹道命中（PRTS 时序）

- 需求（PRTS 元素页）：攻击直接附带的元素损伤"紧接在当次攻击的伤害后
  处理"。近战本就正确（伤害后立即 apply_on_attack）；远程此前在弹道
  发射时结算 EP，早于伤害。
- 影响技能（全部为远程干员）：skchr_kaitou_1（折光 S1）/ warmy_1/2
  （温米）/ christ_1（Miss.Christine）/ threye_2（凛视）/ bobb_2
  （波卜）/ botany_2（伯塔尼）/ nymph_1（妮芙）的 attack@ep_damage_ratio
  与 attack@ep_damage_scale。
- 实现（battle.py）：spawn_projectile 新增 hit_extra（默认伤害/命中事件/
  trait 结算后执行）；_resolve_operator_attack 的远程分支把 apply_on_attack
  与偷取挂到弹道命中回调，发射时不执行（效果循环对 ranged 跳过）。
  例外：switch-attack 连击（_replace，如能天使 S3 过载/陈 S3 绝影）不走
  弹道、连击段在结算时立即打出（模拟器既有模型），不延迟。
- 测试：test_element_talents.py 新增 1 项（发射时 EP=0，弹道命中后
  EP=atk×0.1），3/3 全过；test_operator_skills.py 能天使 S3 连击用例
  在修正后恢复即时结算语义。领域回归 15 文件 221 项全过。

## 2026-08-10 本源术师元素语义修正（折光/妮芙爆发期直伤 + 按技能解析损伤类型）

1. **攻击附带元素损伤按技能元素类型解析【已实现】**
   - 根因：operator_skills.py 所有 `battle.add_ep(..., 0, ...)` 硬编码
     神经损伤；而 7 名 attack@ep_damage_ratio 干员元素类型各异
     （神经：Miss.Christine S1/塑心 S2/酒神 S3；灼燃：温米 S1/波卜 S2；
     侵蚀：伯塔尼 S2；凋亡：折光 S1/凛视 S2/妮芙 S1）。
   - 修复：`OperatorSkillRun._resolve_ep_type()` 按技能描述中的元素损伤
     名称（神经/侵蚀/灼燃/凋亡 → 0/1/2/3）解析，缺失时回退 prefab
     `_elementDamageType`（translate_game_element_type），默认 0；
     `_fire_burst`（含弹道回调）、区间 tick、on_start 与 apply_on_attack
     全部改为该类型。
   - 证据：skills.json 描述含 `<$ba.dt.apoptosis2/burning2/erosion2/
     neural2>` 标签；7 干员 blackboard 无 `_elementDamageType`（prefab
     仅 FSM buff），描述为权威来源。

2. **爆发期额外元素伤害 = ELEMENT 直伤，不是加 EP【已实现】**
   - 根因（PRTS + 游戏模板实锤）：`attack@extra_ep_damage_scale` 对应
     游戏 buff 模板 `kaitou_s_1[ep_damage]`/`kaitou_s_2[ep_damage]`/
     `nymph_s_1[ep_damage]`：ON_BUFF_START →
     `FilterEPBreakRecoveryType(DARK)` → `AdvancedApplyDamage(ELEMENT,
     atkScale=extra_ep_damage_scale)`。爆发期间全部 EP 条锁定，加 EP
     无效果，因此该加成是 HP 直伤（元素伤害类型，无视防御/法抗/屏障）。
   - 修复：`Battle.apply_damage` 新增 `element_as_hp=True`（ELEMENT 分支
     直接扣 HP、绕屏障、共享原有 modifier/统计/死亡尾链；默认 False 保持
     旧 EP 语义）；`apply_on_attack` 在目标处于对应元素爆发期
     （`ep_burst_cd_{type}`）时按 `atk × extra_ep_damage_scale` 结算。
   - 数值：折光 S1 0.2~0.5 / S2 0.4~0.75 / 妮芙 S1 0.2~0.5（M1 起）。
- 测试：test_element_talents.py 新增 4 项（折光 S1 弹道 EP=ep_dark
     atk×0.1、S1 爆发期直伤 atk×0.2、S2 爆发期直伤 atk×0.4、温米 S1
     ep_fire atk×0.15），6/6 全过；领域回归 20 文件 212 项全过。
## 2026-08-10 敌方天赋黑板接入 + 进化的本质 HP/时间驱动形态机（缺口关闭）

1. **敌方 talentBlackboard 加载【已实现】**
   - 根因：EnemyData.talentBlackboard（模式参数/召唤分支/重生分支等）此前
     完全没有读入 Enemy，仅凭技能名近似形态机；多个 Boss 的天赋参数丢在
     这个字段里（进化的本质、蔓德拉 Reborn.branch_id、白垩、蒸汽骑士、
     变形者集群、伤心的大锁 summon 等）。
   - 修复：spawn_enemy 把 `data.talentBlackboard` 写入
     `enemy.talent_blackboard`（值/值串双格式），Enemy 实体新增字段；
     `EnemySkillController._parse_mode_params` 解析 `mode_{n}.*` 与
     `mode_{n}_summon.*`（含游戏数据拼写变体 `mode_1_summoni.interval`）。
2. **进化的本质形态切换改为 HP/时间驱动【已实现】**
   - PRTS：初生形态持续 100s 后或生命 <60% → 进化；进化形态 100s 或生命
     <20% → 完美。旧实现"上一形态蓄力击已释放 + CD"会在 32s 左右过早
     进化，与 PRTS 不符。
   - 实现（skills.py）：`_mode_condition_check` 每 tick 校验当前形态
     hp_ratio/evolve_time，命中即强制施放对应 SwitchToMode 技能（忽略
     蓄力击门控；保留技能自身 CD/沉默判定）；带 mode_params 的敌人其
     切换技能不再被通用技能挑选器选中。`on_cast_finish` 切换形态时按
     `invincible_after_skill_duration`（10s）施加无敌并重置模式计时。
3. **每形态被动【已实现】**
   - 减伤：`_enemy_mode_damage_scale`（battle.py）——初生对左侧
     （direction 3）来源物法 -80%，进化对右侧（direction 1）-80%，完美
     对全部非自身来源物法 -99%；真伤/元素损伤不受影响。
   - 完美自伤：mode_3.damage 300 真伤每秒（interval 1s，浮点累加加
     epsilon 防早/晚 1 tick）。
   - 召唤节律：mode_{1,2,3}_summon.interval 5s/3s/2s 触发
     `try_enemy_branch_summon`（battle.py，始终发 enemy_summon 事件；
     关卡提供 enemyBranches 映射时按分支生成，OD-8 关卡数据缺失时事件
     保留节律可见性）。
- 测试：test_boss_behavior.py 新增 4 项（talentBlackboard 参数解析、
     HP 阈值进化+入场无敌、左右侧减伤/完美全局减伤/真伤穿透、
     完美自伤 300/s），14/14 全过；领域回归（敌方属性/技能/Boss 批次/
     伤害公式/虚弱）67+1 项全过。
## 2026-08-10 官方 gamedata 关卡补全（覆盖率 2140 -> 3146 个可玩关卡）

1. **数据源**：游戏客户端只携带 ~2854 个 level TextAsset（其余关卡按需
   下载，本地缺失）；通过稀疏克隆 Kengxxiao/ArknightsGameData
   （`zh_CN/gamedata/levels`，blob:none + sparse-checkout，仅拉 levels
   目录 ~567MB）拿到官方全量关卡 JSON（3868 个，含客户端没有的活动/多
   模式/肉鸽关卡）。
2. **转换器**：新增 [convert_official_levels.py](G:/Arknights/ark_parser/
   enemy/convert_official_levels.py)，把官方 JSON 归一化为模拟器解析格式：
   - mapData.map 嵌套数组 → {rows, cols, cells}
   - 地块枚举（dump.cs TileData/SharedConsts 实测）：heightType
     LOWLAND/HIGHLAND→0/1、buildableType NONE/MELEE/RANGED/ALL→
     null/1/2/3、passableMask NONE/WALK_ONLY/FLY_ONLY/ALL→0/1/2/3、
     playerSideMask ALL→null、advancedBuildableMask 位掩码
   - waves actionType/randomType/refreshType、route motionMode、
     checkpoint type 字符串 → {"value":N,"name":S}
   - enemyDbRefs.overwrittenData {m_defined,m_value} → 值/null
   - runes difficultyMask/buildableMask 字符串 → 枚举；predefines 保留
     完整（二进制解析器只存计数）
   - 兼容官方 JSON 的 null 路由项（保留位置、不可出生）与 None 片段
3. **接入**：新增 1010 个关卡 JSON 到 data/levels、level_data_index.json
   追加条目、重跑 build_sim_bundle.py 重建 stage_sim_bundle.json。
   运行时加固：merged_routes 容忍 null 路由、build_route_field 接受
   int/dict motionMode、spawn_enemy 跳过 null 路由、_runes_for 接受
   str/int/dict difficultyMask。
4. **验证**：随机 60 个新关卡全量可加载模拟（含 act44side/act49side/
   rogue2/sandbox2/act2break 等）；既有 26 项关卡/runes/自定义关卡测试
   全过；LiveServer 快照链路 2 项全过。stages-parsed 2140→3146
   （90.7%）。
## 2026-08-10 官方关卡预定义单位（predefines）JSON 回退（缺口关闭）

1. **根因**：官方 gamedata 关卡（上一轮新增的 1010 个）没有二进制资产，
   `parse_level_predefines` 只读二进制，预部署干员/陷阱全部丢失；而官方
   JSON 里 predefines 是完整结构（二进制解析器只存计数）。
2. **实现**（predefines.py + battle.py）：
   - 新增 `predefines_from_raw(raw)`：把官方 JSON 的 predefine 条目归一为
     二进制解析器输出形状（position→row/col、direction 字符串/整数、
     inst.phase 字符串/整数、characterKey/level/potentialRank/
     skillIndex/mainSkillLvl）。
   - battle 初始化：二进制资产解析为空时回退到 `raw.predefines`，随后
     统一走既有 `_spawn_predefines`（隐藏条目进 pending、波次
     ACTIVATE_PREDEFINED 激活、token 陷阱/NPC 盟友同管线）。
3. **验证**：
   - 62 个官方关卡带 characterInsts、数百个带 tokenInsts；
   - act10mini_09 预部署 格拉尼/芬莉浦 按位置朝向出生；
   - act10d5_02/04 传感器/吹风机陷阱出生；
   - act17d0_03 隐藏的 灰烬 由波次激活在战斗中出现；
   - test_level_loading.py 新增 3 项，5/5 全过；level runes/自定义关卡/
     地块效果 27 项全过。
## 2026-08-11 攻击附带异常状态接线（寒冷/沉睡/浮空/恐惧/束缚）

1. **根因**：技能扫描发现 apply_on_attack 只消费 prob/times/atk_scale/
   atk/hp_ratio/stun/sluggish/silence/unmove/heal/ep/force，而数据里
   存在一批完全未接线的攻击附带异常 attack@ 键：cold（极光 S2/耶拉 S2/
   寒檀 S2）、sleep（缇缇 S1/S3）、levitate（霍尔海雅 S2/S3）、fear
   （荒芜拉普兰德 S2）、frozen_duration（奥斯塔 S2 束缚、麦哲伦 S1 周期
   束缚）。
2. **实现**（operator_skills.py apply_on_attack）：
   - attack@cold → COLD(23)；attack@sleep → DOZE(43)；
     attack@levitate → LEVITATE(25)；attack@fear → FEARED(33)；
     attack@frozen_duration → UNMOVABLE(13) 束缚（带 attack@interval 的
     周期技能不走命中路径，避免麦哲伦 S1 误挂）。
   - 修正 buffs._buff_abnormal_immune 的 _NAME_MAP 值（FEARED/ATTRACTED/
     TELEPORTED/GROUND_BOUND/COLD 与 consts.AbnormalFlag 对齐），使 buff
     携带的 abnormalImmunes 名称匹配真正生效。
3. **验证**：test_attack_abnormals.py 新增 4 项（极光 S2 寒冷 2.5s、
   缇缇 S1 概率沉睡 1.5s、霍尔海雅 S2 概率浮空 1s、奥斯塔 S2 束缚
   0.8s），4/4 全过；领域回归 9 文件 174 项全过。
## 2026-08-11 buff_prob 概率门控修复 + DamageScale 缩放键系统级修复

1. **attack@buff_prob 从未被消费【已修复】**
   - 根因：4 个干员的概率晕眩写在 attack@buff_prob（雷蛇 S2 10% /
     帕拉斯 S2 50% / 推进之王 S3 40% / 赫德雷 S3 25%），apply_on_attack
     只认 attack@prob，导致晕眩 100% 触发。
   - 修复：攻击附带异常（stun 及上一轮新增的 cold/sleep/levitate/fear/
     root）统一按 buff_prob 独立掷骰（无 buff_prob 则每次命中必中）。
2. **DamageScale 缩放键默认值错误（295 处游戏模板受影响）【已修复】**
   - 根因：buff_templates._n_DamageScale 默认从黑键 "scale" 读倍率；
     游戏节点（dump.cs:567695，无 _scaleKey 字段）默认读 "damage_scale"
     （_customKey 可覆盖）。缺键时旧代码乘 0 → 带 damage_scale[mag]/
     [phy]/[input]/[out] 等模板的脆弱/减伤 buff 会把伤害清零。
   - 实测：电弧 S3 命中后 enemy 挂 weak[magic][limit]（模板
     damage_scale[mag]，黑键 damage_scale 1.1），法术伤害被正确 ×1.1
     （1000 法伤经 mres20 → 880）；修复前为 0。
   - 修复：_customKey → _scaleKey → "damage_scale" 解析，缺失时保持
     伤害不变（不误伤）；并移除 apply_on_attack 里重复的脆弱接线
     （模板路径已覆盖，避免双重加成）。
3. **验证**：test_attack_abnormals.py 新增 2 项（推王 S3 概率晕眩非
   100%、电弧 S3 法术脆弱 ×1.1 生效），6/6 全过；领域回归（buff 模板/
   触发器/敌方 buff/伤害公式/易伤/爆条/干员技能/异常）10 文件 178 项
   全过。
## 2026-08-11 攻击附带属性减益接线（移速/攻速）

1. **根因**：技能扫描发现 attack@move_speed（8 技能）与
   attack@attack_speed（4 技能）完全未消费；其中安哲拉 S2（-20% 移速
   3s）、白雪 S2（-22% 1s）、慑砂 S2（目标攻速 -3 3s）是明确的命中
   减益，其余为光环/自增益（海霓 S2、荒芜拉普兰德 S3、万顷 S2、
   黑键 S2 音色切换等）。
2. **实现**（apply_on_attack）：带 attack@duration 的
   attack@move_speed → moveSpeed mul 层（1.0 基数比率，-0.2 → ×0.8）；
   attack@attack_speed → attackSpeed add 层（100 基数百分比，-3 → 97）；
   无 duration 的光环键不误挂命中减益。
3. **验证**：test_attack_abnormals.py 新增 2 项（安哲拉 S2 移速 ×0.8
   3s、慑砂 S2 攻速 97 3s），8/8 全过；领域回归（干员技能/子职业/高级
   功能/元素天赋/巫役/浊燃/行医）9 文件 121 项全过。
## 2026-08-11 实时快照补齐单位细节字段（AI 打图信息面）

1. **需求**：目标要求"实时对外发送详细信息"供 AI 打图分析；快照此前
   缺元素条、攻速/阻挡数、敌方重量/攻击半径/天赋黑板等字段。
2. **实现**（entities.py）：
   - Unit.base_to_dict 新增：attackSpeed、blockCnt、
     elements（ep_neural/ep_water/ep_fire/ep_dark 数值 + 当前爆条冷却
     类型 burst 列表）；
   - Enemy.to_dict 新增：massLevel、rangeRadius、talentBlackboard
     （进化的本质 mode_* 阈值等直接可见）。
3. **验证**：test_live_server_chain.py 新增 1 项（敌方/干员快照含
   elements/attackSpeed/blockCnt/massLevel/rangeRadius/talentBlackboard，
   元素条数值与 0.6 形态阈值正确），3/3 全过；快照消费方（高级功能/
   UI 点击流/agent env）36 项全过。
## 2026-08-11 链愈师技能跳跃次数接线（attack@chain.extra_value）

1. **根因**：chain_heal_params/chain_max_target 只读天赋黑键（base
   max_target 3 / atk_scale 0.75），激活技能的 attack@chain.extra_value
   （莎草 S2 / 明椒 S2 / 乌啾 S1 / Mon3tr S1 "治疗的跳跃次数+X"）与
   attack@chain.max_target（跳跃次数覆盖）从未被消费。
2. **实现**（traits.py）：chain_heal_params 与 chain_max_target 增加
   激活技能 attack_effects 覆盖：chain.max_target 替换跳跃数、
   chain.extra_value 追加跳跃数（3 + 1 → 4）；链击（chainHit）同样
   支持技能覆盖。
3. **验证**：新增 test_chain_heal.py 2 项（莎草 S2 激活时治疗跳跃到
   4 名友方，未激活基线 3 名），2/2 全过；领域回归（行医/子职业/术师
   子类/干员技能/秘术/吟游）7 文件 85 项全过。
## 2026-08-11 麦哲伦 S1 周期停顿/束缚（attack@interval 通用路径）

1. **根因**：全库 6 个技能带 attack@interval（mgllan_1 / brigid_2 /
   tmoris_2 / lemuen_2 / mcnist_1 / rosesa_2），interval tick 只消费
   无前缀 `interval`；麦哲伦 S1 是被动+主动混合（未激活每 3s 停顿
   0.7s，激活期间停顿变为束缚 1.6s，技能结束回收无人机），完全未接。
2. **实现**（operator_skills.py）：
   - `ActiveSkillEffect.tick` 新增 attack@interval 周期分支：按
     `attack_effects.interval` 每周期施加 attack@frozen_duration
     （UNMOVABLE 束缚）或 attack@sluggish（moveSpeed mul -0.5 停顿），
     并复用 atk_scale/ep_damage_ratio 伤害/元素路径（tmoris S2 每秒
     法伤等受益）；
   - `OperatorSkillController._passive_attack_interval_tick`：未激活时
     按同一 attack@interval 周期对"自身 + 全部已部署无人机 token
     攻击范围"内敌人施加 attack@sluggish 停顿（麦哲伦被动常驻）；
   - 周期相位共享 `skill_run._interval_anchor`：激活只替换效果、不
     重置周期节奏（部署 15 → 被动 106/196/286/376 → 激活后束缚
     466/556/646/736/826，间隔恒 90 tick=3s，激活结束自动回到停顿）；
   - `apply_on_attack` 对周期束缚技能（interval + frozen_duration，
     麦哲伦）跳过命中附带的停顿，异常只来自周期路径；布丽吉特 S2
     （interval + sluggish 无 frozen_duration）命中停顿保留。
3. **验证**：新增 tests/test_mgllan_s1.py 4 项（被动周期/主动束缚
   节奏连续/无人机范围覆盖/命中不附加异常），4/4 全过；领域回归
   （麦哲伦+攻击异常+干员技能+高级功能+链愈+元素/巫役/浊燃/行医+
   术师子类）109 项全过。
## 2026-08-11 attack@def / attack@atk 激活增益 + 陈粘液地面

1. **根因**：全库 12 个技能带 attack@def* 键全部未消费；且
   apply_on_attack 把 attack@atk 当作"额外伤害"（per_hit=atk*scale+atk），
   全库扫描确认 attack@atk 全部是激活期百分比增益（catap2 S2 +55% 攻防、
   kalts S2/S3 Mon3tr 攻防、necras S3 仆役 80%、dolris/cetsyr 鼓舞等），
   无一为命中额外伤害——旧逻辑会对每个命中错误附加 atk 点伤害。
2. **实现**（operator_skills.py）：
   - apply_on_attack 移除 attack@atk 额外伤害（只保留 atk_scale 伤害，
     hunter 特例保留）；
   - on_start 新增 _apply_attack_effect_stat_buffs：attack@atk/def/max_hp
     （正值百分比→mul 层）与 attack@block_cnt（+1→add 层）按技能目标
     接线：kalts_1/2/3 Mon3tr、bstalk_2 磐蟹、necras_3 仆役（owner
     tokens）；pallas_3 身前近战位友方；acmedc_2 全部医疗干员；
     cetsyr_2/dolris_1 攻击范围内友方（鼓舞值）；自身增益已由 prefab
     OWNER buffs 提供（catap2 S2 / kalts S1 验证不 double）；
   - 陈 S2/S3 粘液地面：每次攻击（弹道命中）对范围内地面敌人施加
     attack@move_speed（mul）与 attack@def（add）减益，持续
     attack@projectile_life_time=5s（S2 -10%/-50、S3 -20%/-100），
     飞行敌人豁免。
3. **验证**：新增 tests/test_attack_def_buffs.py 7 项（kalts3 Mon3tr
   攻防、豆苗 S2 磐蟹防御、死芒 S3 仆役三属性、帕拉斯 S3 身前友方、
   陈 S2/S3 粘液、catap2 S2 命中无 0.55 额外伤害），7/7 全过；领域回归
   （干员技能/攻击异常/麦哲伦/高级功能/术师子类/链愈/帕拉斯/元素/巫役/
   浊燃/行医/吟游）125 项全过。
## 2026-08-11 attack@sp 命中回技力（掠风 S1 可靠电池）

1. **根因**：全库 11 个技能带 attack@sp* 键未消费。语义差异大：
   掠风 S1 命中给"可靠电池装备者"回 1 点技力（联网考证：可靠电池
   仅对术师/辅助干员生效）；安洁莉娜 S3 是投递部署干员回 6 SP；
   汽水瓶/荷谟伊哨站 token 砸到友方回 SP；惊蛰金币键为负值特殊。
2. **实现**（operator_skills.py apply_on_attack）：attack@sp 正值且
   skchr_windft_1 时，命中给所有场上术师（profession 32）/辅助（16）
   干员（含掠风自身）直接回复 attack@sp 点技力——直接用
   u.sp=min(sp_max, sp+v)，不走 recover_sp 的攻击回复 spType 门控
   （"回复技力"不受目标技能类型限制）。其余 attack@sp 技能各自语义
   留待对应机制（投递/汽水瓶 token/光环）接线。
3. **验证**：新增 tests/test_attack_sp.py 2 项（激活 S1 命中给自身+阿米娅
   各 +1 SP、医疗凯尔希不回；未激活命中不回），2/2 全过；领域回归
   （干员技能/攻击异常/麦哲伦/attack@def/高级功能）72 项全过。
## 2026-08-11 命中叠层 buff（attack@max_stack_cnt 家族）

1. **根因**：全库 28 个技能带 max_stack_cnt 相关键，其中可露希尔 S3
   （目标减速叠层）、佩佩 S3（自身攻击叠层）、维伊 S2（自身攻防叠层）、
   Sharp S3（自身攻击叠层+切目标清零）是明确的命中叠层机制，全部未消费；
   buff 系统同 key 刷新只取最大层数不自动递增，需调用方显式传目标层数。
2. **实现**（operator_skills.py）：
   - ActiveSkillEffect 新增 _stack_buff helper：层数 = min(当前+1,
     max_cnt)，mul（百分比）或 add（数值）单层值，每次命中刷新时长；
   - apply_on_attack 接线：可露希尔 S3 命中给目标叠加 3% 减速
     （attack@slow_down，3s，上限 10 层=30%）；佩佩 S3 每次攻击自身
     atk +10%（上限 4）；维伊 S2 每次攻击自身 atk +6% 与攻速 +5
     （attack@veen_s_2_buff[stack].*，上限 7）；Sharp S3 每次攻击自身
     atk +15%（无前缀 atk_each_stack/max_atk_stack_cnt，上限 8），
     切换攻击目标清零；
   - apply_on_attack 入口守卫放宽：无 attack@ 效果但属 Sharp S3
     （无前缀叠层键）时仍进入。
3. **验证**：新增 tests/test_stack_buffs.py 4 项（可露希尔 10 层封顶、
   佩佩 2 层 ×1.2、维伊双叠层 7、Sharp 切目标重置），4/4 全过；领域
   回归（干员技能/攻击异常/麦哲伦/attack@def/attack@sp/高级功能）
   76 项全过。
## 2026-08-11 风絮起飞机制（attack@fly_* / taraxa_fly_mode）

1. **根因**：attack@fly_height/fly_duration/fly_end_duration 是起飞
   动画参数，真正机制是"起飞状态"（风絮 S1/S2、兰 S2 立刻起飞）。
   游戏用 taraxa_fly_mode buff 模板（ChangeCharBlockMode FLY）实现，
   模板节点模拟器已支持但技能从未挂载；风絮 S2 attack@atk=+60% 未
   生效；S1"攻击间隔大幅度缩短"未实现。
2. **实现**：
   - on_start 新增 _apply_taraxa_liftoff：风絮 S1/S2、兰 S2 激活时挂
     taraxa_fly_mode buff（模板设置 op._block_mode=FLY，可阻挡飞行
     敌人），attack@base_attack_time 按 **攻击间隔乘数** 处理（PRTS
     确认 *0.2；属性 mul 层为 base*(1+mul)，换算 -0.8）；
   - _apply_attack_effect_stat_buffs 白名单加 taraxa_2/oblvns_2
     （自身攻击力增益）；
   - 风絮 S1 随机治疗：apply_on_attack heal_scale 目标改为攻击范围内
     随机一名已受伤单位（含自身）；
   - battle._op_liftoff 识别 _block_mode=FLY（风絮起飞也能挡飞行
     敌人）；on_expire 清理 buff 并恢复 _block_mode。
3. **验证**：新增 tests/test_taraxa_liftoff.py 3 项（S1 间隔 ×0.2 +
   随机治疗 atk×0.4、S2 攻击 +60%、起飞挡飞行敌人且技能结束释放），
   3/3 全过；领域回归（子职业/skywalker 阻挡/干员技能/攻击异常/
   麦哲伦/attack@def/叠层/attack@sp）74 项全过。
## 2026-08-11 兰 S2 飞翔瞪射（3 波箭 + 降落伤害）

1. **根因**：兰 S2（skchr_orchd2_2）激活只挂了起飞状态，核心输出
   机制（3 波箭 3/4/5 支 + 降落 2.4 倍伤害）完全未实现。
2. **实现**（operator_skills.py）：
   - on_start 记录激活 tick 与波次计数；tick 中 _orchd2_s2_tick 在
     起飞动画（fly_duration 0.2s）后发射 3 波箭（波间 1.3s 近似，4.2s
     窗口内完成），每波 3/4/5 支，每支造成 atk×attack@atk_scale_loop
     （1.2）物理伤害，目标=前方范围内敌人（多支箭对同一目标轮转）；
   - 新增 _is_front_target 前方方向判定（复用方向映射）；
   - on_expire 降落：对前方 2 格小范围所有敌人造成 atk×
     attack@atk_scale_end（2.4）物理伤害，并恢复 block mode。
3. **验证**：新增 tests/test_orchd2_s2.py 1 项（3 波箭总量 ≥
   atk×1.2×12、降落 ≥ atk×2.4、起飞/结束恢复），实测波次 tick 21/60/99
   （间隔 39）、降落 tick 141（4.2s）；领域回归（子职业/风絮/干员技能/
   高级功能）73 项全过。
## 2026-08-11 新约能天使 S3 使命必达（弹药 + 5 连击 + 投递部署）

1. **根因**：S3 激活自动 50 发弹药（is_ammo），但每次攻击只消耗 1 发
   （应为 5）、无 5 连击、投递坐标（token_10056_angel2_target）的
   溅射/部署/回 SP 全未实现。
2. **实现**（operator_skills.py）：
   - on_ammo_attack：angel2_3 每次攻击消耗 5 发（attack@trigger_time
     =50 总弹，10 次攻击后技能结束）；
   - apply_on_attack：angel2_3 强制 hits=5（每次攻击 5 连击 ×
     attack@atk_scale）；
   - 投递：场上有投递坐标 token 时每次攻击对其 3x3 造成 atk×
     attack@cannon_atk_scale（2.5）物理溅射；选择"再部署时间最长"的
     已撤退地面干员，投递部署至坐标（无视再部署冷却，先回收坐标
     token 腾格），部署干员获得 attack@sp（6）点技力。
   - 顺带确认：投递区域内的伤害会被新约能天使天赋"火力电台"
     （talent damage_scale，模拟器加载 1.5）经现有通用 token 区域
     增伤逻辑放大 ×2.5——真实游戏机制，非 bug。
3. **验证**：新增 tests/test_angel2_s3.py 2 项（无投递 6 次伤害调用=
   弹道+5 连击且弹药 50→45；投递时 6 次×2.5 + 溅射×2.5、清道夫
   部署回坐标、SP=14=init8+6），2/2 全过；领域回归（Ray 弹药套件/
   干员技能/攻击异常/高级功能/麦哲伦）77 项全过。
## 2026-08-11 汽水机/圣堂保育员装置回技力（attack@sp token 装置）

1. **根因**：喷射汽水机（trap_200_muulcl，attack@sp=3）与圣堂保育员
   扮演者（trap_237_hlnpcb，attack@sp=1 / attack@sleeper_sp=2）两个
   可部署装置的回 SP 技能完全未消费（token 无 skill_controller，攻击
   调度只选敌方目标）。
2. **实现**（battle.py token 调度）：
   - 汽水机：每 attack_interval=0.2s 随机喷一名友方干员，直接
     +attack@sp=3 技力（不受目标 spType 门控）；
   - 圣堂保育员：全图光环，每秒给所有友方 +attack@sp=1 技力，睡眠
     （DOZE flag 43，"美梦"近似）友方额外 +attack@sleeper_sp=2；
     光环累加器放在 token 每 tick 路径（原实现误放 attack_timer 分支
     导致每 0.5s 才累加，已修正）。
3. **验证**：新增 tests/test_trap_sp.py 3 项（汽水机 2 秒 +29 SP；
   保育员光环对比法 4 秒差 +3；睡眠友方 4 秒差 +9），3/3 全过；领域
   回归（装置/召唤物/无人机/Ray 沙兽/高级功能）57 项全过。
## 2026-08-11 琳琅诗怀雅金币系统（merchant 大买家）

1. **根因**：诗怀雅 merchant 金币（装备技能 blackboard `sp` 键=金币
   上限 S1=1/S2=3/S3=10）完全未实现：无金币存储、特性消耗费用不产
   金币、S1 消耗金币治疗、S3 击倒获币与关闭爆发全缺；且 S3"持续
   时间无限"被误判为 0.1s 瞬时技能。
2. **实现**：
   - OperatorSkillController：装备 swire2 技能时按 sp 键初始化
     op._coin_max/_coins（金币独立于 SP 槽）；
   - battle._trait_tick：merchant 特性消耗费用时若技能激活 +1 金币
     （"大买家"）；apply_damage 击杀处 S3 激活时 +1 金币；
   - S3 无限持续：ActiveSkillEffect 特判 skchr_swire2_3 为 sustained
     （原 _sustained 键表不含 atk_scale/sluggish/sp）；
   - trigger_on_deploy：S1/S2 部署消耗 1 金币（不足则不触发）；
   - S1 攻击命中：周围 8 格 HP<70% 友方恢复 atk×attack@heal_scale，
     触发后技能结束；S3 on_expire：消耗所有金币，每枚对前方范围随机
     敌人造成 atk×atk_scale 物理 + 小力推开。
3. **验证**：新增 tests/test_swire2_coins.py 4 项（三技能金币上限、
   S3 激活持续+费用消耗/击杀获币、关闭爆发消耗所有金币、S1 无币不
   触发/1 币触发治疗），4/4 全过；领域回归（干员技能/SP 机制/高级
   功能/技能系统）89 项全过。
## 2026-08-11 诗怀雅 S2 见面礼（香槟炸弹触碰触发）

1. **根因**：S2 只消耗金币不放置炸弹，香槟炸弹（token_10031_
   swire2_gdtrap）的触碰触发、停顿、3 秒二次伤害全未实现。
2. **实现**：
   - trigger_on_deploy：S2 消耗 1 金币后在范围内第一个可放置地面放
     香槟炸弹（记录放置 tick）；
   - battle._trigger_traps 新增香槟分支 + _trigger_champagne：敌人
     踩上造成 owner 攻击力×attack@atk_scale（1.4）物理伤害 + 停顿
     attack@sluggish（2s）；在场满 duration_switch（3s）后可额外
     触发一次（共 2 次），用完消失；
   - 修复回归中发现的误删：_trigger_traps 的 fired 循环恢复地雷等
     陷阱的 _retire_token 消费逻辑（traper 地雷触发后消失）。
3. **验证**：新增 tests/test_swire2_s2_bomb.py 2 项（放置+首次触碰
   atk×1.4 伤害+停顿 2s+炸弹保留；3 秒后二次触发+炸弹消失），2/2
   全过；领域回归（子职业/地雷陷阱/金币/干员技能）52 项全过。
## 2026-08-11 enm_pfb 技能 prefab 参数补齐（EnemySkill 免疫眩晕等）

1. **根因**：EnemySkill 的 `_immuneStunWhenAffecting`（0x39，施放中
   免疫眩晕）与 `_addEnemyIdToSignalId`（0x3A）未提取；扫描全量
   prefab 后确认游戏当前数据中 _immuneStunWhenAffecting 全为 0
   （字段未被实际使用），_addEnemyIdToSignalId 大量默认 1——补齐提取
   保证数据完整、消费逻辑就绪。
2. **实现**：
   - loader.synthesize_skill_entry 提取两个字段；
   - EnemySkillRun 读取 immune_stun_when_affecting /
     add_enemy_id_to_signal_id；
   - _start_cast 按技能设置 enemy._immune_stun_affecting，施放完成
     清除（链式后续技能重新设置）；
   - buffs.set_abnormal：flag==STUNNED 且目标施放中免疫标记时跳过。
3. **验证**：新增 tests/test_enemy_immune_stun.py 2 项（buff 层免疫
   眩晕+清除后可施加；_start_cast 设置标记），2/2 全过；领域回归
   （异常系统/攻击异常/敌方技能冒烟/Boss 行为）36 项全过。
## 2026-08-11 元素内部模型重构（累加式 → 满值扣减式）

1. **根因**：元素条原为累加模型（value 0→maxEp 累积，满值爆发），
   与游戏"满值 1000 扣减至 0 爆发"的内部模型相反；快照显示累积值
   而非剩余，AI 打图分析语义不一致。
2. **实现**：
   - buffs.update_ep：value = 剩余（初始 maxEp，受击扣减，≤0 爆发）；
     爆发后条重置满（等价原累积清零）；recover_ep 条向 maxEp 回升；
     _ep_burst_end 回满；add_ep_force 扣减且允许负值（超量累积，
     如 Blaze2 T1 2150 EP vs 1000 条，镜像原 >max 累积）；
   - targeting：_unit_ep 返回损伤量（maxEp−剩余），行医
     _wm_ep_metric/_wm_ep_full/_unit_ep_max/_unit_ep_over_half 全按
     损伤量判定（行医"元素值最低优先"顺带恢复游戏真实语义）；
   - entities 快照 elements 直接显示剩余值。
3. **验证**：更新 8 个测试文件的 EP 断言语义（换算为损伤量或剩余），
   全部通过：元素天赋/巫役/浊燃/爆发效果/爆发模板/模组/伤害矩阵/
   行医（含治疗排序）/快照链/UI/agent env 等 130+ 项全过。
## 2026-08-11 Boss xLua Nodes 覆盖率补齐（高频缺失节点）

1. **根因**：全量扫描 prefab 动作图（76 种节点类型）发现 55 种缺失
   handler，其中高频核心节点（TriggerAbility 40 / AlwaysNext 26 /
   CreateBuffToBlockee 18 / TriggerBuffsByKeys 16 / FilterByAbility-
   FinishReason 14 / EmitProjectile 12 / InterruptAbility 12 /
   CheckUnitCurrentMode 8 / DamageViaMaxHpRatio 6 / Withdraw 4 /
   ModifyCost 4 / AssignValueToBB 2）直接影响 Boss 技能行为。
2. **实现**（action_nodes.py）：
   - TriggerAbility：按 _abilityName 匹配技能控制器技能并施放；
   - CreateBuffToBlockee：对阻挡者施加 embedded buff（模板 key）；
   - TriggerBuffsByKeys：触发目标匹配 key 的 buff 模板；
   - EmitProjectile：spawn_projectile 发射弹道；
   - InterruptAbility：按名称/当前能力结束施放；
   - DamageViaMaxHpRatio：按目标 maxHp 比例伤害（PURE→TRUE）；
   - Withdraw：敌方标记退场/干员走 withdraw；
   - ModifyCost：黑键费用增减；AssignValueToBB：黑键赋值；
   - _check_condition 新增 CheckUnitCurrentMode（mode_index 匹配）与
     FilterByAbilityFinishReason（结束原因匹配）条件门。
3. **验证**：新增 tests/test_action_nodes.py 5 项（比例伤害/阻挡者
   buff/模板触发/费用+黑键/退场），5/5 全过；领域回归（Boss 行为/
   Boss 批量/敌方技能全 catalog 冒烟/高级功能）59 项全过。
## 2026-08-11 Boss xLua Nodes 第二轮（召唤类 + 重建/多 buff）

1. **根因**：重新扫描确认召唤类节点（SummonEnemiesFollowMyRoute 30 /
   SummonEnemiesWithRuntimeNearestEndPointRoute 18 / SummonTracking-
   EnemyWithFixedDirection 6 / SummonEnemyWithRuntimeRoute 4 /
   FollowBranchRoute 2 = 60 次）仍走简化 spawn（route_index=0），
   RebuildCharacterOnRandomTile（8）/FinishSeveralBuffsById（4）/
   TriggerAbilityUseSelector（4）/AssignBuffBlackboard（4）/
   CreateBuffOnTileInRange（4）/CreateNoSourceBuff（2）等未实现。
2. **实现**（action_nodes.py）：
   - SummonEnemies* 统一用 source.route_index 召唤到己方路线，并支持
     _summonCount 字段（原来漏读）；
   - 新增运行时路线/固定方向/分支路线召唤（enemy_key 支持黑键回退）；
   - RebuildCharacterOnRandomTile：目标随机可通行格复活满血 + 附加
     appear buff；
   - FinishSeveralBuffsById 批量移除；TriggerAbilityUseSelector 按
     abilityName 施放；AssignBuffBlackboard 写 buff 黑键；
     CreateNoSourceBuff 无源 buff；CreateBuffOnTileInRange 周围 3x3
     敌人 buff。
3. **验证**：test_action_nodes.py 扩至 9 项（新增召唤 2 只沿己方路线/
   随机格重建满血+buff/批量移除/无源 buff），9/9 全过；领域回归
   （Boss 行为/Boss 批量/敌方技能全 catalog 冒烟）40 项全过。
## 2026-08-11 Boss xLua Nodes 第三轮（$type 后缀修复 + 剩余战斗节点）

1. **根因**：发现关键 bug——真实 prefab 的节点 $type 带
   ", Assembly-CSharp" 后缀，action_nodes 的 short 提取只 rsplit("+")
   未去逗号，导致**所有真实数据的动作图分支匹配失败走 fallback**；
   另补剩余战斗节点（ChangeEnemyRouteMotionMode/IfNot/IfConditions/
   CheckAbnormalFlag/FilterId/IsCharacter/CheckHeightType/CreateBuff-
   InCircleRange/EmitProjectileAlongEnemyRoute/EnemyTracePointAway/
   AssignAttributeToBB/AssignMirrorTileToBB/AOEDamageFromProjectile/
   UpdateEnemyCurrentTile + Summon 带 buff）。
2. **实现**（action_nodes.py）：
   - _dispatch/_check_condition 的节点名提取加 split(",",1)[0] 去
     程序集后缀（真实数据动作图从 fallback no-op 变为真正执行）；
   - ChangeEnemyRouteMotionMode 修正：init_route 重建流场会重置
     _motion_mode，重建后重设目标模式；
   - SummonEnemies* 附加 _buffs 到召唤物；
   - IfNot/IfConditions 条件门 + CheckAbnormalFlag/FilterId/IsCharacter/
     CheckHeightType 门控；AssignAttributeToBB 写属性到黑键；
     AOEDamageFromProjectile 弹道溅射伤害。
3. **验证**：test_action_nodes.py 扩至 13 项（新增运动模式切换/条件
   门取反+异常检查/属性写黑键/弹道溅射），13/13 全过；领域回归
   （Boss 行为/Boss 批量/敌方技能全 catalog 冒烟）44 项全过。
## 2026-08-11 敌方 StealAttribute 实例解包核实（关闭遗留项）

1. **核实**：用 UnityPy 全量扫描 data/battle/enm_pfb_*.ab_unpacked
   （48893 个 MonoScript/MonoBehaviour 对象），m_ClassName/m_Name 均
   无 Steal 类——敌方 prefab 数据中**没有 StealAttributeAbility 组件
   实例**。此前发现的 trap_dyldlz_steal_t[random] 模板引用 "StealAtk"
   能力名，但该能力组件未随 enm_pfb 打包（活动专属动态资源），且
   引擎侧节点 handler 与 battle.steal_attribute 已就绪。
2. **结论**：该遗留项关闭（数据不存在，非解析缺失）；若未来游戏更新
   打包该组件，自动生效。
3. **验证**：整体健康检查（关卡加载/战斗集成/实时快照链/自定义关卡）
   25 项全过。
## 2026-08-11 跨领域综合健康回归

覆盖我方技能系统（28）/攻击异常（8）/麦哲伦周期（4）/诗怀雅金币
（4）/香槟炸弹（2）/元素天赋（6）/Boss 行为（14）/动作节点（13），
79 项全过（6 分 54 秒），确认模拟器跨领域整体稳定。
## 2026-08-11 全量干员技能管线冒烟（454 名）

1. **需求**：验证"我方干员"完整性——每个可部署干员（position
   1/2，454 名）部署 + 每个手动技能激活管线不崩溃。
2. **实现**：新增 tests/test_operator_full_scan.py（multiprocessing
   8 进程并行，每干员独立 Simulator：部署 → 手动技能 SP 填满激活 →
   中断）；无技能干员与纯部署/被动技能干员按数据合理跳过。
3. **验证**：454/454 全过（约 11 分钟）；调试中修正了扫描脚本自身
   的站位判定 bug（用 profession 判 position 错误，改用 position
   字段）——模拟器本身无部署/激活失败。
## 2026-08-11 敌方技能效果全量冒烟（1651 技能零 no-op）

1. **需求**：验证敌方技能不只是"施放不崩溃"，而是实际产生效果。
2. **方法**：对 skill_behavior_catalog 全部 1651 个敌方技能条目，
   施放 + 90 tick 后对比 buffs 数量/token 数/弹道数/事件数——零变化
   判定为 no-op。
3. **验证**：1651/1651 全部产生可观测效果（伤害/弹道/召唤/buff/
   事件），零 no-op——敌方技能管线完整性强证据。
## 2026-08-11 xLua 主线 15 PRTS 调度 + 日志节点

1. **核实**：剩余 xLua 缺失多为活动专属（乐土卡牌/赛车/游戏城/27 章
   侧面），其中主线 15 章 Main15TryNextPrtsAction（6 次）影响实际
   主线关卡。模拟器无完整 PRTS 剧情动作队列（该机制属主线 15 剧情
   调度，超出战斗核心）。
2. **实现**（action_nodes.py）：Main15TryNextPrtsAction emit
   prts_try_next 事件（force 标记）；LogExtraBattleInfo 记录到
   battle.stats.extraInfo 计数 + emit 事件。
3. **验证**：test_action_nodes.py 扩至 14 项（新增 PRTS 调度事件/
   日志计数），14/14 全过；领域回归（Boss 行为/敌方技能全 catalog
   冒烟）29 项全过。
## 2026-08-11 端到端交付审计（选择关卡/编队/敌人/战斗/快照）

1. **需求**：一条路径覆盖原始需求关键交付项：选择关卡 → 自定义编队
   （squad 注入）→ 部署干员 → 自定义敌人（覆盖 maxHp/def）→ 战斗
   推进 → 实时快照含详细信息。
2. **实现**：新增 tests/test_deliverables_e2e.py；调试中确认快照字段
   命名（干员 magicResistance→mres、敌人 enemyId→key）。
3. **验证**：端到端 1 项通过 + LiveServer 快照链 3 项通过（此前一次
   失败为并行运行端口冲突，单独重跑全绿）。
## 2026-08-11 buff 模板引擎节点覆盖核实（核心全覆、缺失皆活动专属）

1. **核实**：全量扫描 data_buff_templates.json 1341 种动作节点类型，
   与 buff_templates.py 的 502 个 _n_ handler 对比：491 种已覆盖。
2. **结论**：已覆盖的全部是核心通用节点（CreateBuff 4129 次使用 /
   IfElse 3446 / CheckContainsBuff 2047 / IfNot 1599 / SwitchMode
   1154 / ModifySp 321 / AdvancedApplyDamage 290 / AssignValueToBB
   461 / BlackboardAdd 180 等全部有 handler）；剩余约 850 种缺失
   几乎全是活动专属机制（各章活动 Act*Side、乐土卡牌 LegionMode、
   沙盒 Sandbox、赛车 Racing、足球 Football、合作 Coop、肉鸽
   Roguelike、自走棋 AutoChess、决斗 Duel 等），普通关卡战斗不受
   影响。增益减益核心管线完整性确认。
## 2026-08-11 通用 buff 节点补齐（HealToken/CopyHealth/UnlockHiddenArea）

1. **实现**（buff_templates.py）：HealToken 治疗 owner 的召唤物 token
   （豆苗 S1 治疗磐蟹，按 buff hp_ratio 比例）；CopyHealth 复制源血量
   给目标（支持按 maxHp 比例）；UnlockHiddenArea 清除地图迷雾区域。
2. **验证**：新增 tests/test_buff_common_nodes.py 3 项（磐蟹按 20%
   maxHp 治疗 224.2、复制血量 385.8、迷雾清除），3/3 全过；领域回归
   test_buff_templates.py 82 项全过（顺带修正该文件 2 处元素重构遗留
   断言：ep_fire 累积 10→剩余 990、恢复回满 1000）。
## 2026-08-11 弱点系统回归 + 元素重构遗留断言修正（第二轮）

领域回归（buff 触发/敌方 buff/技能时序/位移/弱点系统）37 项，修正
test_weakness_system.py 2 处元素重构遗留断言（phonor 脆弱缩放 EP 由
累积改为剩余、generic weak 不缩放 EP 断言改为剩余 900）后全过（9/9）。
## 2026-08-11 综合领域回归（技能/投射物/范围/特质/召唤/天赋光环等）

四批共 182 项全过：技能系统/技能格/投射物/范围/攻击时序（41）、
特质/子职业特质/召唤/漏斗/偷取/重量（63）、阿米娅 S3/全阻挡/费用
管理/伤害类型/分支阶段/秘术/祝福（31）、罗德岛屏障/罗德岛技能/
场地效果/潜行者/天赋光环/浊燃重生/波次时序（47）；顺带修正
test_talent_aura.py 8 处过时光环 key 断言（key 已带 value 后缀，
改为按 stat 字段判定）。
## 2026-08-11 剩余领域回归（agents/编辑器/敌方别名/预定义等）

两批 45 项全过：agents/编辑器/敌方 prefab 别名/敌方范围/预定义
（26）、关卡冒烟/关卡符文（19）。至此 tests 目录全部测试文件均已在
近期回归覆盖（除 benchmark 性能测试与 8 干员代表扫描外）。
## 2026-08-11 完整关卡通关模拟 + 性能确认

新增 tests/test_full_stage_run.py：01-01 全流程（部署 3 干员 → 波次
生成 → 战斗 → 结算）跑到 finished（tick 1603 结算 defeat、15 击杀），
1.3 秒跑完、约 1249 tps（≈41 倍速）——AI 打图分析性能可用；benchmark
2 项结构测试通过。至此所有 tests 测试文件（含 benchmark）全部覆盖。
## 2026-08-11 主线 14-17 剧情/环境节点补齐（简化）

实现（buff_templates.py）：Main15ForceSetBattleSpeedLevel/Insert/
Skip/FilterPrts 剧情调度（emit + 速度标记 + 子动作记录）、Main16
阴影区域（ChangeTileShadowViaRange 记录阴影矩形 + CheckInShadow 条件
门）、Mainline14 Lrdead 死亡通知与技能触发、Mainline17 Boss 点击计数
（记录 requiredClicks/successBuff 供 AI 层消费）。主线 15-17 关卡
行为覆盖提升；验证 test_buff_common_nodes.py 扩至 6 项全过，领域回归
（敌方技能全 catalog 冒烟/Boss 行为）21 项全过。
## 2026-08-11 LiveServer SSE 实时流确认 + buff 核心回归

确认"实时对外发送详细信息"完整可用：/stream SSE 推送含 snapshot 的
JSON 批次、/editor 页面、/enemies 搜索已有测试覆盖（test_live_server_
chain 3 项）。本轮 buff_templates 新增 11 个 handler 后重跑核心回归
（test_buff_templates 82 + test_buff_triggers 2 = 84 项）全过，无回归。
## 2026-08-11 AI 打图端到端回归确认

近期元素/buff/节点改动后重跑 test_agents.py（GreedyDefender 自定义
关卡胜利、主关卡运行、BeamAgent 束搜索胜利）+ test_agent_env.py
（观察/动作接口）共 15 项全过——"供 ai 打图分析"的 AgentEnv
（快照观察→决策→执行）管线在改动后仍稳定。
## 2026-08-11 关卡覆盖总量确认（3864 关抽样全加载）

关卡列表共 3864 个（主线 268 + 活动/其它 3538 + 教程/训练/周常），
活动关卡抽样 50 全部加载成功——除 OD-8 等个别活动关卡（数据未下载）
外，已解包的官方 gamedata 关卡覆盖完整。
## 2026-08-11 肉鸽（集成战略）关卡覆盖确认

肉鸽关卡 625 个（含 DLC）抽样 20 全部加载成功——集成战略战斗关卡
可加载可模拟。
