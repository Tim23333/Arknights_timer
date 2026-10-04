# M41 declared ground contact and fall lifecycle

The independent candidate is frozen at `43cdc7a22226ed71c8743976254048e6d4fd2258fff6668f06eb2966e78fe9d3` in `../unpack_work/campaign_m41_hole_contact_candidate`. Its parent is the untouched M38 `2165e5e267fa62012867d7676e0ad68f53234217e0b62fec31ace3956f23fdd6`. Primary and every older candidate remain unchanged. This is a tested reference-based mathematical implementation; it is not an entire chapter completion or client accuracy receipt.

The source profile is `packages/campaign/chapter02_tiles/m41.hole.profile.json`, SHA256 `56295b4c0388e44230992bcaeb1b70d21b36b47beb71b4e2d17fea42074349d8`. The generator reads the frozen chapter 2 tile inventory, verifies its seven input locks, directly reloads HoleTile typetree and MonoScript with UnityPy, checks its actual GameObject component membership, and scans the original stage maps. The result includes 32 hole cells in 2-9 and none in 2-10. It includes the native map indices and a separately declared row flip; it does not alter native geometry or tiles.

Actual HoleTile component `-3839091121938991978`, root GameObject `-8581190342131747690`, and script `-2826163073248832506` bind to class `HoleTile`. The prefab's `_data.passableMask=0/buildableType=3` is distinct from 2-9's actual `passableMask=ALL/buildableType=NONE`. The source JSON retains both. `_injectEnvDmgFlagToBlackboard=1` is retained as evidence; it is not treated as a physical damage instruction. Dump callbacks `OnEnemyEnter` and `OnEnemyMotionModeChanged` expose signatures without restored method bodies.

The [PRTS combat mechanics reference](https://prts.wiki/w/%E4%BD%9C%E6%88%98%E6%9C%BA%E5%88%B6), read on 2026-10-03, supports checking ground enemies on tile entry, appearance completion, and movement-mode changes, and distinguishing failed death checks. It also describes historically changing path cost behavior. Consequently excluding holes from ordinary ground paths here is an explicit model choice, not a claim that every native version uses an impassable hole. The force-contact and appearance policies remain independent of native passableMask. Client feedback can revise these choices without embedding a tile or enemy ID into domain code.

## Content interface

Any declared tile key may bind this profile; kernel code never checks a special tile name:

```json
{
  "type": "contact_lifecycle",
  "rule": "rule/chapter02_ground_fall",
  "parameters": {},
  "normal_path_passable": false,
  "forced_contact_passable": true,
  "appearance_contact_passable": true,
  "health_policy": "zero",
  "death_reason": "dead",
  "reevaluate_each_tick": false
}
```

All keys are mandatory and typed. `tile.contact` is a new pure Boolean contract with entity/tile snapshots, cause, effective motion mode, readiness, and parameters. The supplied rule accepts an enemy when motion is WALK0 and readiness is true. A replacement expression, graph, or provider can deny a fall for a special state. Wrong contracts, unknown motion modes, non-Boolean output, and undeclared tile behavior reject. There is no guessed resurrection or phase change algorithm.

Normal routing uses `normal_path_passable`; forced clipping uses `forced_contact_passable`. Ordinary walls and map boundaries still clip. High speed displacement enumerates crossed cells and stops at the first accepted contact, avoiding tunneling over a one-cell hole. APPEAR uses its own explicit enterability gate and relocates without accruing movement-distance DoT, then checks contact before any posthumous route exit.

Actor effective `components.spatial.motion_mode` is explicit WALK0/FLY1. When supplied alongside a route it overrides the runtime route copy; the compiled source remains immutable. Omitted fields retain the existing normalized route mode/default ground convention. `set_motion_mode` is a public content effect with an exact integer `value` of 0 or 1. It clears derived paths/velocity, updates the runtime route copy, emits the mode transition, checks contact, and reconciles blocking atomically. Flying creation and actual forced flight over a hole are independently tested.

Born protection uses a separate typed Buff field `contact_flags: {"defer_fall": true}`. It is a half-open union over live Buff instances. No control, camouflage, invincibility, selector tag, or ability-disabled flag is inferred to mean born. The phase-0 contact observer is registered after Buff maintenance, so a 1.5-second protection expires at tick 45 and then falls on that tick. This is a declared logical appearance-completion profile. It is not evidence of a native animation callback. Sibling birth wrappers can add this field to their actual birth Buffs without replacing old source evidence. Arbitrary manual removal after that phase-0 observer may be checked by the next tick; this candidate does not implicitly alter all Buff remove semantics.

## Lifecycle and accounting

A fall has environment-contact cause, tile/cell, actual initiating source if a direct/forced displacement supplied one, and the target's owner. Route/birth/appearance contact has null initiator. `health_policy` explicitly selects zero or preserve; the supplied profile zeros the health resource without a damage effect. It emits `tile.contact_death` and invokes the existing `dead` lifecycle. Enemy dead lifecycle increments kills once, releases managed timeline membership, cancels its casts/lifetime/forced movement, and handles owned children according to their existing policy. It does not leak life, inflate damage_dealt, publish damage.accepted, or award a caster combat.kill event. Attribution and live native HP representation remain replaceable profile questions.

Static tile-field owners are excluded, as are dormant, retired and route-hidden actors. Projectiles do not call actor contact code. A denied special-death decision is not repeatedly retried on an unchanged cell by default, matching the explicitly chosen failed-check policy. Cell/motion/readiness changes trigger a new check; `reevaluate_each_tick=true` permits rules that depend on other changing state.

Settlement is within the same atomic movement/create transaction. A private reentrancy guard is cleaned with try/finally. Real death settlement failure after HP mutation, retirement, RNG draw and scheduling restores the whole pre-call checkpoint. Rule failure does likewise. This does not claim a failed scheduler handler can continue without restoring the session's valid checkpoint.

## Actual validation and remaining scope

`tools/experiments/m41_hole/test_contact.py` has 37 passing tests, final 3.22 seconds. Separate frozen-core engine/spatial/flying/timeline compatibility selection has 80 passes in 17.41 seconds, source identity unchanged before/after. `verify.py` stores each actual compile fixture and four public scenarios: move, push, motion change, and birth end. Each includes actual input/commands, ordered on-disk checkpoint, replay, final snapshot, and exact continuation/replay equality.

An unconfigured public movement witness preserves all 17 events and persistent World/RNG/scheduler/state values against M38. The only excluded identity fields are program/runtime/rule fingerprints, explicitly listed in the report: adding the contract changes identity. This bounded witness is not cross-version whole-stage equality. No new default binding or contact state/event is inserted into unconfigured actors.

The edge test exposed why one nextafter is insufficient at 0.5: `floor(nextafter(0.5, 0)+0.5)` can still equal 1. Opted-in contact maps now back off until the point projects into the previous cell; maps without contact retain the prior clip path. A forbidden forced entry therefore cannot accidentally die through rounding. Positive/negative travel and exact half-up margins are tested.

The final report is `validation/campaign/m41_hole/candidate_final.json`, SHA256 `0a23873cd547d2c0e1b1251392dd1619a300296e5c286015a25ae26f4c6c3c37`; patch SHA256 is `17d92e8562575b0b5bb57804f439e9ede6e5342c79b63d7fd1b18e823653ba1b`. Client body comparator, native path cost/appearance callback, death immunity/revive behavior, and talent credit remain explicit source or client pending items. They do not block delivery of this declared model under the user's reference-first workflow. No whole-stage test, promotion, receipt, commit or push was performed here.
