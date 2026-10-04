# M46 area membership independent review

This review imports `../unpack_work/campaign_m46_area_members_candidate/ark_sim` directly, frozen core `c4c02d6dd11b457f30d1ccd75ac2175bde332e149c20828a62481ab3a2115000`. No author source, test, helper, model or historical candidate was edited. Own fixtures are in `tools/experiments/m46_peer/test_area.py`; actual compile inputs and source locks are stored beside the final evidence.

The pre-freeze read found two consumer problems. Direct `rules.evaluate` discarded the membership trace and omitted normal source/target context. Also, a globally allowed membership_rule on non-area effects could be declared but unused. The frozen author version uses `ctx.calc` only for opted-in area dispatch, explicitly includes source/target/owner, ability/effect binding scope and immutable ability/effect records, and rejects the new field on non-area operations. Those changes were made by the author before this execution, not by the peer.

Eighteen independent cases passed in2.74 seconds with core and catalog bytes unchanged before/after. The actual input uses a synthetic ATK37 actor and HP1000 targets, not an author fixture or an official-unit approximation. The cases establish:

- Source, target, owner, ability and effect are actually read by replacement expressions, and exactly one observable area.members calculation contains the chosen rule/source and actual result.
- A replacement rule can choose a different geometry and order, with two distinct actual candidate IDs consumed in that returned order.
- Projected half-up cell offsets include the flying diagonal4.49 corner while excluding4.5; this differs deliberately from the old continuous radius. Primary-target selection and splash membership remain separate.
- Map-edge negative half margins are projected without clamping multiple cells or repeating packets. Duplicate offsets produce a single target packet.
- Duplicate results, aliases, Boolean values, undeclared/out-of-candidate integer IDs, wrong contracts and non-area declarations reject. Output rejection restores the full pre-call checkpoint.
- A late explicit failing damage rule restores earlier actual damage, RNG consumption and membership trace events in one area transaction. Member death increments the enemy-death counter once and does not duplicate other target packets.
- A public scheduled area continues from its legitimate retired source record, retaining its actual source ID. This is current declared source-retention behavior, not a universal native callback claim.
- The old radius branch adds no area.members calculation and retains continuous geometry.
- Public grid and custom-context scenarios have actual input/commands, ordered disk checkpoints, resumed snapshots and complete command replay equality.

Initial independent fixture errors remain in `initial.log` and `fresh.log`: an unclosed list during collection, and a failure pipeline initially attached to a target definition although damage.pipeline is source-owned. The corrected failure is explicitly invoked late through a conditional on_success effect. Neither initial result is presented as an author core failure.

Final report: `validation/campaign/m46_peer/final_review.json`, SHA256 `81fd6cad3ceffe9db7172c38c7bc18576d2e6b7872f0be318e71ad1aeb5dbf23`. It includes all candidate Python/catalog locks, own input fixtures, author source-model identities, two complete public witnesses, and observed calculation events.

The source-backed Skullshatterer wrapper remains the author's separate `reference50` package. Its literal field/frame/threshold declarations and preserved historical40% conflict were read; this generic review does not falsely relabel its author boss fixtures as independent peer execution. The nine-cell point model, projection precision, native callback/packet interpretation and source-retention behavior remain user-feedback items. This is a passed declared-model/API review, not a whole-stage receipt or client verification.
