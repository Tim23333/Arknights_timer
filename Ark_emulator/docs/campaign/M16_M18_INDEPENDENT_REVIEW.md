# Independent M16/M18 source and consumer review

This review changes no frozen candidate or package. M16 scope is669982006a81507973d8f3c3abb1f694d7ee9831de67ad2de1c0b3ea441df571; M18 scope is283ed55d0aaab3b9d6aaeb4806209182b5b6bb746882d52403ba9ef124a3d999. The revised boundary check separately uses M21 initial079da0f04c6f190e5521d2ee876341fcd75a440b48132e745e39d058f26deb69. Tools assert actual imported path and/or core start/end identity and save full input fixtures; no complete-stage/model receipt is issued.

## Actual blocking counterexample and correction

`tile_rule_boundary.py` independently authors a custom pure terrain.tile_options provider returning an unknown tileKey, active blackboard and active effects over a base with those field names. Old M16 and M18 compile/create successfully and report the unsupported fields as effective tile data. M18 also permits an entry tile identity to become an exit through that provider. The strict compile-time tile profile guard is therefore bypassed at the dynamic getter. The old numeric partial output also drops base identity fields rather than preserving them.

Original failures remain `m16_original_boundary_failure.json` and `m18_original_boundary_failure.json`. M16's portal replacement case rejects only because that earlier core lacks portal support; this is not proof its custom getter protects portal identity. No old failed report is reclassified as passed.

Root's new M21 restricts changed fields to supported six PATCH fields plus derived groundPassable/movementCost. Other base identity/blackboard/effects/metadata inherit when omitted and must be equal when supplied. The identical independent cases now pass their strict expectations: unknown behaviors reject, legitimate numeric partial yields cost7/height.75 with unchanged base identity, and portal identity replacement rejects. `m21_revised_boundary.json` proves this boundary only, not all M21 behavior or promotion.

This policy is appropriate for the current scope: numeric custom rules remain free while behavior dispatch stays with declared map profiles. A future intentional tile identity/behavior change needs an explicit supported mechanic and validation, rather than treating a custom tile-options result as a silent floor.

## Independent raw source reads

`audit_raw_sources.py` loads actual EMP token CAB and verifies complete TrapMode and MapDependentTrap typetrees against the frozen reference. Overlay values exactly map buildable0, physicalHeight.4000000059604645 and obstacleLikeMoveCost; keep pass/heightType/advanced flags preserve the original fields, not the raw unconsumed pass2. occupiedCnt0, withdrawable1 and advanced required mask1 are checked.

It separately loads the actual tile CAB, reads both portal GameObjects and every stored component. The plain Tile class does not prove teleport method bodies. Both generic profiles use actual entry/exit associations. There are27 total used SPAWN routes in1-12; eight of those contain nine portal pairs. The audit's used_spawn_route_indices inventory includes all27 and is not mislabeled as eight total routes. Raw report is `raw_sources.json`. Native TrapMode merge/weight/3D physics and Tile/Enemy dispatch bodies remain unknown.

## Dynamic paths, restore and pure getters

`dynamic_paths.py` builds an independent owner+walker scene and a custom time6 terrain rule. The initially closed cell holds the real WALK actor at0 through tick5. At session time6, repeated pure getter reads see the open tile without changing the checkpoint. Restoring that checkpoint yields the same getter. Phase0 observes the new output, invalidates route cache/wait revision and walker reaches.3 after ticks6/7/8. Revision becomes2. Actual World/events and complete command replay/checkpoint results equal. This tests real dynamic rule consumption rather than inspecting the builder's claimed fields.

A separate actual API negative call rejects system/battle as a terrain owner and preserves the complete checkpoint. It is an API permission/rollback observation, not a command replay fixture.

## Portal consumers

`portal_consumers.py` independently authors source-map route excerpts for native3/35/40-second portal waits. Actual entry/exit positions come from source association and original map, with a synthetic zero-speed actor only to isolate the transition. All three hide at0, appear at90/1050/1200, retain actual World capture and record zero teleport distance. Pure getter checks do not mutate state. CP from hidden state, resumed execution and recorded-command replay match. These are excerpts; they do not establish full original route combat or native enemy skills.

The fourth scenario uses a real owner skill command to change the captured entry's numeric terrain during hiding. A custom transition rule actually reads captured pass3/tick0 and current effective pass1. Terrain revision preserves portal capture, restore preserves it, actor appears at the authored exit and teleport distance remains0. CP/replay pass. M18 candidate is unchanged; the dynamic behavior-field bug above remains a blocker for its original strict boundary.

Reports and tools live in `validation/campaign/m16_m18_peer` and `tools/experiments/m16_m18_peer`. No author fixture/assertion function is reused for these consumer tests. Declared model priorities, weighted costs and portal semantics are mathematical profiles; this review neither certifies native bodies nor signs a stage receipt.
