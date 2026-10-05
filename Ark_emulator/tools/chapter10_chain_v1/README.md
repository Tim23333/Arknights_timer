# Finite impact chain candidate

Frozen runtime: `../unpack_work/campaign_c10_chain_v1_candidate`, core
`09c265c4a5f8d849f20d08a0e073db558d8d6a727f1060f3ad2a63cec2e1f7c6`.
Read-only parent: `cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18`.
The five changed core files and exact byte hashes are recorded in
`validation/campaign/chapter10_chain_v1/frozen.v1.json`.

`native_module.build_fragment()` returns the sourced dkmage attack/projectile
definitions and separate provenance. `mount(data, source_entity)` appends these
definitions and the new ability without removing any existing owned ability.
The assembler must provide the source's normal behavior selection, route,
remaining state-machine nodes and deathrattle. This attack scope alone does not
constitute a complete enemy or stage model. It preserves the raw RangedAttack
record, selector configuration, source blackboard and Spine animation binding.
Native EmptyAbility/behavior-node ordering remains the assembler's explicit
source obligation; it cannot be silently modeled as simultaneous parallel fire.

The opt-in projectile declaration is:

```json
{
  "chain": {
    "selector": "selector/c10/dkmage_chain/next",
    "maximum_targets": 4,
    "attenuation": 0.85,
    "selection_origin": "impact_position",
    "no_repeat": true,
    "lifetime": "whole_chain",
    "scale_fields": [
      ["health_effect", "scale"],
      ["element_effect", "parameters", "attack_scale"]
    ]
  }
}
```

The compound `elemental_attack` is carried by
`health_effect.projectile_definition`; health executes at actual impact before
EP. A target that dies from health receives no EP. Source and target attributes
are read at actual impact (`_useCachedAtkOnly=0`). The elemental packet computes
current ATK × source EP ratio × per-hop scale. The blackboard-selected profile
uses `.85` and radius `1.6`; original raw float `.8500000238418579` and collider
radius `1.7000000476837158` remain separate provenance, pending client review.

One owned projectile has one current trace target and one waiting source cast.
Each actual impact schedules one owned next-selection task for the next tick,
from the captured impact position. Selection reads current candidate positions,
active state, target availability, source-qualified eligibility, abnormal flags,
candidate tile facts when requested, priority scores and declared random stream.
Visited targets are excluded. A moved or dead candidate is evaluated at the
actual next-selection time. After a target has already been selected, homing
follows its movement; leaving the selection radius does not retroactively
cancel that captured leg. Invalid source/target and hidden policies are the
projectile's declared lifecycle policies. The single lifetime covers all legs.

Launch is bound to the current source cast, owned scheduled effect task and
declared packet. Step/expiry/next callbacks require exact issued task leases.
Actual impacts require the owned hit execution scope and corresponding health/EP
hit event. The journal records full launch source/target views, cast, packet,
program, position, RNG, time, task permissions, all impact history and current
candidate views. Restore validates full instance proof, hit uniqueness and
attenuation, exact pending task payloads/clock/phase and required future tasks.

Actual compact evidence:

- `author.v1.json`: nine cases, including four sequential public impacts,
  dynamic movement/death/target-free rejection, source retain/cancel, restore
  mutation rejection and atomic rejection of unowned callbacks; seven complete
  disk CP continuations and head replays compare snapshot, every event, count
  and full continuation state.
- `native.scope.v1.json`: sourced dkmage attributes and blackboard, actual
  automatic attack launches at ticks 37 and 157 (four-second cycle), four
  sequential health/EP impacts and complete disk CP/head equality.
- `primary_lackcounter.v1.json`: actual primary rejects undeclared `chain`.
- Failed fixture development reports remain separate and have no passed claim.

All raw test outputs use leased `E:/ArkSimLogs/runs` directories and are deleted
after validation by `run_with_log_cleanup.py`; independent receipts under
`E:/ArkSimLogs/receipts` record deleted bytes, remaining/protected files and errors.
Full parent regression and 0-1 baseline use separate reports and actual completion
identities. Model checks do not claim client accuracy or primary promotion.
