# 定向回归策略（替代全量回归）

每次改造只跑“影响领域”对应的测试；**只有改动影响全部（battle 核心 tick、
通用 buff 引擎、公共 API/快照、加载器）时才跑全量**。全量约 64 个文件
550+ 项、需 20+ 分钟，定向回归单轮 1~15 分钟。

## 2026-08-11 内存修复后全量耗时大降

- 根因：`stage_sim_bundle.json`（149MB）被每个 `DataStore` 实例重复解析
  （~750MB/份），每个 Simulator 战斗都重建一份；批次跑
  test_operator_full_scan 时 8 个 worker 峰值内存打爆系统（worker
  MemoryError，连带 adb/git 崩溃）。
- 修复：`loader.py` 进程级共享 `_BUNDLE_CACHE` / `_LEVELS_CACHE`（bundle
  与原始关卡 JSON 每进程只解析一次，只读共享）。
- 效果：全量 4 批 702 项约 6.5 分钟全绿（原 20+ 分钟且批次偶发 OOM）；
  test_operator_full_scan 576s → 40s；3 个并发战斗内存 2.27GB → 820MB。

## 领域 → 测试文件映射

| 影响领域 | 测试文件 |
|---|---|
| buff 模板 / buff 触发 | test_buff_templates.py、test_buff_triggers.py |
| 敌方属性 / 技能 / Boss | test_enemy_buffs.py、test_boss_behavior.py、test_boss_batch.py、test_enemy_prefab_aliases.py、test_enemy_range.py、test_enemy_skill_smoke.py |
| 敌方技能冒烟（全量目录匹配） | test_enemy_skill_smoke.py（1651 技能全跑） |
| 关卡 / 地图 / runes / 场地 | test_level_loading.py、test_level_runes.py、test_branch_phases.py、test_tile_effects_e2e.py、test_level_smoke.py |
| 干员技能 / 天赋 / 子职业 | test_operator_skills.py、test_amiya_s3.py、test_ray_kit.py、test_arts_subclasses.py、test_more_subprofessions.py、test_element_talents.py、test_ritualist_talents.py、test_t2_reborn_talents.py、test_funnel.py、test_bard_trait.py、test_mystic_trait.py、test_pallas_talents.py、test_blessing_trait.py、test_phatm2_s3.py、test_stalker_trait.py、test_wandermedic_trait.py、test_thumpy_talents.py |
| 模组 | test_modules.py |
| 元素 / 异常 / 伤害公式 | test_damage_matrix.py、test_damage_type.py、test_ep_break_templates.py、test_abnormal.py |
| 位移 / 力 / 阻挡 / 攻击结算 | test_displacement.py、test_force_weight.py、test_attack_all_blocked.py、test_attack_timing.py |
| 费用 / 高级功能 | test_cost_manager.py、test_advanced_features.py |
| 自定义关卡 / 自定义敌人 | test_custom_levels.py |
| 关卡加载冒烟 | test_level_smoke.py |
| agent / AgentEnv | test_agents.py、test_agent_env.py、test_battle_integration.py |
| LiveServer / 实时快照 | test_live_server_chain.py |
| 全部（影响所有） | test_enemy_skill_smoke.py + 全部其余测试 |

## 已知限制

- **range-gated targeting（已启用，2026-08-10）**：干员在范围内无目标时待机
  （真实游戏行为）。启用时同步完成：
  1) agent 路线感知部署：GreedyDefender._plan 的 vanguard 按 route_cells 靠近
     出生点落位、blocker 靠近出口/咽喉点，ranged 用 _best_direction 朝向覆盖
     路线；examples/bot.py 同样路线感知。
  2) 弱 squad 测试更新：test_agents/test_agent_env 的击杀关卡把干员部署到路线
     单元格 (2,5)；test_custom_levels 的 Bot 编队扩到 8 人（医疗/双阻挡/双输出）。
  3) targeting.py 在范围内无目标时 return None（范围外待机），删除 legacy
     全列表 fallback。

## 2026-08-10 行医索敌修正（元素值最低优先）

影响领域：医疗索敌 / 行医技能。定向回归：
`test_wandermedic_trait.py`（行医 12 项）+ test_operator_skills.py +
test_buff_templates.py + test_traits.py + test_more_subprofessions.py +
test_arts_subclasses.py（154 项）。

## 2026-08-10 行医/医疗多目标治疗（蜜莓 S1/S2）

