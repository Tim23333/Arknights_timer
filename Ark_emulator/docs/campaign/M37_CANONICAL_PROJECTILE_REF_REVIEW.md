# Independent M37 canonical projectile reference review

Reviewed frozen candidate is `D:/Arknights/Arknights_timer/unpack_work/campaign_m37_projectile_refs_candidate`, corec77ce7a46101cf903fd9c6c56dcabddf5775008d091365cd7486ddeb47b8d740. The source delta relative to frozen M30517290 is verified exactly one line: world.resolve(target) immediately after default trace-target fallback and before quota, target-history or call-stack reservations. No author core, package, helper or test was changed.

Nine fresh independent cases passed1.13s; verification report validation/campaign/m37_peer/final_review.json SHAb0b69c7daf454b5a38df8638a42fd52cb8083b7c577038c145391775cff1704c locks actual import and source/core before/after. Own provider/fixture composition uses previously frozen generic quota fixture data, not the author's alias expectations.

Three alias/int orders show a same-runtime-target nested dispatch is rejected while its first dispatch is in flight when can_hit_same_target:false. The stored history contains only the canonical integer and later alias repeat is also rejected. Missing alias, negative ID and bool are rejected before any quota/world/RNG/task/event change. None is intentionally the documented default trace-target fallback, not an invalid reference. With can_hit_same_target:true and finite2, alias then integer legitimately dispatches twice, stops at2 and does not leave private reservations.

These direct _hit/reentrancy cases are explicitly API instrumentation, not claimed as public-command replay. A separate ordinary public fire command tests reach first hit, waiting completion, actual checkpoint continuation and full command replay under the same current core. Native collision/contact/callback semantics remain separately pending and are not inferred from the alias correction.

No new defect was found in these bounded cases. Canonical runtime identity is the shared basis for quota/history, while semantic policy remains content-declared. This is source/math/API correctness review, not whole-stage or actual-client approval. Model advancement continues using reference data/profiles; user will later supply unified real-game feedback.
