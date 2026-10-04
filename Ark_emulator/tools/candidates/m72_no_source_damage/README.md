# M72 explicit source-independent damage

This candidate is constructed from frozen M68 core
`1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8`.
M71/v12/v13 remain frozen and are not dependencies of this runtime. No V1 code
is imported. Only the parent's offline level JSON fixture is copied.

## Interface for M62

```python
result = ctx.effects.execute(None, selected_targets, {
    'op': 'no_source_damage',
    'fixed_amount': 700,
    'damage_type': 'true',
    'attack_type': 'NONE',
    'damage_without_modify': False,
    'ignore_for_sp': False,
    'node_is_env_damage': False,
    'env_blackboard_injected': True,
    'environmental': True,
    'origin': {
        'field_uid': field_uid,
        'cell': {'row': row, 'col': col},
        'trigger_sequence': sequence,
    },
    'rules': {'damage.pipeline': 'rule/model_no_source_fixed_pipeline'},
}, cause=trigger_event_id)
```

`pipeline.rule.json` provides a source-independent fixed PURE reference rule.
Add that rule to actual content/profile dependencies; it is not silently
injected at runtime. The op and every source-policy field are schema validated.
Only `fixed_amount` is accepted for the fixed input; `value`, actor ATK and
arbitrary unused `parameters` are rejected rather than pretending to be consumed.
An explicit `damage.pipeline` binding is required. It must not bind actor source
attributes. Target attribute bindings are consumed at hit, including declared
defaults. Numerical output remains replaceable through the existing contract.

The required booleans distinguish raw NoSourceDamage `_isEnvDamage=False`,
CastTile env-blackboard injection, the explicitly declared model ENV projection,
and `_ignoreForSp`. Current scope explicitly supports PURE/true,
`attack_type='NONE'`, `damage_without_modify=False`; unknown or unsupported
switches fail. Origin is a nonempty detached JSON record preserved through damage,
resource changes and genuine death/kill events. M62 owns injection of its live
field UID/cell/sequence and rejection of profile attempts to override those keys.

Selected target lists or a positive integer `target` are supported. Source must
be exactly None; actor ability/cast state cannot be borrowed. There is no source
before-hook, SourceCrit/Miss sampling, projectile launch or source attack-SP
claim. Target after hooks still run and may sample their declared streams.
Their source entity and source-buff-list views are `{}` and `[]`; attempting a
source attribute binding fails. Ordinary actor effect paths remain their
existing behavior. Existing ordinary `damage` with None still fails.

## Settlement and state

Live target activity, visibility and its `targeting.availability` rule are checked
before every packet. `SpatialSystem.available(None, ...)` receives `source={}`
and an explicit source selection projection with side2 (no actor/neutral model),
not a fictitious side0 field unit. Actual candidate flag9 and immunity9 projection
remain active. M62 can call this availability entry before pure membership and
again before damage.

The pipeline and after hooks produce full settlement/allocation plans. Resource
bounds and health-role lookup produce actual deltas before publication. For
HP100 hit by700, `pipeline_amount=700`, `actual_health_loss=100`, and accepted
`amount=100`. Shield charges are separate allocation deltas and do not count as
health damage. Positive health allocations do not become negative damage. The
primary `amount` reports primary target health loss; `total_health_loss` includes
all eligible health recipients and increments the battle's global damage total.
Each allocation records requested/actual delta and whether it is a health role.
Unknown allocation fields, dual delta+amount, negative/bool amounts and absent
source allocations fail atomically.

An accepted event is emitted before lethal cleanup so target event-SP eligibility
captures emission-time freeze using the existing resource mechanism. A no-source
accepted event with `ignore_for_sp=True` suppresses its event-SP recipients;
False retains the declared event driver. Source-role on-kill/attack drivers see
sourceNone, so no actor receives kill credit. Target still follows normal
lifecycle rule decisions. There is no immediate HP0 force-kill; standard revive
was verified, and only a genuine final runtime `dead` state produces combat.kill.
The M61 staged rebirth implementation remains a separate composition.

Lifecycle check receives the complete attribution and accepted-event cause.
For allocations, it runs once per recipient with health-row attribution preferred
over shield-row attribution. Genuine retirement uses an optional
`damage_attribution` keyword solely for this path, retaining sourceNone/origin in
entity.died. Existing ordinary retirement stays unchanged. Reconciliation, death
subscriptions and reaction queue remain existing engine semantics. An active
observer's sourceNone-origin death subscription was exercised; dead-owner skill
execution remains governed by its existing capability/lifecycle model.

After each packet, lifecycle objective evaluation may finish the battle. Remaining
packets stop on finished state and re-read target activity. Existing queued event
reactions are not forcibly executed recursively inside a damage packet.

All operations run under Session.atomic. Rule, after-hook, allocation, resource,
lifecycle or synchronous callback failures restore World/versions, scheduler
sequence/IDs, RNG samples/state and complete events. Asynchronous callback failures
retain the existing Session advance/failure boundary and are not claimed as an
expanded all-tick rollback protocol.

## Evidence and integration scope

Exact environment source SHA is
`148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8`.
The actual raw NoSourceDamage records are copied into the guarded validation
report; source/reference policy remains separate. Independent tests cover
positive/negative/mixed allocations, raw700/actual100, shields/invulnerability/cap,
source/target hook sampling, target role SP/freeze, typed9/immunity availability,
source bindings, genuine death observers/credit, normal revive, packet terminal
state, rollback and ordered public checkpoint/command-record replay.

Parent/candidate no-opt comparison uses separate interpreters and complete
snapshot/checkpoint/replay values for real0-1 tick120 and custom850 tick30.
Program fingerprint also changes because the compiler includes the newly added
supported-op catalog in program metadata. Reports list the exact changed program
and runtime fingerprint paths; every other value/type/float bit is compared.

Verification hashes all M68/M71/M72 Python files and task tools at start/end,
binds the consumed source/catalog files, and rebuilds M72 in a temporary checkout
to verify every source byte. No old accepted report is relabeled. This module
does not implement periodic trigger/membership, M61 staged rebirth/instant kill,
4-9 assembly, fullstage/36-stage completion or native client frame accuracy.
