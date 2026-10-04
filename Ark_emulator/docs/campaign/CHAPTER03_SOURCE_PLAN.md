# Chapter 3 selected-stage source plan

`tools/build_chapter03_source_plan.py` generates and checks the non-executable `packages/campaign/chapter03_plans/source.plan.json`. Final SHA256 `d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6`. Build and `--check` actually succeeded. It locks21 inputs, fixed public commit `56aee3d6c5a29c3a0d192456d70d14252cbb0804`, retains13 exact ID/level/override variants, and does not modify old helpers, source packs or runtime code.

Both original level documents are retained in full: options, native map/palette/edges/tags, every action and wave/fragment flag, routes, runes/optional runes, predefines/hard predefines/cards, exclusion list, seed and auxiliary fields. The plan does not flatten controls or change native base life3; the user's life99999 override remains a future external scenario policy.

| Stage | Spawn population | Distinct DB variants | Source controls | Additional source dependencies |
|---|---:|---:|---|---|
| 3-7 | 61 | 9 | PREVIEW_CURSOR2, DISPLAY_ENEMY_INFO3 | Sensor E0L60 initial trap; five crate E0L1 cards; lurker invisible state; new ranged/ordinary variants |
| 3-8 | 63 | 8 | PREVIEW_CURSOR1, DISPLAY_ENEMY_INFO2 | Six tile_defup cells; Skullshatterer level1; yokai level1; stronger rogue/katar/handax variants |

The fixed12 deck does not justify deleting native traps/cards. Native deploy limits8 and9 are separate from deck cardinality. NORMAL selection leaves FOUR_STAR runes inactive, while preserving their source: 3-7 includes a crate initial-count−2 hard-mode rune, and both stages have difficulty-specific enemy/life modifiers. No inactive rune is silently applied to NORMAL here. No stage was compiled or run by this plan.

## Exact new closures

The plan directly loads local Unity trees and retains their PPtrs, GameObjects, MonoScript declarations and raw component fields. It freezes selected closures for `enemy_1009_lurker`, `trap_005_sensor`, `trap_001_crate`, `sktok_sensor`, and `tile_defup`, plus referenced BSON templates. Other new enemy modes/animation/projectile dependencies remain explicitly unextracted rather than claiming their behavior from DB prose.

Lurker's exact prefab is `enm_pfb_3/CAB-ef3a5632a5f1224887cc6e898efc163c`. `ToggleablePassiveBuffAbility`1815641500334631868 points to checker1915533585889569724. Its permanent self Buff has abnormalFlags[9], keytalent_1, loadFromDB0 and overrideEffectcommon_invisible. The checker has initOn1, disableWhenAttack1, disableWhenBlocked1, restoreDelay3; other disable switches are0. The actual enum declares INVISIBLE9 and CAMOUFLAGE17. Existing camouflage17 selection cannot substitute for9. Attack-event timing, blocked toggling, delayed restore and external immunity need a new generic content/state consumer; method bodies are not claimed restored.

Sensor and crate exact GameObjects are present in the already pinned official20250327 token bundle. Their component/script closures are retained with a clear2025-asset/2026-09-table gap. Sensor root has Trap/TrapMode and permanent self INVINCIBLE5; this is distinct from target-free and invisible. Its selected table skill is manual sktok_sensor: SP15, init0, continuous increment1, duration20, range x-3. The range table's actual25 diamond cells are included. Its real AuraAbility applies abnormalImmunes[9], removes members on leave and detachment, and its TargetValidator has enemy side2/motion3/category1/advancedOn/ignoreTargetFree1. SkillController's allowSpRecoveryWhenAffecting0 is source evidence for an explicit freeze choice.

Sensor's native instance is level60 although the current phase declares maxLevel30. All level1/30 attribute endpoint records are identical. The source contradiction remains explicit: a generic ordinary-operator level guard must not discard the native instance, while a constant-endpoint NPC stat profile can preserve the supplied numbers without inventing interpolation. Sensor is hiddenFalse; it is not an alias for the earlier dormant Adnach.

Crate is MapDependentTrap with finite five initial cards and passive sktok_crate. Its TrapMode records buildable0, passable0, overrideObstacleLikeMoveCost1 **and keepCurrentPassableMask1**. Thus blindly treating the raw passable0 as an unconditional wall is unsupported. Weighted route choice, legal placement, obstruction attack/destruction, ownership cleanup, height.4000000059604645, paid DP/refund and card depletion need explicit source consumers. The table's nominal blockCnt3 is not by itself proof of normal-character blocking behavior. Sensor's tile rewrite is a distinct policy and cannot be copied onto the crate.

3-8 tile_defup has actual blackboard def200, highland/RANGED/FLY_ONLY geometry. Its BuffTile attributeType2/formulaItem0/loadFromBlackboard1 supports a declared flat DEF200 adapter through the existing per-cell field framework. It is not a guessed resistance or percentage field. Native target options and clear-when-left fields are retained for the next consumer.

## Reuse with required rebinding

The inventory lists existing exact prefab-source candidates from chapter1/2 without claiming executable equivalence. Gopro2, handax, yokai and Skullshatterer have source candidates; new prefab keys still require their actual modes/frames/selectors/skills. A same prefab does not permit copying another variant's stats or level-dependent BB.

3-8's Skullshatterer is DBlevel1: HP30000, ATK1300 and the actual `.5` ratio BB. The earlier2-10 reference model's HP10500/ATK1000 and literal threshold5250 cannot be reused as those numbers. A rebound50% policy would use15000. Yokai is level1HP1870; its stage overwrittenData includes maxHp1450 with m_definedFalse, so1450 remains inactive. The full wrapper and inheritance rows are retained. Both stages' resolved enemy HP/SP recovery entries are zero; this is source evidence, not a universal no-regeneration assumption.

The next prioritized consumers are generic invisible9 toggle/immunity, sensor manual reveal and lifecycle/SP, crate cards/placement/path cost/destruction, DEF200 field, and new ordinary source attacks. Root has assigned invisible work separately. This document/source plan supplies dependencies only; it is not a complete converter, formal stage receipt or client verification. Missing method bodies are feedback items under the user's reference-first workflow and do not alone block model development.
