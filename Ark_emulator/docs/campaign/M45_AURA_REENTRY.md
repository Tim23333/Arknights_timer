# M45 source invalidation during aura callbacks

Frozen independent candidate: `../unpack_work/campaign_m45_aura_reentry_candidate`, implementation `181eb512eaa01234775ab6ebfdb7ada7f98cb6eea998093bc31a3cb412c39670`. Parent M42 `2746020dd269241d8802551ea63cb28243755ff0105a19bb09033c448f497420` remains unchanged. Only `domains/buffs.py` changes; it includes the parent synchronous remove transaction and extends reconciliation. No source package, primary runtime, older branch or live input was modified.

## Preserved actual counterexample

An aura adds DEF5 to A and B. A's public ability moves out of the radius, so its child Buff's legal on_remove effect retires the aura's source. The next effect in that same ability damages B. A captured desired/member set still retained B's DEF5, yielding ATK100−DEF15=85 and HP15. Once the source retires, B should have bare DEF10, yielding90 and HP10. The full actual source/inputs/commands/events/core proof is `validation/campaign/m42_peer/retire_samecast_original_failure.json`, SHA256 `0834abe780a944b8c6a28be23991a2a2c446513393744743e7f8eadd255349bb`.

An earlier child-remove-parent fixture was rejected as a dependency cycle; its initial log is retained as a fixture error. A retire-source callback is legal and is the actual demonstrated runtime failure. The old report and source are not relabeled.

## Generic repair

After each child removal or application, reconciliation re-reads the current parent instance and checks its center, actual source and half-open expiry. A missing/inactive parent immediately loses its remaining owned children. Cleanup keys use the globally unique aura-parent instance ID; another parent with the same Buff definition, source overlap, or shared target remains separate.

Callbacks can also move the center or install a replacement parent. Actual external apply/remove/retire/move reconciliation requests are deferred while the pass is active, then processed before the caller returns. Owned membership is published from actual child instances before restarting, preventing duplicate independent children when an immediate callback requests another pass. A nonconverging callback graph raises at the session reaction budget and rolls back. This is a declared synchronous model policy, not a reconstructed native callback body.

Normal internal owned-child installation/removal does not itself request another pass. This avoids extra ordering/RNG decisions for a random aura. The explicit two-candidate random selection check consumes exactly one new sample per explicit pass. No no-op removal creates new events. Sources dying during a child's immediate effect are checked before a sibling can be applied.

The entire stabilization is atomic. Removal-depth, reconciling and deferred-request guards restore in finally blocks. Actual on_remove pure-rule failure after retirement/RNG mutations and actual second-pass selector provider failure after movement restore World, resources, attributes, ownership, jobs, events and RNG exactly. Repeated failure does not leave a guard that skips later evaluation. Existing started casts are not indiscriminately cancelled by membership changes; source lifecycle retains its established interruption policy.

## Evidence

Twelve independent cases passed in3.05 seconds: same-cast90 damage; another same-definition source surviving; remote source retirement while center stays alive; callback movement and range recomputation; expiry and single retirement; genuine rule/provider failures with full rollback; source invalidation during immediate child effects; replacement parent; bounded callback loop; random sampling budget; and public ordered-disk checkpoint/command replay.

The existing aura/Buff controls/domain selections plus six author remove cases passed83 in the frozen candidate. Eleven existing source-backed defdrn cases passed7.16 seconds. These94 cases are compatibility checks, separate from the12 independent cases. Copies alter only runtime-path harness selection; original author files and expectations remain unchanged.

The ordinary stable and random aura witnesses preserve their full snapshots, ordered checkpoint partitions, World/RNG/tasks and every event value against M42. Program fingerprints are equal. Only runtime_fingerprint fields differ and are explicitly excluded; no battle numerical value is removed. This bounded pair is not whole-stage cross-version equivalence.

Two new public same-cast retire/move scenarios store actual input, commands, ordered checkpoints, replay and final snapshot. Each yields B HP10 and exact checkpoint/command replay equality. Final source guards lock implementation before/after and every actual compile fixture, including explicit ruleset options for the budget test.

Final review: `validation/campaign/m45_aura_reentry/candidate_final.json`, SHA256 `561e8288721ac88bd3b25565ad538e7097f9f4e9185322b39f88d5857826640e`. Patch SHA256 `673fd943ba322bbb8929d8bfc4cff2b9ac2e8c86d61220dd9a1458cf6a50bc2f`. Ordinary comparison captures and compatibility logs are beside it. Native timing/body feedback is still separate. No full stage, promotion, conversion receipt, commit or push was performed.
