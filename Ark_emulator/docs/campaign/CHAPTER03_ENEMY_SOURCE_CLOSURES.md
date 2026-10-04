# Chapter 3 exact enemy source closures

The new offline generator `tools/build_chapter03_enemy_sources.py` built and checked `packages/campaign/chapter03_sources/native.reference.json`, SHA256 `d6a1d5294e1419d6ee41022efa1ef93a0ad44b6effb80c4bdfcf7fc3e7cd1e35`. It follows the frozen chapter3 plan, resolves13 exact prefabs and13 DB/level/override variants, freezes four projectile closures, and locks19 source identities. Shared Spine parser/library identities are identical before/after. No runtime/model or stage was created.

Every mode follows the actual local root `_modes` PPtr into mode `_combat`, `_attack` and `_attackTrigger`; null and external pointers remain distinguishable. Serialized combat/selector fields, active/passive Buffs, checker fields, geometry, MonoScripts, referenced BSON and exact animation bindings are retained. Shared skeleton name differences are resolved by actual serialized pointer chains, with the earlier strict-name rejection recorded rather than a guessed name fallback.

| Exact prefab | HP / ATK from selected DB | Combat / normal authored OnAttack frames | Additional source dependency |
|---|---:|---|---|
| gopro2 |1700 /260|Melee physical18|rebind source variant |
| gopro3 |3000 /370|Melee physical18|new exact source stronger variant |
| lurker |2200 /300|Melee physical12|toggle INVISIBLE9/checker3s |
| jshoot |1800 /260|melee/ranged physical16|toggle INVISIBLE9; crossbow_big speed10/life5 |
| jmage |2200 /350|melee/ranged arts19|toggle INVISIBLE9; magic_ball speed10/life10 |
| mortar |3300 /400|ranged physical16|mortar Paracurve speed4/life10/HitBehaviour |
| shield2 |10000 /600|Melee physical14|source variant/body attributes |
| handax |8000 /750|Melee physical28|exact raw source shared with chapter2 |
| handax2 |12000 /850|Melee physical28|actual stronger prefab/DB variant |
| katar |4000 /450|Melee physical17|new ordinary source |
| rogue2 |3000 /450|MultiMelee physical12,23|packet/repeat profile must stay explicit |
| Skullshatterer level1 |30000 /1300|melee53; ranged14,17|two source modes, HP ratio BB, attachment; skulsr speed5/life10 |
| yokai level1 |1870 /0|EmptyAnimatedAbility; no attack signal|flight, no fake attack;1450 undefined override inactive |

Jshoot and jmage are not just ordinary ranged actors: their exact passive Buffs contain INVISIBLE9 and their checkers have restoreDelay3. They need the same generic visibility/toggle consumer as lurker, with their own source clocks, damage types, stats and packet fields. Source null combat selectors/INPUT_TARGET2 and same-GO triggers are retained for binding work. They must not inherit lurker's frame12 or stats.

Mortar and Skullshatterer source projectile closures retain SimpleProjectile, ParacurveMovement, HitBehaviour and raw collision/expiry/quota flags. Crossbow/magic ball retain SimpleProjectile plus AdvancedMovement. Their motion/hit policies are not authored by this source extraction. Inactive maxHitNum and actual hit type remain separate; a field value alone does not imply finite quota.

Yokai, handax and Skullshatterer exact raw component sets and asset hashes match prior chapter2 closures and carry an explicit reference to that frozen package SHA. Their selected DB level/override values are still independently rebound. In particular Skullshatterer level1 must not copy HP10500/ATK1000 or threshold5250 from the earlier reference50 level0 model; source HP30000 makes a declared50% threshold15000. Historical serialized checker/table mismatch remains in raw fields and is a feedback item, not erased.

The crate category correction is separately important for the forthcoming actor composition: current dump EntityCategory DEFAULT1/TRAP_OR_ITEM2/OBSTACLE4 and Token `_category` typedEntityCategory bind the raw crate4 to OBSTACLE. Enemy ordinary category1 selectors cannot be assumed to attack it as a player character or item. A source-bound obstacle contact/attack consumer is required. This source inventory does not change crate category to make an existing selector work.

The output is exact offline dependency material with stated gaps, not executable completeness, client verification or an approval receipt. The next content authors can use these real frame/source records with explicit reference-based math policies and separate user-feedback items.
