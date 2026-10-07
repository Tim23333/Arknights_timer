# Independent frozen chain review

`verify.py` targets only candidate core
`09c265c4a5f8d849f20d08a0e073db558d8d6a727f1060f3ad2a63cec2e1f7c6`.
It checks all 96 paused source hashes, the five frozen source deltas and the
author tool hashes before its runs. It does not invoke author tests or assertions.
The sole author interface consumed is the expressly exported
`native_module.build_fragment()` source fragment; its internal implementation is
not copied. Entities, receivers, scene, public controls and numerical oracles are
owned by this peer.

The peer scene uses 880 attack, 20 resistance, 20000 health/element capacity,
a different map and 1.2-tile spacing. The first cast is public/manual, launches
at tick 8, and has a duration shorter than the projectile chain. Public buffs
change attack and target resistance after launch. Public controls alter the next
target's current position, target-free eligibility or life, kill a target during
flight, and withdraw the source under retain/cancel policies. The retained-source
oracle checks the cast/launch source snapshot fallback, not the live buffed attack.

All positive scenarios use a real written checkpoint reopened from disk, a
restored continuation and a replay from public inputs. Exported bytes are
validated against the owned journal by the generic streaming observation helper.
The full snapshot, ordered event digest, event count and full continuation state
(world, scheduler, RNG and runtime identity) must all match. Checkpoints include
active step and pending-next boundaries; a result does not rely only on final HP.

Hostile calls must actually raise ValueError from the owned callback/impact path,
and the complete checkpoint must remain equal after rejection. Twelve independently
changed checkpoint fields are rejected, covering position, multiplier, history,
source snapshot, packet, cast, task issuance and scheduler ownership.

Run through `tools/run_with_log_cleanup.py` with a fresh
`E:/ArkSimLogs/runs/chapter10_chain_peer_v1_*` directory. The compact result is
`validation/campaign/chapter10_chain_peer_v1/result.v1.json`; launcher/cleanup
receipts are retained under `E:/ArkSimLogs/receipts/<run-name>/`. Raw journals and
checkpoint files are removed after validation, so their recorded hashes are
evidence of executed comparisons rather than reusable recovery material.

Scope covers finite chained projectile and the sourced RangedAttack fragment.
EmptyAbility, behavior selection, movement/deathrattle assembly, complete enemy,
complete stage, client verification and the interrupted full suite remain outside
this gate. The primary simulator is read only. This peer does not grant formal
promotion or modify the production baseline.
