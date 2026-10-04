# M5 independent model review

Review date: 2026-10-02. This is an independent source review and executable
model check, not a native-client approval or a promotion of any of the 36
mainline cases. Only this document and `tests_v2/test_m5_independent_review.py`
were authored in this review. Core and integration fixes belong to the root
agent; old expectations and source recipe packages were not edited.

## Finding and correction

The first source inspection found that `build_campaign_squad.py` copied the
Weedy probe's `on_start.spawn.position={row:3,col:3}` and `facing=right` into the
integrated actor. Moving the host to (7,10) would therefore still create its
cannon at the probe coordinate. This was an actual integration input leak.

The root author corrected integration to remove that position/facing and require
`parameters.position_from_payload=true`. The independent regression requires
explicit (7,11), facing left, from a host at (7,10), facing up. It verifies the
created token's owner, exact position/facing and battle DP 50 -> 45. Missing,
out-of-map, fractional, boolean coordinate and noncardinal-facing payloads all
reject with the entire snapshot and event log unchanged. The original Weedy
source fixture remains intact. Card terrain, occupancy and the native water
cannon deployment UI constraints remain separate pending work.

## Independent witnesses

The new suite contains 23 cases, using small authored content and real
`Compiler`/`Engine` operations rather than mocked handlers or the root's helper
models. The only existing scene factory used supplies ordinary source/target
definitions; this review supplies its own effects, selectors, rules and assertions.

| Area | Independent evidence |
| --- | --- |
| Ownership | Retiring a source by alias retires its canonically owned child; the ownership record holds the resolved runtime ID. |
| Atomic payment | A second spawn beyond `max_owned` leaves battle DP, casts, scheduler, world snapshot and public events unchanged. |
| Lifetime | A command at the exact three-tick expiry cannot activate the child before the effect phase; zero-lifetime child also cannot attack on its first command tick. |
| Projectile completion | Two packets at different distances hold the cast until the slower impact; two nested delayed effects run without consuming or repeating projectile completion. |
| Area selection | One launched area packet includes a second living target moved inside its radius after launch; only one `area.resolved` event occurs. |
| Forced motion | A second push cancels the old generation and adds only its own displacement; map edge and wall clip actual displacement. |
| Effective mass | An explicit `mass_attribute` reads the current attribute including a flat Buff modifier, preventing a push that default mass would permit. |
| Distance merge | Both refresh and extend flush the old tail and start a new cursor. A lethal final removal produces two samples/two settlements total and one death, with no later duplicate settlement. |
| Half-open mode | A mode Buff expiring at tick three resets mode before automatic attack sampling; the sole ordinary packet is 10 damage, without the expired +20 Buff. |
| Owned SP gate | A foreign owner's child cannot enable recovery. The actual owner's SP is cleared and disabled at the child's exact expiry. |
| Temporal snapshot | A capture at tick three of a six-tick linear curve deals 20 across expiry; live ATK has already returned to 10. |
| Restore/replay | A wall-clipped 0.5-tile push settles 50 HP damage; checkpoint and replay snapshots exactly match the uninterrupted run. |
| Roster source | All twelve integrated actors are compared against normalized HP/ATK/DEF/RES/interval/block/cost/mass and selected native skill. Every source package SHA is checked, and selected skills are actually owned. |
| Ordinary clocks | Actor ability IDs are unique; ordinary automatic attacks have at most one eligible clock per mode. Chen's explicitly marked replacement attack is considered separately from its ordinary clock, consistent with the core's successful-start break. |

Reviewed source paths include `ark_sim/domains/abilities.py`, `effects.py`,
`movement.py`, `lifecycle.py`, `buffs.py`, `resources.py`,
`tools/build_campaign_squad.py` and `tools/build_campaign_units.py`.
`LifecycleSystem.retire` resolves aliases before comparing owners.
`AbilitySystem.start` plans all holders' costs and executes synchronous
`on_start` inside the same atomic transaction. Projectile payloads carry an
explicit completion marker; scheduled descendants do not inherit it.
The distance cursor is advanced before settlement, protecting reentrant death
and Buff removal against charging the same accepted movement twice.

The base attack converter uses source animation events, refuses missing events,
and checks exact binding attack path ID and charpack SHA. Its timing remains
explicitly `unscaled_native_animation_event_probe`; no missing frame is filled
with a timing fallback. Integration preserves actual base attributes before
adding skill-only attributes, includes the selected dependency closures and
retains `complete_operator_count=0` and `formal_mainline_approved=false`.

## Results and identity

Executed:

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m5_independent_review.py tests_v2/test_impacts_and_owned.py tests_v2/test_forced_distance.py tests_v2/test_temporal_and_recovery_gate.py tests_v2/test_buff_mode_lifecycle.py tests_v2/test_campaign_squad.py -q --tb=short
```

Result: **54 passed in 7.79 seconds**; the new independent suite contributes
23 of those cases. No test was skipped or marked expected failure.

At that run, SHA256 identities were:

| File | SHA256 |
| --- | --- |
| `tests_v2/test_m5_independent_review.py` | `74b6d47691b9f9b13d892e376585cb6ac520ed4a2f9a55f9e52dc482ef60ba27` |
| `tools/build_campaign_squad.py` | `c29e2de07c1d67dd54acedf8555c6cdefcec4bcba671d9d0a8c085283974052d` |
| `packages/campaign/squad.integrated.json` | `407d16fbfd563910219106588a66b68a826eef402f663013ab7d5daf95e01113` |

This result confirms the tested model contracts after the coordinate fix.
Push force/weight curves and linear forced-motion projection still use the
declared replaceable model profile; the client steering curve is not calibrated.
Temporal curves, native projectile callback positions, source-version alignment,
talent coverage, Eyja random target/FSM behavior, token ordinary attack clocks,
and complete native skill/unit validation remain their declared pending scope.
The current area implementation resolves the center from the target's position
at impact; this check proves its current model behavior, not a client assertion
that a projectile follows a moving target's final position.
