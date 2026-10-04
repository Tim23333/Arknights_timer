# Frozen shared actor witness scope

This is applicability review for source content `0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4` and two targets: M14 `83bfa1829958f80a4f1da95740466326db3f5a8c7143737d728887b3670116d2`, and 0-11 `0c8736089ebd08b1768499c4e043486275c2ccdbbb08f4fa6c4007590f55a149`. Actual imported runtime is the frozen `unpack_work/campaign_m12_projection_candidate/ark_sim` with implementation `bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11`. Original source reports and input identities remain untouched; no model receipt is issued.

## Structural and metadata review

`review_shared_scope.py` reviews the existing proposal's boundary capture/evaluation implementation and uses it to stop the actual original helper at `make`. A sentinel stops construction before battle, never returns a fake Simulation. The compiled programs, every actual reachable definition, rule runtime fingerprint, provider descriptors, effective scene inputs, explicit helper seed, initial World, events and RNG are compared. Scenario metadata and compiler/catalog program metadata are distinct. The recorded full scenarios preserve identity differences rather than renaming their fingerprints.

In frozen runtime source, `RuntimeContext.calc` only supplies scenario rule bindings to rule selection; its calculation context contains time and actor views, not scenario metadata. Domain scenario reads use rules, map, resources, parameters, objectives, initial entities or timeline. API `Engine.create` uses an explicit seed when supplied; every original make forwards that seed, including default11. Helpers' metadata reads are actual actor config/source assertions or report exports, not scene metadata as mathematics. Actor metadata is part of the compared actual definition identities. Provider and rule descriptor/implementation fingerprints are equal. The report stores source access rows and hashes. This bounded dataflow review does not assume all metadata everywhere is inert.

`export_shared_scope.py` additionally inspects each structural case's reachable Python constructor call graph. Each of the 77 structural cases has one reachable make load site in reviewed locked functions; the five known multiple constructors are not certified by their first capture. Future helper/core/rule/provider/definition changes invalidate these locks and applicability. No future arbitrary provider is presumed to ignore metadata.

## Five genuine multi-fixture cases

The first-capture proposal had insufficient all-fixture coverage for Bagpipe deck/refund, Night failed DP/position, bird death/owner retirement, taunt filter/retirement, and Weedy near/far SP. Those reasons remain recorded as the reason extra evidence was necessary; they are not erased by setting a boolean.

All five original functions now run genuinely against source0fb, M14 and 0-11. Original make is wrapped only to record its real inputs and return its genuine Simulation. Each function constructs two fixtures: 30 total across three bundles. Each original assertion completes, and every returned fixture has genuine helper checkpoint/resume and command replay equality. Each source/target make pair independently compares explicit seed, effective scenario, all reachable definition identities, rule/provider fingerprints, initial World and RNG. Actual fixture/program/runtime identities and original assertion results are saved in separate `shared_actor_{target}_{case}.json` artifacts. New source runs use separate `shared_actor_source0fb_*.json` names and do not replace old witnesses.

No claim is made that raw events are byte-equal across source and target program identities; traces can carry different runtime fingerprints. Checkpoint/replay equality is per genuine fixture and program.

## Four static source assertions

Trio/Night/Weedy/Kalts configuration assertions execute against both packages and return without make. They are explicitly `static_source_definition_equivalence`, not battle fixtures: no_runtime_fixture true and target_case_executed false. Their returned assertions and actual compiled twelve-actor reachable closure identities are equal. They are not assigned fictitious all_fixtures or replay flags.

## Scoped bindings and actual gate checks

Each target has 86 exact source-evidence/case/helper bindings, with frozen per-case proof artifacts under `validation/campaign/shared_scope_proofs`. The Lisk defense helper exposes `probe`; its source witness names the test node. The exporter independently reads that test AST and verifies its actual `probe()` call before creating the explicit node-bound proof. Duplicate config_source names retain distinct helper identity.

The gate-facing reviews are `shared_actor_scope_m14_gate_review.json` and `shared_actor_scope_00_11_gate_review.json`. Scope is specific helper/case/source artifact applicability; neither native target enemies nor stage timeline/controls are shared. Those dependencies require separate target source and whole-stage evidence.

`verify_shared_gate.py` genuinely calls the revised shared gate for all172 bindings. Sixteen negative calls across both subjects reject wrong target, wrong helper, missing approved receipt scope, first-fixture-only proof, unequal reachable definitions, missing metadata review, changed source artifact and static fake execution. The result is frozen in `shared_actor_scope_gate_peer.json`. It verifies the gate boundary, not a full model receipt.