影响领域：医疗索敌 / 治疗结算 / 多目标攻击快照。定向回归：
test_wandermedic_trait.py + test_operator_skills.py + test_buff_templates.py +
test_arts_subclasses.py + test_more_subprofessions.py + test_attack_timing.py +
test_attack_all_blocked.py（140 项）。

## 2026-08-10 元素爆发阈值 maxEp（默认 1000）

影响领域：元素损伤/爆发/满元素判定。定向回归：
test_ep_break_templates.py + test_element_talents.py + test_ritualist_talents.py
+ test_t2_reborn_talents.py + test_phatm2_s3.py + test_thumpy_talents.py +
test_wandermedic_trait.py + test_damage_type.py + test_abnormal.py +
test_damage_matrix.py（69 项）。

## 2026-08-10 纯艾 S3 火山回响（5 连发治疗 + 全图范围）

影响领域：医疗索敌 / 治疗结算 / 技能范围覆盖。定向回归：
test_wandermedic_trait.py + test_operator_skills.py + test_buff_templates.py +
test_arts_subclasses.py + test_more_subprofessions.py + test_attack_timing.py +
test_attack_all_blocked.py + test_phatm2_s3.py（144 项）。

## 2026-08-10 纯艾 T2 火山灰疗愈 aura（S3 期间 2 倍）

影响领域：天赋 aura / 范围作用域 / buff 数值刷新。定向回归：
test_wandermedic_trait.py + test_operator_skills.py + test_arts_subclasses.py +
test_more_subprofessions.py + test_pallas_talents.py + test_ritualist_talents.py
+ test_t2_reborn_talents.py + test_buff_templates.py + test_phatm2_s3.py
（149 项）。

## 2026-08-10 纯艾 T1 氤氲 HoT + dynamic 变量修复

影响领域：buff 模板（AdvancedApplyHeal/AssignAttributeAsDynamicVarToBB）/
治疗结算 / 周期性触发。定向回归：
test_wandermedic_trait.py + test_buff_templates.py + test_operator_skills.py +
test_arts_subclasses.py + test_more_subprofessions.py + test_phatm2_s3.py +
test_t2_reborn_talents.py + test_enemy_buffs.py + test_ritualist_talents.py
（161 项）。

## 2026-08-10 行医技能/天赋补全（哈洛德 T1/S2、桑葚 S2、纯艾 S1）

影响领域：医疗索敌 / 治疗结算（trait_scale）/ 天赋 aura（新 cond
ep_over_half + 技能 aura 注册）/ 技能 buff 窗口（prefab buff 跳过）。定向回归：
test_wandermedic_trait.py（25 项）+ test_operator_skills.py +
test_buff_templates.py + test_buff_triggers.py + test_arts_subclasses.py +
test_more_subprofessions.py + test_element_talents.py + test_ritualist_talents.py
+ test_t2_reborn_talents.py + test_pallas_talents.py + test_phatm2_s3.py +
test_thumpy_talents.py + test_enemy_buffs.py + test_ep_break_templates.py +
test_damage_type.py + test_abnormal.py + test_attack_timing.py +
test_attack_all_blocked.py（203 项）。

## 2026-08-10 哈洛德 WDM-X 模组（特性 ep_heal_ratio / 天赋强化）

影响领域：模组（module_trait_upgrades 新解析）/ 部署流程（battle.deploy
挂模组时应用特性升级）/ 行医特性 / 天赋 aura。定向回归：
test_modules.py + test_wandermedic_trait.py + test_operator_skills.py +
test_buff_templates.py + test_arts_subclasses.py + test_more_subprofessions.py
+ test_element_talents.py + test_ritualist_talents.py + test_t2_reborn_talents.py
+ test_pallas_talents.py + test_enemy_buffs.py + test_ep_break_templates.py +
test_damage_type.py + test_abnormal.py（219 项）。

## 2026-08-10 敌方领袖元素爆条阈值 2000（maxEp 规则修正）

影响领域：元素损伤爆条 / 满元素判定 / buffs.ep_max。定向回归：
test_ep_break_templates.py + test_element_talents.py + test_ritualist_talents.py
+ test_t2_reborn_talents.py + test_phatm2_s3.py + test_thumpy_talents.py +
test_wandermedic_trait.py + test_damage_type.py + test_abnormal.py +
test_modules.py（82 项）。


## 2026-08-10 元素爆条效果敌我分流 + 全局锁定 + 按类型冷却

