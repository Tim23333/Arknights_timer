# tests — 回归测试

`pytest` 驱动（`python -m pytest tests`，全量约 8 分钟）。每轮改造按
`docs/TEST_SCOPING.md` 的领域映射跑定向回归；改动影响 battle 核心/通用
buff 引擎/加载器/公共 API 时跑全量。

## 主要测试组

- **敌方**：`test_enemy_skill_smoke.py`（1651 技能零 no-op）、
  `test_boss_behavior.py` / `test_boss_batch.py`（Boss 行为/批量）、
  `test_enemy_range.py` / `test_enemy_buffs.py` / `test_enemy_immune_stun.py`
- **干员**：`test_operator_full_scan.py`（454 名部署+技能激活）、
  `test_operator_skills.py` 及各干员专项（阿米娅 S3、纯燚、诗怀雅、麦哲伦…）
- **buff/增益减益**：`test_buff_templates.py`（数百项）、
  `test_buff_triggers.py` / `test_buff_common_nodes.py` / `test_abnormal.py` /
  `test_damage_matrix.py` / `test_ep_break_templates.py`
- **机制**：`test_search_tick.py`（3-tick 索敌门控）、`test_prts.py`（PRTS
  调度）、`test_act31.py`（污染区）、`test_act35.py`（宝石）、
  `test_act_extra_nodes.py` / `test_extra_modes.py`（活动/肉鸽节点）、
  `test_attack_timing.py`（生效帧）、`test_displacement.py`、`test_traits.py`
- **关卡/场地**：`test_level_loading.py`、`test_level_smoke.py`、
  `test_tile_effects_e2e.py`、`test_custom_levels.py`
- **AI/实时**：`test_agents.py` / `test_agent_env.py`、
  `test_live_server_chain.py` / `test_ui_click_flow.py` / `test_editor.py`
- **端到端**：`test_full_stage_run.py`、`test_deliverables_e2e.py`、
  `test_advanced_features.py`

## 全量验证工具

`tools/scan_unhandled.py --stride 1`：扫描全部 3864 关，报告
`buff_node_unhandled`（当前为 0）。
