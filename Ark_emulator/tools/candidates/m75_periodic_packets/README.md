# M75 same-frame periodic packet continuation

The immutable parent is M73 core
`1b548c29fba3dd19c177fbb458a0226e496b15a03c5c2a3599243bcb20e40932`.
Its actual minimum public-content failures remain in
`validation/campaign/m73_environment_peer/callback_reproduction`: normal
damage.accepted subscriptions retire or move the second target, yet M73 damages
it first. M73 files and original reports are never edited or relabeled.

M75 retains the same authored periodic field and no-source request interfaces.
There are no new imaginary content effects for field deletion/scene completion.
Normal ability subscriptions can retire/reposition targets or change objective
resources; a host callback can call the existing public field.remove or
state_update methods. Source-free numerical settlement is unchanged from M72.

`pulse` now verifies its actual owned scheduler sequence/due/generation/sequence,
emits exactly one field.triggered record, increments the next-trigger sequence
once, and publishes a World-owned packet chain. All fields share one FIFO in
the battle's periodic_fields state. A chain records trigger-event token,
generation, captured member order and current effect/member cursor. Only one
global packet dispatch is pending. Its exact task ID, scheduler sequence, due,
phase, token and cursor are checkpoint state. Copied payloads/direct handler calls
do not own those identities and cannot apply a duplicate packet or RNG sample.

Pulse runs at phase0. The first dispatcher runs at base effect_phase+1, after
all normal field.triggered reactions. Each subsequent packet/completion dispatch
uses a strictly later numeric phase. During opt-in periodic execution only,
RuntimeContext.effect_phase is max(base effect phase, active numeric scheduler
phase). This allows ordinary event reactions, ability.start and delay0 effects to
schedule at their current stage. Existing scheduler order naturally drains that
complete stage before it chooses the next higher-stage packet. There is no direct
queue flush, hidden callback executor or deletion of historical events. External
same-frame tasks retain their deterministic phase/priority/sequence ordering.

Stages are not an unbounded out-of-band loop: each packet and queued reaction is
still a counted Session callback under the existing reaction budget. An infinite
reaction cascade fails that budget before later packets run. This reference
protocol uses the Engine's numeric phases; it is not a new named-phase ordering
implementation. The effect_phase setter remains available, and profiles absent
retain the original raw phase and all other behavior.

Before each packet, lifecycle objective evaluation sees resource changes caused
by preceding callbacks, then field generation/activity, battle completion, live
membership, visibility and target availability are read again. Member order and
effect order remain the captured FIFO sequence; eligibility is always live. After
the last candidate, a separate completion task waits for its callbacks before
sampling the next interval. Empty chains use the same completion boundary.

Removing a field cancels its owned pulse/continuation identities, discards its
chain and advances its generation. Other FIFO fields remain. Terminal state stops
all field-owned tasks without consuming future interval samples. Trigger sequence
counts actual emitted triggers, even when a later callback removes a field; the
captured chain retains the trigger's original origin sequence.

Each pulse/packet transaction is atomic. In periodic programs, each complete
event_reaction callback also runs under Session.atomic. A failed callback restores
its own World, RNG, scheduler and events boundary. Already completed earlier
packets remain committed. Session records the failure and blocks advancement;
pending continuation is not silently skipped or retried. Ordered checkpoint
reload of that failure state remains blocked. Recovery requires restoring an
earlier valid boundary and correcting the cause, with normal version identity
rules. This does not claim an all-trigger rollback across scheduler callbacks.

Fresh tests retain the M73 failing fixtures and cover public retire/reposition,
ability.start plus delay0 cascade, multi-field FIFO, legal life-resource defeat,
public host removal, callback failure boundaries, duplicate pulse/packet ownership,
reaction-budget cycle, external same-frame ordering, actual ordered checkpoint
reload and command-record replay. Source/core/tools/catalog guards and actual
no-profile parent comparisons are saved separately. Root's real eight-cell module
tests can be run against the actual M75 runtime with new version evidence; none
of these small tests implies 4-9 complete battle, 36-stage completion or native
client frame accuracy.