影响领域：元素损伤爆条 / 爆发效果 / EP 锁定与恢复 / 伤害管线（虚弱）。
定向回归：test_ep_burst_effects.py + test_ep_break_templates.py +
test_abnormal.py + test_element_talents.py + test_ritualist_talents.py +
test_t2_reborn_talents.py + test_phatm2_s3.py + test_thumpy_talents.py +
test_modules.py + test_wandermedic_trait.py + test_damage_type.py
（91 项）。
## 2026-08-10 索敌刷新间隔 SEARCH_TARGET_TICK=3（3 tick = 0.1s）

影响领域：敌方普攻索敌 / 干员与医疗普攻索敌 / token 索敌（全局攻击目标
选择路径）。定向回归：test_search_tick.py + test_attack_timing.py +
test_attack_all_blocked.py + test_operator_skills.py + test_arts_subclasses.py
+ test_more_subprofessions.py + test_wandermedic_trait.py +
test_boss_behavior.py + test_boss_batch.py + test_phatm2_s3.py +
test_skill_tiles.py + test_enemy_buffs.py + test_ui_click_flow.py
（141 项）。


## 2026-08-10 属性偷取引擎（StealAttributeAbility）

影响领域：攻击命中结算 / 干员技能（agent/artsfghter/geek 等带偷取黑键的
技能）/ 撤退与死亡回收 / 快照 stealValues。定向回归：
test_steal.py + test_operator_skills.py + test_arts_subclasses.py +
test_more_subprofessions.py + test_attack_timing.py + test_attack_all_blocked.py
+ test_buff_templates.py + test_buff_triggers.py + test_boss_behavior.py +
test_boss_batch.py + test_modules.py + test_advanced_features.py +
test_ui_click_flow.py。


## 2026-08-10 敌方 maxEp 实证 + GainToken 部署链路

影响领域：敌方元素爆条阈值（实证收口，无代码改动）/ token 库存部署 API
与 LiveServer 动作。定向回归：test_gain_token.py + test_ui_click_flow.py +
test_buff_templates.py + test_advanced_features.py（111 项）。

## 2026-08-10 缪尔赛思流形 token 偷取

影响领域：token 创建/攻击命中 / 偷取引擎（token 来源）。定向回归：
test_steal.py + test_gain_token.py + test_operator_skills.py +
test_buff_templates.py + test_ui_click_flow.py + test_advanced_features.py
+ test_phatm2_s3.py + test_more_subprofessions.py + test_skill_tiles.py。

## 2026-08-10 敌方模式状态机（进化的本质）

影响领域：敌方技能控制器（EnemySkillController/EnemySkillRun，影响所有
敌方技能施放）/ 链式施放 / 快照 modeIndex。定向回归：
test_boss_behavior.py + test_boss_batch.py + test_enemy_buffs.py +
test_skill_system.py + test_damage_type.py + test_ep_break_templates.py +
test_abnormal.py + test_attack_timing.py + test_phatm2_s3.py +
test_thumpy_talents.py + test_buff_templates.py + test_advanced_features.py。

## 2026-08-10 远程攻击附带元素损伤延迟到弹道命中

影响领域：远程干员/召唤物攻击命中结算（apply_on_attack 与偷取延迟到弹道
命中）/ 弹道 spawn hit_extra。定向回归：test_element_talents.py +
test_operator_skills.py + test_attack_timing.py + test_phatm2_s3.py +
test_ritualist_talents.py + test_t2_reborn_talents.py + test_thumpy_talents.py
+ test_wandermedic_trait.py + test_more_subprofessions.py +
test_arts_subclasses.py + test_ui_click_flow.py + test_advanced_features.py
+ test_buff_templates.py + test_skill_tiles.py + test_steal.py。

## 2026-08-10 本源术师元素语义修正（折光/妮芙爆发期直伤 + 按技能解析损伤类型）

影响领域：干员技能 attack@ 附带元素损伤类型（ep_damage_ratio 不再硬编码
神经）/ 爆发期额外 ELEMENT 直伤（apply_damage element_as_hp）/ 弹道命中
结算。定向回归：
test_element_talents.py + test_operator_skills.py + test_ritualist_talents.py
+ test_wandermedic_trait.py + test_phatm2_s3.py + test_thumpy_talents.py
+ test_ep_break_templates.py + test_ep_burst_effects.py + test_damage_type.py
+ test_abnormal.py + test_weakness_system.py + test_damage_matrix.py
+ test_sp_mechanics.py + test_modules.py + test_t2_reborn_talents.py
+ test_advanced_features.py + test_skill_tiles.py + test_steal.py
+ test_gain_token.py + test_search_tick.py + test_boss_behavior.py
（212 项全过）。
## 2026-08-10 敌方天赋黑板接入 + 进化的本质 HP/时间驱动形态机

