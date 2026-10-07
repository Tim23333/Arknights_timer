# Parent-da interruption sequence read-only findings

Parent `campaign_owned_channel_phase_v2_candidate` first settles actual health
loss through `ResourceSystem`, then `Lifecycle._retire` increments death_generation
and writes alive/active false and state=dead. It then calls `abilities.interrupt`.

Parent interrupt cancels tasks/removes selected cast records, cancels attachments,
releases cast-owned Buff instances and emits ability.interrupted. Afterwards
Lifecycle reconciles Buffs and emits entity.died. Ordinary Buff.notify removes
unavailable holders and does not grant dead-owner effect authority. This ordering
explains why an interrupt subscriber can disappear before the event or be ignored
as unavailable. It is not evidence of a repaired callback primitive.

The proposed declaration targets an actually possessed active cast and snapshots
its eligible Buff subscriptions before cast teardown. The event-time source view
is already the real corpse (HP0, dead generation incremented), not the old alive
view. Only a private finite synchronous scope may authorize declared nonhealth
resource effects. Declaration allow_owner_inactive cannot revive removed/expired/
disabled Buff eligibility or become ordinary dead cast permission.

The prepared selector distinction uses the actual cast targeting A at tick1,
publicly withdrawing A at tick5, and killing caster by public true damage at7.
`selector_timing=live_at_event` must debit the still-live B, not revive A or borrow
the old cast targets. Both resources have distinct starting values to make this
observable. Source stats are synthetic generic data; no dmech/client acceptance
is claimed. All actual execution waits for the exact final new freeze.
