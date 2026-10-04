# M78 cast-owned attachments and C4 dmage

Immutable parent: M75
`348c5671adfd73adb501c67a3dd4c51ce4f88228e45dcc6b1026c6eb2822bd57`.
M75/M73 are unchanged. The runtime has no enemy-ID or lasso-ID branches and does
not import V1 combat code. The parent's offline level JSON fixture remains the
only copied V1 artifact. `domain/buffs.py` is unchanged so Root's M84 immunity
consumer can compose independently.

## Explicit interfaces

Define an attachment through the package's `definitions` collection with
`kind="attachment"`. The profile must explicitly declare finite held duration,
flight limit, quantum step interval, refresh interval, trajectory rule/parameters,
target buff, actor damage effect, damage-integral boolean, typed cancellation
flags, typed owned-source exceptions, forced timeout reach, invalid/hidden
policies, packet limit(null means unlimited), completion blocking, recovery buff
and its stop reasons. Unknown/malformed fields fail compilation.

Use `{"op":"begin_attachment", "attachment": profile_id}` in a real ability
with top-level `wait_for_channels=True`. It requires the actual active cast and
cannot borrow another source's identity. Ordinary source/target IDs, not virtual
actors, own the instance. Acquisition uses the ability's existing selector. The
captured target is retained with no reselect; inactive/retired targets end it.

`apply_buff` may explicitly set `bind_to_cast=True`. The resulting actual buff
instance UID/target is recorded on that cast and removed on finish/interruption
or source retirement. Target leases also belong to the specific attachment and
are removed immediately on link end or target retirement. Sharing one buff UID
across different active casts fails instead of removing someone else's lease.
No buff definition is globally erased by name.

Optional actor `damage_flags` is the exact record
`{"source_attack_type":"BUFF", "ignore_for_sp":false}`. Known source attack
types are NORMAL/SPLASH/BUFF/ADDITION/NONE. Only NORMAL may emit attack.accepted or
claim source attack-SP. Target event-SP consumes its explicit ignore switch and
the original emission-time freeze path. These flags are compiled and validated
again for direct explicit-effect calls; they are not unused parameters. Ordinary
effects lacking the new fields keep their original payload/value behavior.

Ability activation may declare typed `forbidden_source_flags`; selectors may
declare typed `exclude_abnormal_flags`. Both read effective projected states,
including half-open buffs/immunities. No-profile numeric effect phase remains
the M75 behavior; attachments do not introduce a new phase override.

## Ownership, lifetime and failure boundaries

Instances, positions, held deadline, refresh deadline, packet count, generation,
task ID/sequence/due, lease UIDs and waiting-cast references live in World. Actual
scheduler identity guards duplicate step payloads. Arrival uses the declared
replaceable projectile.trajectory contract; held damage still uses damage.pipeline
and live source/target at_hit attributes. No RNG is hidden in the manager.

For damage_integral, the profile's scale is multiplied by the actual quantized
step duration. The module uses left-endpoint quantum installments in the
half-open held interval. Target STUN is **infinite**, refreshed each second;
there is no one-second expiry gap. A deliberate cleanse can free the target
until the next refresh. On deadline, source/target retirement, cancellation or
terminal state, exact owned leases are removed in that same tick before further
packets. The source's own declared STUN0 hold is excluded from cancellation;
owned SILENCE12 is not accidentally excluded.

Completion blocking is explicitly configurable. A true live attachment delays
victory; false allows completion and immediate owned cleanup. Defeat/terminal
state cancels the link rather than blocking forever. Source-invalid retention
is not supported for cast-owned links; postmortem projectiles are a separate
M76/M85 consumer.

Begin/step/stop, owned finish/interruption/retirement and opt-in event callbacks
are atomic. Callback failure restores that boundary's World, RNG, scheduler and
full events. No completed earlier scheduler packet is retroactively erased.
The existing Session failure state prevents silent continuation. Ordered saved
checkpoints reload all controller/cast/buff state; replay identity includes the
actual changed implementation.

## Exact dmage source and declared policies

The audit `chapter04_dmage/source.reference.json` is bound to frozen C4 source
`3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603`.
Its own SHA is `bac0af413f5a2380e623c180e3c8b8c1852e2a425e4058e8c0f0ec217eb34681`.
Actual PPtr paths, EnemySkill/RangedAttack/ThreePartChannelingAnimation,
projectile components, source flags, empty BSON, animation frames, raw geometry,
DB operands and dump enum declarations are preserved there.

The module consumes HP12000/ATK500/DEF200/RES50, normal interval4/range2.5,
lasso BB duration20/scale.35/range3, finite trigger1 and priority1 with initial/CD0.
Skill postfilter12 is NOT_STUNNED_HATRED_DES; ordinary postfilter4 is HATRED_DES.
STUN0 exclusion is real enum consumption; taunt/newest-ID ordering remains an
explicit replacement for unknown native hatred comparator. Range3 comes from the
actual BB; raw collider2 remains distinct. Ground target/camouflage/target-free
projection remains the declared V2 eligibility policy.

Skill_Begin26 then Skill_Loop OnAttack0 launches a declared speed10 homing
attachment. Skill_Loop14 is not silently used as damage interval. Actual
hit_duration20 is the held-phase override; raw link5/life5 is retained as source
fallback and a flight limit. Native forceReachedWhenTimeup1 is separately
consumed. Normal magic projectile uses its actual life10, speed10 and f30.

The [PRTS reference](https://prts.wiki/w/%E8%90%A8%E5%8D%A1%E5%85%B9%E6%9C%AF%E5%B8%88)
describes repeated permanent stun and35%ATK arts damage over a bounded20-second
link. It is secondary behavior evidence, not recovered method bodies. The module
integrates500*.35 per second using actual quantum packets and refreshes STUN
each1second. Native LinkProjectile/MeleeModifierSplitter/Harpoon/BB loading
bodies and exact client packet timing remain pending. Float sums retain their
actual values; no rounding is added to make the3500 integral artificially exact.

Caster active STUN0/templateempty is a cast-owned hold. Native source flags
ignoreSilence0/isSilenceable1 and immuneStunWhenAffecting0 map to explicit typed
source cancellation and activation policies. The skill uses a dedicated one-use
counter, not fake SP cost; quota is consumed at accepted cast start even when
later interrupted. Cleanup restores movement/normal attack after the declared
recovery: raw minimum0.6669999957 seconds quantizes to21ticks, distinct from
authored Skill_End20frames.

SourceAttackType4 is BUFF. The source contains no serialized ignoreForSp for
this node; the module's false victim-SP value is explicitly a reference policy,
not a claimed raw flag. Both switch values are independently exercised. M84
immunity applicability composition remains Root's next cross-module validation;
this standalone source branch does not claim that integration already passed.

Audit/module builders support real byte `--check`. Author fixtures and source/
core/tool/catalog guards are saved under `validation/campaign/m78_attachments`.
The small source/controller tests are not 4-9's complete49-spawn battle,36-stage
completion or client-verified behavior. The initial module life5 fallback and
partial build anchors were corrected during WIP before acceptance; no frozen
source or prior accepted report was relabeled.