影响领域：敌方实体初始化（spawn_enemy talent_blackboard）/ 敌方技能
控制器（模式切换门控、每 tick 条件检查、每形态被动）/ 伤害管线
（apply_damage 形态减伤）。定向回归：
test_boss_behavior.py + test_boss_batch.py + test_enemy_buffs.py
+ test_enemy_prefab_aliases.py + test_enemy_range.py
+ test_enemy_skill_smoke.py + test_damage_matrix.py + test_damage_type.py
+ test_weakness_system.py（14+67+1=82 项全过）。
## 2026-08-10 官方 gamedata 关卡补全（新增 1010 关卡）

影响领域：关卡数据（data/levels 新增官方 JSON 转换文件 + 重建
stage_sim_bundle.json）/ 关卡加载与地图/路由/波次消费（merged_routes、
build_route_field、spawn_enemy、_runes_for 加固）。定向回归：
test_level_loading.py + test_level_smoke.py + test_level_runes.py
+ test_custom_levels.py + test_live_server_chain.py（28 项全过）
+ 随机 60 个新关卡可加载冒烟。
## 2026-08-10 官方关卡 predefines JSON 回退

影响领域：关卡初始化（battle 预定义单位 spawn 路径）/ predefines 解析
（新增 JSON 回退）。定向回归：test_level_loading.py（5 项）+
test_level_runes.py + test_custom_levels.py + test_tile_effects_e2e.py
（27 项）全过。
## 2026-08-11 攻击附带异常状态接线（寒冷/沉睡/浮空/恐惧/束缚）

影响领域：干员技能攻击命中结算（apply_on_attack 新增异常键）/
异常免疫名称映射（buffs._buff_abnormal_immune）。定向回归：
test_attack_abnormals.py（4 项）+ test_operator_skills.py +
test_abnormal.py + test_element_talents.py + test_ritualist_talents.py
+ test_thumpy_talents.py + test_wandermedic_trait.py + test_buff_templates.py
+ test_damage_type.py + test_ep_burst_effects.py（174 项）全过。
## 2026-08-11 buff_prob 概率门控 + DamageScale 缩放键修复

影响领域：干员攻击附带异常概率（apply_on_attack buff_prob）/ buff 模板
DamageScale 缩放键（buff_templates，影响 295 处游戏模板）。定向回归：
test_buff_templates.py + test_buff_triggers.py + test_enemy_buffs.py
+ test_damage_matrix.py + test_damage_type.py + test_weakness_system.py
+ test_ep_break_templates.py + test_operator_skills.py +
test_attack_abnormals.py + test_ep_burst_effects.py（178 项）全过。
## 2026-08-11 攻击附带属性减益接线（移速/攻速）

影响领域：干员攻击命中结算（apply_on_attack 新增 attack@move_speed /
attack@attack_speed + duration 命中减益）。定向回归：
test_operator_skills.py + test_arts_subclasses.py + test_more_subprofessions.py
+ test_advanced_features.py + test_attack_abnormals.py +
test_element_talents.py + test_ritualist_talents.py + test_thumpy_talents.py
+ test_wandermedic_trait.py（121 项）全过。
## 2026-08-11 实时快照补齐单位细节字段

影响领域：Unit/Enemy 快照序列化（entities.to_dict 新增 elements /
attackSpeed / blockCnt / massLevel / rangeRadius / talentBlackboard）。
定向回归：test_live_server_chain.py（3 项）+ test_advanced_features.py
+ test_ui_click_flow.py + test_agent_env.py（36 项）全过。
## 2026-08-11 链愈师技能跳跃次数接线（attack@chain.extra_value）

影响领域：TraitSystem 链愈/链击参数（chain_heal_params / chain_max_target
读取激活技能 attack_effects）。定向回归：test_chain_heal.py（2 项）+
test_wandermedic_trait.py + test_more_subprofessions.py +
test_arts_subclasses.py + test_operator_skills.py + test_mystic_trait.py
+ test_bard_trait.py（85 项）全过。
## 2026-08-11 麦哲伦 S1 周期停顿/束缚（attack@interval 通用路径）

