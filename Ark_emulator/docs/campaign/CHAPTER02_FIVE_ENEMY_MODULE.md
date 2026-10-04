# 2-9 five exact enemy closures

New module: `packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json`, SHA256 `4d9d07839243f1d2a7d7852f8952415f6971496473483765148a2def9ec10306`. `tools/build_chapter02_09_enemy_module.py --check` passed under M44. It binds only the stage's actual resolved variants, with source count26/8/2/12/4 (52 total):

| Native variant | Unit ID | Motion | HP | ATK | DEF | RES | Move speed | Attack interval | Steering factor / maximum |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| enemy_1005_yokai@0/94e6ea8ae7c08cbd | unit/chapter02/enemy_1005_yokai | FLY1 | 800 | 0 | 50 | 0 | .9 | 2.3 | 20 /100 |
| enemy_1005_yokai_2@0/dbec03902e7c8432 | unit/chapter02/enemy_1005_yokai_2 | FLY1 | 1550 | 220 | 50 | 0 | .9 | 3 | 20 /100 |
| enemy_1017_defdrn@0/46bb5552f4a5c320 | unit/chapter02/enemy_1017_defdrn | FLY1 | 4000 | 0 | 150 | 20 | .8 | 2 | 20 /100 |
| enemy_1013_airdrp@0/20e3225f73e1c6e6 | unit/chapter02/enemy_1013_airdrp/level_0/20e3225f73e1c6e6 | WALK0 | 1450 | 220 | 100 | 0 | 1 | 1.9 | 8 /10 |
| enemy_1013_airdrp_2@0/8903647724c13db5 | unit/chapter02/enemy_1013_airdrp_2/level_0/8903647724c13db5 | WALK0 | 2300 | 300 | 150 | 0 | 1 | 1.9 | 8 /10 |

Every selected root has source blockVolume1. Four variants define source mass0; defdrn has no defined mass and explicitly retains a replaceable model fallback0. All five source HP/SP recovery rates are0 and stunImmune isFalse. The builder rejects source changes to nonzero recovery or true immunity until an executable consumer is explicitly supplied; it does not turn unknown immunity into a fake numeric attribute. Default acceptance and absent recovery drivers are equivalent only for these locked values.

The previous flying prototype's empty spatial components omitted actual MoveController factor20/maxForce100. This module consumes those fields through the existing replaceable steering rule and marks FLY/WALK explicitly, while preserving the immutable old package. Arrival radius.05 is the declared mathematical policy; native steering-body calibration and half-body-width collision precision remain feedback items. Enemy names do not determine flight or variant level.

The public composition helper allows equal duplicates and rejects conflicting definitions. The builder records full explicit replacements and source hashes for defdrn's exact TargetValidator/silence driver, block/mass/motion and steering updates. It compiles a dependency-only five-actor scene, prunes unreachable definitions, then recompiles and compares actual executable definitions/rules/scene. The returned module contains23 author definitions and no stage scenario. Unused skulsr DEF-down is removed. Source tables, raw PPtr/typetree inventories and parent module bytes remain locked; the old first-seven/projectile/birth artifacts are unchanged.

`tools/experiments/chapter02_five/verify.py` actually imported M44 `81d12ea08787d4edeed139ab55dc73e424644a1b4b8f48360fb9b114b25203da`. Its fresh18 cases passed in16.02 seconds: two actual five-module checks, eleven source-backed defdrn cases and five independent hole/birth cases. The actual five-module scene proves native HP/ATK/DEF/RES/intervals and steering configurations, ground actors stationary before birth expiry, flight actors moving, ground motion resuming after45, ordered disk checkpoint continuation and recorded-command replay. Report `validation/campaign/chapter02_five/m44_final.json` SHA256 is `39fb7a365decb9b4640a4b060ab9e978374c512b5bf43c2028b6ae097d70c159`; actual core/input/helper hashes are unchanged.

The stage composer still separately consumes native52 spawns, seven Info repetitions, managed wave/fragment clocks, source routes,32 hole cells, gazebo FLY-only1.7 outgoing scaling/AS−20, the fixed12 roster and base life99999 commands. This module does not flatten waves or add a no-op hole. It provides dependencies for the declared-reference simulation delivery, not complete stage evidence or client verification.

An independent later M42 peer found a separate same-reconcile source-retirement defect: removal of A's child can retire the aura source while stale desired membership preserves B's child until maintenance. This bounded18-case report does not cover or resolve that counterexample. Frozen M42/M44 are retained; M45 is an independent revision assigned to the other agent. Integrating or promoting these dependencies requires that fix and new evidence under the resulting implementation identity. Native-body/precision feedback remains separate from this real execution gap.
