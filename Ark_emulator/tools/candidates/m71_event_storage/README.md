# M71 opt-in event storage

This independent candidate is based on frozen M68 core
`1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8`.
It only changes event storage, transaction publication ordering for disk IO,
and explicit storage/checkpoint options. No battle math, RNG consumption,
scheduler ordering or world representation changes. The sole V1 directory
artifact copied from the parent is its offline `level_main_00-01.json` fixture.

## Calling interface

```python
simulation = Engine.create(program, seed=123, event_journal_path="new-active.jsonl")
# Alternatively, at an idle boundary, convert an already created simulation:
simulation.session.enable_event_journal("another-new-active.jsonl")

# Existing reads remain full, readonly values; dict key insertion order survives.
events = simulation.session.events
full_checkpoint = simulation.checkpoint()

# New explicit external-storage protocol:
reference_checkpoint = simulation.checkpoint(event_reference=True)
restored = Engine.restore(program, json.loads(saved_checkpoint_path.read_text()))
repeated = replay(program, simulation.export_replay(), event_journal_path="new-replay.jsonl")

export_metadata = simulation.session.export_events_jsonl("new-export.jsonl")
```

Every new active/export path must not already exist. The active file is owned by
the session. It records one complete insertion-order UTF-8 JSON object per line;
isolated Unicode surrogates are escaped without changing string values. Every
event retains its original ID, type, payload, time, cause, integer/float types,
negative zero and object key insertion order. All payloads still pass recursive
validation/detachment; foreign `FrozenMapping`/`FrozenTuple` identity never implies
that mutable children are trusted. No historical object-identity encoder cache
is introduced.

The journal retains one 64-bit offset and 32-byte SHA256 per event (plus container
overhead), rather than historical payload trees. Reads validate bytes before
decoding. Stable `iter_records` deliberately retains the existing materialized
readonly-slice semantics. The default full checkpoint remains complete embedded
JSON, and can have **higher** allocation cost than the original in-memory log.
Likewise `Simulation.snapshot()` and `session.events` still materialize full
history. Callers must choose the new options to lower these costs.

An external checkpoint creates a **sealed physical copy** of the logical journal
prefix. Its absolute path, SHA256, exact bytes and event count are embedded in
the checkpoint. Restore reads actual bytes, checks identity and required event
fields, finite JSON values, contiguous IDs/time/cause, then owns a separate branch
copy; the sealed file and original session cannot be rewritten through that
branch. Missing, truncated or modified referenced files fail explicitly before
live session state is published. There is no path fallback. A checkpoint is only
portable when its referenced file is also available at its bound absolute path.

Nested atomic rollback restores the event offset/checksum index and next ID with
no rollback disk IO. Aborted physical bytes may remain beyond the logical end,
are never read/exported/checkpointed, and future appends overwrite that tail.
Consequently physical active-file size can reflect its high-water mark. Complete
intent batches append before publishing world/scheduler stores, and failed
appends roll back the logical index before rethrowing. The disk operation does
not alter RNG records or their existing storage.

`campaign_streaming_evidence_v12.py` is a separate explicit consumer. It directly
exports owned bytes and recanonicalizes **one complete event at a time** for the
established canonical observation hashes, preserving their meaning. This still
requires per-event decoding/canonical encoding for hashing. It does not modify
the live v9 runner or `tools/campaign_streaming_evidence.py`.

## Costs and limits

Writes require one full event serialization, SHA256 and disk IO; reads require
SHA256 and decoding. Public full-history reads/default checkpoints remain
potentially large. Reference checkpoints use bounded event-sized memory but copy
the complete logical journal; storage consumption and copy time remain linear
in complete trace size. Each checkpoint/restore creates a new file. Caller must
retain sealed files while referenced checkpoints are needed and manage cleanup
afterward; the runtime does not silently remove evidence. There is no compression,
cross-event deduplication, crash-recovery protocol or guaranteed durable fsync.
Rollback only protects valid preceding bytes; physical damage to those bytes
fails explicitly rather than inventing replacement records. Live active-file
replacement/deletion and malicious external rewriting are outside exclusive
ownership; byte corruption is nevertheless checked on reads and exports.

The measured benchmark is complete actual 0-1 events through tick 120, not
fullstage RSS, million-event acceptance, 36-stage completion or client accuracy.
`tracemalloc` measures incremental Python allocation, not OS cache or process RSS.
The interrupted tick-600 attempt's 50,204,540-byte files remain as unaccepted
partial benchmark artifacts; no final benchmark report or campaign outcome was
obtained from that attempt. No previous missing-process diagnosis is inferred.

Independent tests cover nested savepoints, rollback of RNG/world versions/cache
epoch/scheduler identities, injected partial disk write/batch failure, readonly
iteration, foreign frozen mutable children, live/reference corruption, missing
files, rehashed semantically-invalid input, actual file reload/independent
branches, byte export and full-value Engine checkpoint/replay. Parent no-opt
comparison uses separate interpreters and reports only three actual
`runtime_fingerprint` paths; every other full value/type matches at tick 120.

The initial broad `tests_v2` attempt was interrupted without a final result;
early offline-import failures were caused by the initially omitted parent's
offline JSON fixture. That fixture is now included, and the focused kernel,
offline-import and independent storage suites were rerun successfully. Broad
suite completion remains unverified for M71.