影响领域：干员技能周期效果（ActiveSkillEffect.tick attack@interval 分支
新增束缚/停顿/伤害）、技能控制器被动周期（_passive_attack_interval_tick）、
攻击命中异常排除（apply_on_attack 周期束缚技能跳过命中停顿）。定向回归：
test_mgllan_s1.py（4 项，新增）+ test_attack_abnormals.py +
test_operator_skills.py + test_advanced_features.py + test_chain_heal.py
+ test_element_talents.py + test_ritualist_talents.py +
test_thumpy_talents.py + test_wandermedic_trait.py +
test_arts_subclasses.py（109 项）全过。
## 2026-08-11 attack@def / attack@atk 激活增益 + 陈粘液地面

影响领域：干员攻击命中结算（apply_on_attack 移除 attack@atk 额外伤害）、
技能激活期属性增益（on_start 新增 _apply_attack_effect_stat_buffs 给
召唤物/友方）、陈 S2/S3 粘液地面减益（弹道命中路径）。定向回归：
test_attack_def_buffs.py（7 项，新增）+ test_operator_skills.py +
test_attack_abnormals.py + test_mgllan_s1.py + test_advanced_features.py
+ test_arts_subclasses.py + test_chain_heal.py + test_pallas_talents.py
+ test_element_talents.py + test_ritualist_talents.py +
test_thumpy_talents.py + test_wandermedic_trait.py + test_bard_trait.py
（125 项）全过。
## 2026-08-11 attack@sp 命中回技力（掠风 S1 可靠电池）

影响领域：干员攻击命中结算（apply_on_attack 新增 attack@sp 消费，
掠风 S1 给术师/辅助装备者直接回 SP）。定向回归：test_attack_sp.py
（2 项，新增）+ test_operator_skills.py + test_attack_abnormals.py +
test_mgllan_s1.py + test_attack_def_buffs.py + test_advanced_features.py
（72 项）全过。
## 2026-08-11 命中叠层 buff（attack@max_stack_cnt 家族）

影响领域：干员攻击命中结算（apply_on_attack 新增 _stack_buff 叠层：
可露希尔 S3 目标减速叠层、佩佩 S3/维伊 S2/Sharp S3 自身属性叠层、
Sharp 切目标清零；入口守卫放宽支持无前缀叠层键）。定向回归：
test_stack_buffs.py（4 项，新增）+ test_operator_skills.py +
test_attack_abnormals.py + test_mgllan_s1.py + test_attack_def_buffs.py
+ test_attack_sp.py + test_advanced_features.py（76 项）全过。
## 2026-08-11 风絮起飞机制（attack@fly_* / taraxa_fly_mode）

影响领域：技能激活期起飞状态（on_start 挂 taraxa_fly_mode 模板 →
ChangeCharBlockMode FLY）、攻击间隔乘数（attack@base_attack_time
*0.2）、自身攻击增益（taraxa_2/oblvns_2）、命中随机治疗目标（风絮
S1）、阻挡系统（battle._op_liftoff 识别 _block_mode FLY）、技能结束
恢复（on_expire）。定向回归：test_taraxa_liftoff.py（3 项，新增）+
test_more_subprofessions.py + test_operator_skills.py +
test_attack_abnormals.py + test_mgllan_s1.py + test_attack_def_buffs.py
+ test_stack_buffs.py + test_attack_sp.py（74 项）全过。
## 2026-08-11 兰 S2 飞翔瞪射（3 波箭 + 降落伤害）

影响领域：技能激活期波次射击（_orchd2_s2_tick 3/4/5 支箭 ×
atk_scale_loop）、前方方向判定（_is_front_target）、技能结束降落伤害
（on_expire atk_scale_end）+ 起飞恢复。定向回归：test_orchd2_s2.py
（1 项，新增）+ test_taraxa_liftoff.py + test_operator_skills.py +
test_more_subprofessions.py + test_advanced_features.py（73 项）全过。
## 2026-08-11 新约能天使 S3 使命必达（弹药 + 5 连击 + 投递部署）

影响领域：弹药消耗路径（on_ammo_attack 按技能区分消耗量）、攻击命中
连击数（apply_on_attack angel2_3 hits=5）、投递部署（投递坐标 token
溅射 + 再部署最久干员 + 回 SP）。定向回归：test_angel2_s3.py（2 项，
新增）+ test_ray_kit.py + test_operator_skills.py + test_attack_abnormals.py
+ test_advanced_features.py + test_mgllan_s1.py（77 项）全过。
## 2026-08-11 汽水机/圣堂保育员装置回技力（attack@sp token 装置）

