# M17 generic projectile/attachment candidate

Candidate `D:/Arknights/Arknights_timer/unpack_work/campaign_m17_projectile_candidate/ark_sim` is frozen at `b964bef82bbc9f6a05cad76740e81030dc9b3d72e82641c3b809d65fb2df875e`, copied from M15 category f98a638812a18a01d10505dadd48b01de410ac27e992230881bc01c4f9a993b9. Primary and every prior candidate, W package, source helper and shared Spine reader remain unchanged. Patch/change identities are under `validation/campaign/m17_projectiles/`.

The source audit tool actually loads native CABs and re-reads four projectile components, their external MonoScript PPtrs/classes and four RangedAttack components. Stored source identities and complete typetrees match. The design/source constraints are in `CHAPTER01_PROJECTILE_FEATURE_DESIGN.md`; native method bodies are absent. No official ID branches exist in candidate domains or providers.

## Generic interfaces

New projectile definition collection is opt-in through exact effect.projectile_definition on damage/heal/area. Schema/kind checks reject wrong references and missing/invalid lifecycle policies. Capability checks require exact projectile.trajectory and projectile.collision contracts; these already existed in the catalog, so no default catalog or binding was extended. No-definition content follows the original path.

Motion/collision numerics are replaceable pure providers/rules. The supplied trajectory supports planar homing, fixed attachment and live-follow attachment, with explicit visual parabola and small mathematical arrival tolerance. Height is a model visual coordinate; no native 3D body/collision accuracy is claimed. Default relative swept trace-point collision uses captured target identity. Other actors require explicit collision.allow_other_targets; a custom policy then resolves genuine canonical actor references. Custom terrain-stop and duplicate-hit policies are independently exercised.

World stores source/trace/attachment IDs, actual positions/last target, opaque motion-state, source/target launch snapshots, cast group, hit memory/count and owned jobs. Source/target hidden and invalid policies are explicit. Normal cancels invalid/hidden targets; C4 retains its fixed/last point. Area callbacks use explicit center_position geometry and select living visible members at settlement. They never create fabricated battle/source coordinates. Source retirement normally retains launched objects, separately from interrupted source casts.

Expiry precedes same-tick owned motion at effect phase; force-reach/end-hit/invalidate/completion ordering is explicit model policy. Max-hit and identity memory prevent duplicates. Nested on-invalid projectiles increase the still-active cast pending counter before the parent releases its count. Every terminal path removes only its owned jobs, marks the instance once and releases pending once. Compact finished identity records omit recursive cast snapshots.

Attack recovery claim pruning includes active projectile cast groups. A late old packet after a newer attack therefore cannot reclaim another SP. This is a generic fix for newly persistent objects; old no-definition calls skip the new path.

## W content mapping and scope

New content is `packages/campaign/chapter01_models/projectile_lifecycle/`:

- model.json: two_full_packets_model, fixed attachment; SHA8d416e8c72e1b3524f5bd6201b6216b42a5d14d9bba4129433c73b9ed58f2c44.
- follow.model.json: same signals with explicit follow replacement; SHA8ec2438806ab294d659e702cc46ba7da10630f27eedbb067b63bc51897e0a25a.
- first_signal.model.json: first-signal alternative; SHAd4238bfdbe3233563b9b4558b80193519cd3c3a97b0f16b64f0847eaf08a865e.

Keep old unit/chapter01_w, HP modes, normal0/1 and C4_0/1 IDs as a whole module. Both normal effects use projectile/chapter01_w/normal; C4 effects use projectile/chapter01_w/c4. Replace the old W module rather than appending another normal attack. Old projectile_speed is removed for opt-in attacks. C4 now launches after authored-frame .6 seconds, owns a real3.2-second attachment and waits for invalidation; it does not merely schedule area after3.8. Pending count closes on actual invalid callback.

Normal signals9/23 each yield a packet only under the explicit two-full mathematical profile. The native signals do not prove two full native packets. Source speed5/lifetime10/maxHit1 are used. Fixed C4 is justified as a declared model using false follow/update flags; native parent-transform attachment might still follow and remains pending. Native source flags, callback names, float32 values and old source provenance are preserved. C4 radius2.5 is an explicit area interpretation of DB range_radius, not a proven native blast shape. Native curve, mount/parent transform, target inheritance, packet count, callback timing and FSM remain client pending/fullBoss gaps.

## Actual validation

Fresh `test_lifecycle.py` completed27 passed,0failed,92.60seconds on this frozen candidate. Tests include both phases/frame15+29/370 damage, moving target command→21+35 impacts, fixed/follow center and health differences, source/target retirement and actual HP0 deaths, route-hidden captured target rejection, expiry end-hit/quota, exact three-object wait, nested completion117, late old packet323 preserving SP2, replacement terrain collision, explicit other-actor permission, duplicate collision quota and strict content negatives.

The callback fault test instruments the real handler boundary with Session.snapshot (not an illegal in-handler checkpoint), executes primary damage/RNG/DP effects then a genuine division-by-zero recovery rule. World/HP/resources, RNG, events, scheduler and instance state restore exactly to that boundary; kernel stores failure and refuses further advance. Failure diagnostics/task-pop are not described as a resumable whole checkpoint.

Three actual probes in `probes.json` export input fixtures, recorded commands, relevant events and World instance state with genuine CP/resume and replay equality. Public move/withdraw/skill/damage or declared route movement drives positions; no hand-written ctx position stands in for replay.

Old no-definition W40tick/seed17 is independently run on f98 and candidate. Program/rule fingerprints, World, all pending tasks, RNG and all2080events are exactly equal. API core identities differ as expected. This is bounded compatibility evidence, not all old stages automatically passed.

Builder generate and --check passed. All three packages compile as real62-definition fixtures. No entire chapter stage was executed, no complete Boss/client accuracy claim or model receipt is issued. Root/peer will independently review this candidate and merge into a new identity alongside terrain/portal/dormant changes.
