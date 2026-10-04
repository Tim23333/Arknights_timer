# M70 exact-clock boundary counterexample

The M70 candidate and its original 24-case report remain frozen at `0b5a6a6b09cfbb631bd69dd67079814e90bccbe4d5d5737c1d33f869b7fab647`. Subsequent independent review found a real boundary not covered by those cases: their expiry probes advanced past the exact expiry clock.

`validation/campaign/m70_root_peer/initial_review.json` preserves the independent input and actual failed expectations. After `advance(3)`, a combo-immunity Buff expiring at tick3 has already ceased contributing to the read-only half-open selection projection. Cached dependent sleep control still permits attack until ordinary maintenance runs. Likewise, expiry of silence at time3 leaves a mixed active-rule Buff's cached modifiers/flags disabled even though the effective silence projection no longer contains SILENCED. Advancing to4 hides the mismatch and is not a repair.

This is a declared-model/API gap, not merely a pending native-body comparator. The immutable source model operands and earlier scoped tests remain valid evidence of their individual cases; M70 cannot be promoted as complete boundary behavior. A new M84 candidate implements explicit clock-boundary settlement, with new implementation identity and independent verification. It does not rewrite old M70 evidence or alter getter purity to mask the failure.