影响领域：token 调度循环（battle.py 新增 trap_200_muulcl 随机喷友方
+3 SP、trap_237_hlnpcb 全图每秒光环 +1 SP、睡眠友方额外 +2）。定向
回归：test_trap_sp.py（3 项，新增）+ test_gain_token.py +
test_funnel.py + test_mgllan_s1.py + test_ray_kit.py +
test_advanced_features.py（57 项）全过。
## 2026-08-11 琳琅诗怀雅金币系统（merchant 大买家）

影响领域：金币存储初始化（operator_skills 按 sp 键设上限）、merchant
特性消耗费用获币（battle._trait_tick）、击杀获币（apply_damage）、
S3 无限持续、部署消耗金币（trigger_on_deploy）、S1 命中治疗、S3 关闭
爆发。定向回归：test_swire2_coins.py（4 项，新增）+
test_operator_skills.py + test_sp_mechanics.py + test_advanced_features.py
+ test_skill_system.py（89 项）全过。
## 2026-08-11 诗怀雅 S2 见面礼（香槟炸弹触碰触发）

影响领域：部署放炸弹（trigger_on_deploy 范围内可放置地面）、陷阱触发
系统（battle._trigger_traps 香槟分支 + _trigger_champagne 触碰伤害/
停顿/3 秒二次触发）、陷阱消费逻辑恢复（fired 循环 _retire_token）。
定向回归：test_swire2_s2_bomb.py（2 项，新增）+ test_more_subprofessions.py
+ test_swire2_coins.py + test_operator_skills.py（52 项）全过。
## 2026-08-11 enm_pfb 技能 prefab 参数补齐（EnemySkill 免疫眩晕等）

影响领域：敌方技能 prefab 参数提取（loader.synthesize_skill_entry 新增
_immuneStunWhenAffecting/_addEnemyIdToSignalId）、施放免疫标记
（skills.py _start_cast / 完成清除）、异常免疫（buffs.set_abnormal
STUNNED 跳过）。定向回归：test_enemy_immune_stun.py（2 项，新增）+
test_abnormal.py + test_attack_abnormals.py + test_enemy_skill_smoke.py
+ test_boss_behavior.py（36 项）全过。
## 2026-08-11 元素内部模型重构（累加式 → 满值扣减式）

影响领域：buff 元素存储语义（update_ep/recover_ep/_ep_burst_end/
add_ep_force）、targeting 元素判定（_unit_ep 损伤量 + 行医排序）、
快照 elements 剩余值。定向回归：test_element_talents.py +
test_ritualist_talents.py + test_t2_reborn_talents.py + test_phatm2_s3.py
+ test_ep_burst_effects.py + test_ep_break_templates.py + test_modules.py
+ test_damage_matrix.py + test_live_server_chain.py + test_abnormal.py +
test_wandermedic_trait.py + test_thumpy_talents.py + test_ui_click_flow.py
+ test_agent_env.py（130+ 项）全过。
## 2026-08-11 Boss xLua Nodes 覆盖率补齐（高频缺失节点）

影响领域：敌方技能动作图执行（action_nodes.py 新增 TriggerAbility/
CreateBuffToBlockee/TriggerBuffsByKeys/EmitProjectile/InterruptAbility/
DamageViaMaxHpRatio/Withdraw/ModifyCost/AssignValueToBB + 条件门
CheckUnitCurrentMode/FilterByAbilityFinishReason）。定向回归：
test_action_nodes.py（5 项，新增）+ test_boss_behavior.py +
test_boss_batch.py + test_enemy_skill_smoke.py + test_advanced_features.py
（59 项）全过。
## 2026-08-11 Boss xLua Nodes 第二轮（召唤类 + 重建/多 buff）

影响领域：敌方技能动作图（action_nodes.py SummonEnemies* 路线召唤 +
_summonCount、RebuildCharacterOnRandomTile、FinishSeveralBuffsById、
TriggerAbilityUseSelector、AssignBuffBlackboard、CreateNoSourceBuff、
CreateBuffOnTileInRange）。定向回归：test_action_nodes.py（9 项）+
test_boss_behavior.py + test_boss_batch.py + test_enemy_skill_smoke.py
（40 项）全过。
## 2026-08-11 Boss xLua Nodes 第三轮（$type 后缀修复 + 剩余战斗节点）

影响领域：action_nodes 节点名提取（去 Assembly-CSharp 后缀——修复
真实数据动作图全 no-op）、运动模式切换/条件门/属性写黑键/弹道溅射
等剩余战斗节点、Summon 带 buff。定向回归：test_action_nodes.py
（13 项）+ test_boss_behavior.py + test_boss_batch.py +
test_enemy_skill_smoke.py（44 项）全过。
