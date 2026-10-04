# M27 full event payload storage candidate

Candidate root `D:/Arknights/Arknights_timer/unpack_work/campaign_m27_event_intern_candidate` is frozen at75fdf7c2ffe99014f707aa900cbe5c4dffc9756229a81b607f0f3ef9178d9b90, copied from M267aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe. Only kernel/events.py, kernel/session.py and new kernel/interning.py differ. Primary, other candidates, old inputs and live long processes were untouched. Patch SHAa36bf3fad39ef7f08818a3152a03e0b3bbfe5fb38f80cd96c84aff7a1e597870; final report validation/campaign/m27_storage/candidate_final.json SHAd7c8370720501c2fe19b5b7b3fc91ca765ad7289c63a965f41968308a30248c0.

## Storage semantics

Root独立完整基线已真实exit0：0-1 11击杀/0漏怪、181937事件、CP恢复与完整命令回放相等，custom850/60及各自回放通过。core75fd与源/内容起止身份相等，证据 `validation/campaign/m27_storage/baseline_20261003.json` / `.identity.json`。新qualified1-12的基地99999完整过程+CP/replay正在session16100运行，不以本首关基线代替完整主线或客户端准确性。

Root另独立4项存储边界复核通过：内层savepoint失败保外层事件及不可变旧视图，成功内层后外层失败恢复完整checkpoint/随机日志，zero/tinycache预算及clear不改变全journal，restore后caller修改原checkpoint不能改日志且相等子树共享。报告 `validation/campaign/m27_root_peer/report.json`；没有修改候选源码。

Every event, number, nested value, ID/time/cause and payload remains. No trace branch is removed or sampled. Existing complete JSON validation executes before cross-event interning: cycles, nonfinite numbers, object keys, primitive subclasses, digit limits and malformed public FrozenMapping remain subject to original rules. Immutable equivalent payload subtrees can share storage across events. Hash matches require exact typed comparison; bool/int/float and signed-zero remain distinct. Mapping insertion order participates, array order is retained. Collision checks never assume a digest implies equality. Caller mutable data is detached; returned values stay immutable.

The pool uses32-byte hash keys rather than retaining giant structural tuples. It is local per EventLog, bounded to65536entries and32MiB conservative weighted deep cost. Deep descendants/aliases are counted repeatedly per entry, including mapping backing upper estimate128bytes/key, retained key and entry allowance. This overcounts sharing. OrderedDict and allocator overhead are bounded separately by entry count; the budget is NOT a hard RSS limit. Clear/eviction only changes performance; historical event data still owns all referenced immutable values. Failed atomic transactions restore events/RNG/world/tasks and clear the private performance cache. Restore validates all incoming records before swapping; each session/cache is independent.

## Measured retained data

Fixed actual package9135b591dc75836d544c3ae8ef9a1aa760b17d0af3b90a4f6fe84ddf4c97a034 is the frozen 1-12 M26 base-life99999 wrapper, with its actual unchanged26commands. Both implementations simulated300ticks. No fullstage or actual-game accuracy claim follows from this bounded storage test.

| At300ticks | Parent M26 | M27 |
|---|---:|---:|
| All retained events |47,370|47,370|
| RSS before census |311,480,320B|120,590,336B|
| Event-graph shallow retained estimate including mapping backings |251,860,715B|79,037,722B|
| Distinct container identities |993,685|248,335|
| Different typed/ordered container structures |121,292|121,292|
| Fully serialized compact event bytes |74,894,745|74,894,745|

RSS falls about61.3%, event retained estimate68.6%, container identities75.0%. The estimate is the event graph only, not world/program/cache/allocator accounting. Census has its own temporary overhead, so RSS before census is reported separately.

There is an explicit CPU cost. Actual advance-only process CPU is22.859375s parent vs33.46875s candidate, wall22.895s vs33.528s: about46.4% more CPU. Total census43.73s/43.52s must not be used to hide this regression, because the smaller graph also makes census cheaper. Final private pool has1,033entries/4.77MiB weighted cost,6.60M hits and464K misses. Ordinary failed automatic activation clears the cache frequently; future optimization can review cache retention across rollback in a NEW candidate. This version is frozen; memory savings do not justify silently relabeling CPU performance as improved.

## Full value comparison and identities

capture_v2.py reads actual package/commands bytes once for decoding, checks their SHA against guarded source identity, and saves those exact raw snapshots. It binds actual import/core/catalog/preset and before/after source guards. The original capture.py has a repeated-read window; its original report is retained as bounded history, not claimed as a solved actual-byte identity gate.

The final actual-byte comparison is validation/campaign/m27_storage/all_values_capture_v2.json SHAc8c98ad42caa9856f2e972d14a03d27c3d145c9a55d049e7838597ddd2b1dd71. It directly parses and compares all47,370events line by line and complete world/random/scheduler/state:2,459,461 scalar values and1,241,336containers. Type checks and IEEE float bits preserve bool/int/float/signed-zero. No payload field is excluded. Raw full event bytes are equal, SHA0e7e9a12be53069de877317d0ee055182c8429911de28e326a39cff01fa1f3b3; raw continuation bytes equal SHAd6410e3bd7b229fbcb9954fc1000644ce31f881bce36b8887830732b8b12f312. Typed ordered graph hashes also match at0/100/200/300. Program fingerprint is the same, API runtime fingerprints differ and are explicitly kept separately in reports; there is no broad fingerprint/metadata removal from compared data.

Final fresh21storage cases plus102existing kernel/replay/M6review cases all passed:123 total. Cases include forced hash collision, LRU/clear, independent restore, caller aliases, complete actual atomic RNG/events rollback, actual program checkpoint/commands replay, original lone-surrogate emit acceptance, validation-before-restore-swap and changing digit limit on a would-be cache hit. Candidate source start/end remain identical.

## Content provenance and remaining validation

Input metadata.required_runtime remains7aa because the input is frozen M26 content and the storage comparison intentionally preserves every byte. Compiler does not enforce this author metadata as a runtime admission gate. This experiment locks actual imported75fd and actual bytes explicitly. New long baseline/qualified-stage evidence must record actual75fd runtime, never migrate old7aa receipt or claim metadata was updated. Root's new content wrapper may later declare75fd under its own new content identity; this test does not mutate the old input.

Fullsuite, independent peer and whole-stage CP/replay remain Root's separate required checks. The user requires exact game intermediate data; this candidate only proves conservation of declared simulation values, not native correctness. No formal stage receipt or gameplay accuracy approval is created here.
