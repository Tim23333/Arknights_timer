# M93 World-wide cast-owned Buff leases

Frozen parent M78 core:
`27d8ba218d90e6880a4f8704418871a517e5a6f30f034a79db8b04ca46a0cf74`.
M93 core:
`4e5b8d8433dd860efa57ee031e07d42e99d8799b39d78499715ba71fb12d7020`.

This author revision changes only `domains/abilities.py`,
`domains/attachments.py`, and `domains/effects.py`. It has no enemy-ID, Buff-ID,
or cast-ID special cases and does not change the frozen M78 catalog or the
DMAGE `90e091ba` parent module. DMAGE's SourceCombat input-target correction is
the separate M92 module, not this generic lease revision.

`bind_buff(source, cast_id, target, instance)` requires a real, half-open live
Buff instance and the source's active cast. It scans all World entities' actual
runtime casts. Only repeated binding by that same source and same cast is
idempotent. Any other cast on the same or another source holding the exact
`(target, instance UID)` lease causes an explicit ValueError.

`apply_cast_buff` performs normal expired-Buff pruning, real application or
refresh, and lease binding in one Session atomic boundary. Attachment refresh
and explicit `bind_to_cast` effects both use this helper. Rejected sharing
therefore restores source, generation, modifiers, controls, RNG, tasks and
full events, including effects performed by the attempted Buff application.

Cancellation and source retirement use the existing cast teardown and exact
owned UID release. A canceled cast no longer appears in runtime casts and
cannot retain a lock. Normally pruned expired Buff UIDs are not reused: a stale
lease row may remain on a still-running cast but cannot match the new instance
UID. This revision uses the existing Buff expiry callbacks and removal events;
it does not delete or rewrite history or silently mutate other active casts.
Direct binding of a missing or half-open expired instance is rejected without
writes. Default Buff identity includes source, so independent external Buffs
of the same definition retain their separate UID and survive another caster's
teardown.

Author verification is `validation/campaign/m93_world_cast_leases/`:

- `verification_final.json`: 26 actual passed assertions, including unchanged
  original controller9, packet3 and lifecycle4 plus 10 author negatives and
  ownership boundary checks. It includes complete captured input/command/event
  records, source/catalog/tool guards, disk reload/replay and fresh rebuilding.
- `compatibility_v2.json`: 95 actual passed original M78 attachment and selected
  ability/aura/event-resource/damage-hook checks; includes all actual imports and
  selected test file start/end SHA guards.
- `no_feature_comparison.json`: actual 0-1 120-tick and custom 30-tick complete
  observations against M78 differ only at six runtime fingerprints. All other
  JSON types, values and float bits agree.

The first compatibility attempt's import-path collection failure is preserved
as `compatibility.json`; `verify_v2.py` supplies the existing `tests_v2` helper
import path and records a fresh result. The 21-case first author report also
remains separate from the final 26-case report. Original M78 peer failures stay
frozen and failed. These are author receipts, not independent acceptance, all
V2 regression, 4-9/4-10 stage completion, 36-stage completion, or client accuracy.

`build.py` is exclusive and SHA-pinned, reconstructing only into a new candidate
path. For verification reruns, provide fresh output report paths or a new helper
directory; existing accepted report paths are intentionally not overwritten.
