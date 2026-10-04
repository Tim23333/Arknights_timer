# Frost normal attack and ArcticBlast partial consumer

Current frozen candidate is `../unpack_work/campaign_frost_combat_v5_candidate`,
core `df98feb41687d1b560d27d24bcbc7aad8bbb2f7ace48aaa67aca5816fe95e86b`,
on unchanged M94 `cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7`.
Build reproduces five changed files: schema/capabilities, lifecycle, new generic
ability_timing, and qualified-radius provider. It does not change M94 or run helpers.

`ability.initial_cooldown_seconds` is typed finite nonnegative seconds. An entity
may explicitly declare `components.ability_timing.initial_cooldowns` overrides,
restricted to actual possessed abilities. Creation/activation validates effective
overrides and uses replaceable time.quantize into World cooldowns. This opted-in
creation path is atomic, including invalid instance overrides after allocation.
Dormant actors initialize their clocks on actual activation. Existing rebirth
reset_cooldowns explicitly restarts ArcticBlast's 8.5-second clock.

Qualified radius may explicitly set strict Bool include_primary. The captured
primary joins the radius membership as a union, is deduplicated, and still must
be a live/visible domain candidate passing the same declared source eligibility.
Absent/False preserves the radius-only behavior. No IDs or enemy names are hardcoded.

Actual source audit is `chapter04_boss/frost_combat_v1/source.audit.json`, bound
to source-plan7ad2fb46, native3e392d80 and M86trueFrost41bfb7ff. Actual raw PPtrs,
animations, BB, projectile10/speed10, splash radius2, four native immunities,
initial sleep immunity/removal, and IceShield closure are retained. The PRTS
FrostNova and Sealed Floor pages were actually browsed on 2026-10-03.

Accepted content is exclusively the new `chapter04_boss/frost_combat_v6/` modules:

- first17.bb8.reference_ground.json is the default reference choice.
- last28 and both17_28 alternatives retain the raw two OnAttack events17/28.
- first17.raw4.source_motion3.json exposes serialized buff4 seconds and raw
  projectile hit motion3 instead of reference8 seconds and ground-only hits.

First17 is not recovered native routing or proof of one normal packet. Blast's
waitForAttackEvent0/preDelay.933 is independently quantized to28; it does not use
normal event17 or accidentally fire twice. Its zero-flight source-centered
radius2 plus qualified captured primary is a reference timing profile, while
the raw .1s projectile and method-body gap remain visible in the audit. Slow
uses actual AttributeType7 ADDITION -50 converted to V2 ratio -.5, max stack1
refresh, and an always-active rule to opt into existing boundary expiry settle
(source isSilenceable0). These are ordinary unowned target debuffs.

Blast uses the existing attack replacement gate with the actual normal111tick
clock, ready initial255, then source Attack48-frame cast duration and8.5-second
cooldown after finish. In a continuously qualified scene it casts333/666, which
is an explicit reference clock policy. Interrupt retains the accepted cast's
clock; rebirth resets it. Time/duration/recovery/damage/membership/eligibility
remain rule/provider inputs, not a fixed authored cast table.

The current module implements only normal and Blast. Multiple enemy-skill
priority arbitration, IceShield2's shared-clock gate, and its cast-busy group
must be composed and verified separately. List order is not a substitute for
priority. Root's tile-target module is a separate candidate under peer review.
There is no whole4-10,43-spawn,36-stage, or client-accuracy receipt here.

Actual verification: 26 author assertions in52.94s,182 selected compatibility
assertions in83.39s, ordered disk checkpoints/public replay, byte check of audit
and four modules, fresh core rebuilding, and actual no-feature0-1/custom values
equal except six runtime fingerprints. Root additionally passed four fresh
initial-clock/dormant/unpossessed/empty-target checks on this core. WIP source
generation/compile failures and the earlier source-withdraw boost expectation
are preserved with their original reports and modules; they are not accepted
content or relabeled mechanism failures.
