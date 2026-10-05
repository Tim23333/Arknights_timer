# Canonical damage lifecycle protocol V2

This is the new candidate's component protocol, retaining the existing generic
`resource.depletion` calculation contract and its original zero-health default.
It does not change the frozen parent's 107-contract catalog.

An entity may explicitly declare `trigger: health_zero_or_damage`. Positive
health can then create a finite lifecycle lease only from actual damage
settlement under the runtime's opaque damage capability. A normal resource
update, a public attack-shaped dictionary, or a static cast cannot create this
authority. The pillar source consumer uses this profile because native
`candead` plus `ON_TAKE_DAMAGE` can collapse a pillar with 4500 actual HP.

The original settlement event, requested and actual health values, source and
target stamps, selected pure plan, generation transition, phase, finite action
slots and scheduled jobs remain checkpoint obligations. Missing leases,
generation resets, orphan jobs and an unrecorded current-health change reject.
Dead or withdrawn owners with canceled jobs remain legal restoration states.

`selection_context: true` adds source/target selection projections to the pure
plan context. Restoration reconstructs those projections from the full
historical actor snapshots and pinned program Buff definitions. This lets a
source-declared plan distinguish actual silence, including Buff contributions,
without obtaining live World mutation access.

An owned action may start an explicitly possessed finite manual entity or tile
ability. External channel/projectile continuation remains excluded from this
terminal bridge. Actor selection/area effects are available only while the
actual owned callback task is executing; public ordinary activation and static
cast data do not acquire that permission.

Full historical timing-source values live in a dedicated causal event, with
World casts retaining its event ID and fingerprint. Restore checks event
type/ID/time/cause, actor stamp, generation, ability/cast ownership, value
fingerprint, pure timing traces and the original declared schedule. This avoids
recursively copying previous casts' proof snapshots into later parallel casts.

Explicit `instant_kill` options may specify `source_policy: none` and a nonempty
`origin`. A genuine finite callback can finish its own exhausted owner this way;
the resulting kill event has a literal `source: null`. This is independent of
the NoSourceDamage health protocol and of elemental health-plus-EP packets.

For Duspfr, the DeadLike Buff's native lifetime remains 3 seconds. The independent
Suicide child retains its float32 pre-delay `1.100000023841858`; the default
replaceable ceil quantizer therefore schedules tick 34 at 30 Hz. It is not
silently normalized to tick 33. Damage, PullDupilr and KillDuspfr have separate
native 1-second clocks; all five child abilities start concurrently.
