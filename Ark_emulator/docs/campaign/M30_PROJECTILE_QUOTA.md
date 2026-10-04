# M30 unified projectile quota and immediate finish

Frozen new candidate is `D:/Arknights/Arknights_timer/unpack_work/campaign_m30_projectile_quota_candidate`, implementation517290e56f59bdf5f57862dbadb8929b37cf6fbe0468116dcb39669df6357b51. It copies frozen M28cb0e7a97a2621aaf4b14dc942181686906733acbcc61f6a5a23ebae9448e997b and changes only domains/projectiles.py. Primary, cb0e, M29,75fd and all live source/input/report artifacts remain unchanged. This is a general mathematical quota/lifecycle correction, not a native projectile callback claim.

## Original actual counterexample

The strict independent original fixture has max_hits:null, stop_after_first:true, hit_on_reach:true and finish_on_reach:false. Atstep1 the collision profile returns no contacts but motion reports reached, so reach fallback dispatches40toA. Oldcb0e does not finish in that path; atstep2 collision dispatches40toB, and only then its collision-loop stop check finishes. Actual packets[(1,40),(2,40)]/HPa160,b160 contradict the declared first-valid-dispatch policy: only[(1,40)]/HPa160,b200 and waiting cast completed1. The source fixture, initial HP, commands, actual all relevant events/core/module and unchanged expectation are in validation/campaign/m28_peer/reach_first_original_cb0e_failure.json SHA2f4e6f4f6b366dcdfcd1d1d1a76b47427fc499ace0910fc57fdf6d18156d57f7. The strict original peer test remains failing under frozen cb0e; it was not weakened or used as a pass receipt.

## Generic correction and explicit policy

_hit now enforces total finite quota and first-hit quota at a single entry, independent of collision/reach/expiry caller. Valid target dispatch reserves a private call-stack slot before entering the effect. This is not persisted in World and does not change packet source snapshots or public counts before the effect. Finally removes each reservation even on callback/rule failure. Same-projectile nested dispatch is allowed only if remaining finite/first slots and per-target policy permit; different IDs are independent. Unlimited/no-first allows further dispatch, while no-repeat still excludes previously or currently reserved targets.

After the actual effect returns, the current registry record is read again. Count/target history merges with nested hits, and an already invalid record is retained rather than reconstructing an old active local object. It keeps the invalid reason and stripped cast/effect fields. Missing records are never recreated. A quota-ending successful dispatch finishes immediately, cancels scoped jobs, runs invalid callbacks and releases the waiting cast. step/expire callers return once invalid and cannot re-put/reschedule an old local record. Existing deadline expiration reason and explicit collision stop/terrain priority are preserved.

Quota counts valid effect dispatch, not positive damage amount or accepted damage after dodge/after-hooks. An area effect may validly dispatch at a retained position even if the trace actor is dead, as separately declared by that projectile policy. These are explicit model semantics; native contact/effect/callback ordering is still pending. No official IDs or guessed native body were added.

## Executed verification

Final fresh60tests pass:17newM30 cases,14original M28 and29existing ability tests. Report validation/campaign/m30_quota/candidate_final.json SHAc4e83c85b3b0cd7c9814de7ad365679f0f543e3002f23dbe652d8e7f7bdb91cc locks source/core start/end. Patch SHAda8adf43b6f69b3eea5c3115e4115a24f0d587d9b2a7e8c51fa1ff50e57edadb. Only projectiles.py differs.

Coverage includes original reach failure fixed for null/finite2/finite1; first dispatch at zero lifetime with expired reason; unlimited repeated collision/reach/expiry contacts; no-repeat target policy; invalid primary reach target not consuming quota before valid B; retained/cancelled source retirement driven by public director command; actual oninvalid RNG/HP/rule failure with complete checkpoint restoration and empty private reservations; valid callback launching a second projectile/ability ID with correct two waiting-cast releases; and real target HP0 death through lifecycle policy.

Actual private API reentrancy instrumentation proves sameID remaining cap2 permits a nested hit and merges public count2, while cap1/first forbids the second dispatch. Reentrant finish during the damage packet cannot reinsert active state, old cast/effect snapshots or jobs and produces exactly one invalid/finish. Those instrumentation cases are API-bound, not mislabeled as public-command replay. Three ordinary complete public-command inputs are separately saved with actual program/runtime/commands/checkpoint and strict full checkpoint/commands replay equality.

Two initial added fixtures failed because the test used unsupported non_blocking instead of documented blocks_attacks:false and omitted the target's lifecycle policy. Their original test bytes are retained. Fixtures now use real generic contracts; packet/time/quota expectations and core were not changed to bypass those mistakes.

The old finite1 collision fixture remains112events and full snapshot equal between cb0e/M30, with CP/replay in both. Its pre-existing comparison helper removes only runtime_fingerprint/rule_fingerprint fields and records them separately; this bounded finite path does not imply old reach/fallback semantics were already correct. New changed paths have the strict new first-hit expectations above.

## Delivery boundaries

M30 catalog/preset remain identical to frozen M28. Root must merge into a new storage candidate and establish a new implementation/content identity for future baseline, fullsuite and complete-stage replay; the existing M29 run is not labeled fixed by this candidate. Original source classes/INFINITY field/phase conflicts and native method-body gaps remain as originally recorded. Latest user requires game-accurate intermediate values through full process; a mathematical lifecycle correction plus exact source fields does not become a client accuracy receipt.
