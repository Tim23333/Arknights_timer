# 2-10 exact twelve-variant reference module

Frozen module: `packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json`, SHA256 `bf13eb78c7b81dd0727c60f3d88d4f7d09a5244c6cfb9dad1e959ad0c5dd3859`. Its new generator is `tools/build_chapter02_10_enemy_module.py`; `--check` passed on M48. Twelve bindings expose `variant_id`, exact `native_reference`, `native_motion`, `unit_definition` and `spawn_count`, plus actual Enemy root, MoveController, mode/ability pointers and table operands. They total36 spawns, not the previous stage's52.

| Variant (all source level0) | Resolved suffix | Count | HP | ATK | DEF | RES | Interval | Selected attack clock |
|---|---|---:|---:|---:|---:|---:|---:|---|
| enemy_1027_mob | 0f723be34866a077 | 4 | 1700 | 250 | 50 | 0 | 2 | Melee f12 |
| enemy_1028_mocock | 069602c10526d517 | 2 | 1550 | 180 | 50 | 0 | 2.7 | f22, projectile speed5 |
| enemy_1027_mob_2 | b5774f909228b1e7 | 6 | 2650 | 350 | 85 | 0 | 2 | Melee f12 |
| enemy_1002_nsabr | 37e30b67e4fb40e4 | 2 | 1650 | 200 | 100 | 0 | 2 | Melee f12 |
| enemy_1015_litamr | c57a9f5e85b95f37 | 4 | 2500 | 250 | 400 | 0 | 2 | Melee f13 |
| enemy_1011_wizard | c9da7ae884f6e054 | 2 | 1600 | 200 | 50 | 50 | 4 | f19, projectile speed10 |
| enemy_1018_aoemag | 7dba1883dfa0b55a | 4 | 7000 | 240 | 120 | 50 | 3.8 | Specified.6669999957s →21ticks |
| enemy_1030_wteeth | 6886869808ffa02a | 3 | 5000 | 500 | 50 | 20 | 3 | Melee f19 |
| enemy_1033_handax | be90bb5c327669fc | 2 | 8000 | 750 | 80 | 30 | 3.3 | Melee f28 |
| enemy_1006_shield | 828a72f7f53f587e | 3 | 6000 | 600 | 800 | 0 | 2.6 | Melee f14 |
| enemy_1500_skulsr | 082a711ecbcd1bdf | 1 | 10500 | 1000 | 150 | 30 | 3 | Selected reference50 model: melee f53 /ranged f14,f17 |
| enemy_1017_defdrn | 46bb5552f4a5c320 | 3 | 4000 | 0 | 150 | 20 | 2 | No damaging attack; source aura/silence driver |

All selected source born delays are0; unexpected nonzero delays reject until a real born module is supplied. HP/SP recovery0 and stunImmuneFalse are guarded. The Skullshatterer source silenceImmuneTrue and defdrn's applicable talent remain in their separately source-backed modules. Undefined defdrn mass keeps its explicitly replaceable fallback0; other mass values and all blockVolume/leak costs come from source. Every entity gets typed side/motion/category/ordinary status data and exact mover parameters. Native getter/default details are marked feedback; a hook can consume the actual stored typed motion without silently reading absent fields.

The module reuses frozen wizard/mocock projectile definitions, source-qualified defdrn and the new frozen reference50 boss. Seven ordinary units generate actual blocked INPUT_TARGET melee abilities from their own mode/PPtr/frame data. Each selected entity receives its own source stat/mover/typed-state replacement with provenance, rather than changing parent packages. Exact source JSON, raw database/lock, stages, AB, Spine, BSON and dump identities are reread and hashed; unexpected additional root skills, talent blackboards, recovery, immunity or modes reject. The public composition helper rejects unreviewed conflicting definitions, prunes unreachable content, recompiles and checks executable values; the final module has71 definitions and no stage scenario.

For wizard/mocock and Aoemag, actual combat `selectTargetSource=2` is consumed through an ability-scoped declared score: existing blocker first, then base taunt/distance/stable ID. It is not bound to every enemy or to player rules. Ordinary melee selects its actual blocker directly; the boss retains its own ground-primary versus blocked-melee split. Native comparator internals remain feedback. A synthetic high-taunt alternate target cannot steal a true blocked combat packet in the independent two-ranged cases.

Aoemag's actual attack has waitForAttackEvent0 and specified preDelay.6669999957084656, so its packet is at21, not the unrelated visual OnAttack f24. The source PhysicsRange has two centered1×3 /3×1 BoxCollider2D shapes; their union is declared as target-centered cross5 cells. The [PRTS high-level caster reference](https://prts.wiki/w/%E9%AB%98%E9%98%B6%E6%9C%AF%E5%B8%88), successfully searched on2026-10-03, describes damage to the target and four neighboring cells. The [TR-12 reference](https://prts.wiki/w/TR-12) independently lists the usual2.2 attack radius. Neither page's generic stats replace the fixed 2-10 database.

Source trigger radius is2.0999999046325684; default `reference_2.2` explicitly selects2.2. `source_point_circle` is a replaceable alternative and the discrepancy is retained. A target at2.15 receives180 arts damage under the reference policy and none under the stationary source-point policy. Source local Unity XY, transforms and body-overlap mapping remain feedback; this module does not claim reconstructed Unity physics. Actual arts240 with RES25 settles180; an explicit fixture ATK+100% settles360 for exactly five living player targets. Cardinal cells including a flying splash victim are included, while diagonal cells and enemy-tagged actors are excluded; the shared center is not damaged twice.

Fresh M48 `a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9` imported from the actual candidate path ran15 cases in26.19 seconds. All source/package/helper/core hashes match at start/end. Every successful battle fixture has ordered disk checkpoint continuation and recorded-input command replay equality. Report `validation/campaign/chapter02_twelve/m48_final.json` SHA256 is `9aa4d08cfa005cca82e4dd1432e416609a10ef054f0f836c99a80707abc1f0f8`. The earlier successful15-case input lacking the `native_motion` metadata field, its original builder/test bytes and report are separately preserved under `initial_without_native_motion.*`; their SHA is not reused for the new module.

An initial unsealed projectile fixture swapped the known speeds of wizard and mocock. Reading the actual frozen source gives wizard10 (f19+3=22) and mocock5 (f22+6=28) for a one-cell shot; those source-derived expectations are used in the final tests. In the preblocked same-cell source-role cases, casting starts at1 and the first projectile update adds one tick: impacts21/24. These fixtures do not fabricate an already blocked relation with a direct World write.

No complete 2-10 stage was executed by this tool. Root separately composes the native managed timeline, two waves,36 spawns/two controls, routes, movement option.5, map/healing fields, fixed12/owned roster and recorded commands with base life99999. This module delivers the declared fixed-table/reference dependencies; no full stage, client comparison, promotion or formal receipt is asserted.
