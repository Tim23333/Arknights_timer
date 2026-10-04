# C6 exact units: first author batch

`dependency.priority.json` preserves every exact selected variant, source level/override, stats, mode nodes, PPtr/animation and passive/skill records. 6-16 (`level_main_06-14`) has50 births across8 variants; 6-17 (`level_main_06-15`) has one separate story variant. No source subset is presented as a complete stage.

| Priority | Exact variant | Required consumer |
|---|---|---|
| 1 | enemy_1006_shield_2@0/1b3c182b7c843247 | Plain blocked melee14 frames; this batch |
| 2 | enemy_1064_snsbr@0/46d19a92399ca050 | Blocked melee12 and TARGETFROZEN1.5; this batch |
| 3 | enemy_1065_snwolf_2@0/a153592b593567e5 | Melee16 and TARGETFROZEN1.5 |
| 3 | enemy_1069_icebrk@0/2115d20b3e309ca7 | Melee29 and TARGETFROZEN2.5 |
| 4 | enemy_1066_snbow@0/fc7412f7cf3aee2d | Ranged12, actual selector/projectile and TARGETFROZEN1.5 |
| 5 | enemy_1067_snslime@0/142dfde9301f6888 | Melee14, SOURCE not SILENCED death projectile, ATK2 and Cold10 |
| 6 | enemy_1068_snmage_2@0/36f9c16582d28dfa | Ranged20, EnemySkill SP2/coldattack priority0/ReadyEnemySkillEffect |
| 7 | enemy_1510_frstar2@0/3681c71c12a71fb0 | Two28-frame modes, reborn10/HP50%/ATK+.5/invincible20, shields/branch, Cold5/10 |
| 8 | enemy_1510_frstar2_s@0/2ca10c3158df0a8d | Independent NeverTrigger/no normal OnAttack, init16/23 skills, PURE NoSource2000 and story controls |

The first two consumers are in `melee.model.json`. Exact source stats:

| Variant | HP | ATK | DEF | RES | Interval | Speed | OnAttack |
|---|---:|---:|---:|---:|---:|---:|---:|
| shield_2 |10000|600|1000|0|2.6s /78ticks|.75|14frames|
| snsbr |3400|360|100|0|2s /60ticks|1.1|12frames|

The native MeleeAttack requires blocked target source2, wait-for-event1, physical damage1, scale1, no active buffs or extra damage. Source root delayToBorn and HP/SP recovery are zero, so no artificial zero-recovery system is added. Actual block volume, steering parameters, lifecycle leak loss, original raw DB wrappers and all passive records are preserved in each binding. The builder rejects unexpected mode/driver/passive/skill dependencies.

The snsbr has exactly one PassiveBuffAbility with `e2c_frozen_atkscale`, scale1.5, non-silenceable and no attribute/flag modifier. It references the immutable C6 Cold module's initial conditional damage-hook buff; it does not receive a global ATK multiplier. The shield has no such buff. Exact source missing immunity wrappers use an explicit replaceable getter defaultFalse policy; this is distinguished from the shield's encoded stunImmuneFalse.

The frozen Cold module remains SHA `e610f9446b077c6df7a86922e6719226e5a352a3826d6fe40c49e3296437b4dc`. Runtime is the read-only isolated buff.application v7 candidate, Python SHA `4ef955c5d5a7628382fc3d15003bb0a30c749832d210ca50897355568ec8d329`. No current runtime, registry or stage-run helper is modified.

24 author tests execute actual public deployment, block relation, DP7 payment, exact relative14/12 frame hits and78/60 intervals, physical incoming damage, arts incoming damage proving RES0 independent of DEF, no regeneration, withdrawal, lethal HP/death cancellation, route exit and base leak1, durable disk CP and head replay. The snsbr target is publicly Cold-applied at20/21: real packets are13:260,73:440,133:440,193:260 against DEF100, while source ATK remains360. Frozen immunity keeps all four packets260; plain shield packets remain500 despite a frozen target. The correctly summed final snsbr target HP is8600. The first author failure was an expected-HP addition mistake (8560); that receipt is retained, module/runtime bytes were not changed to fix it.

`evidence/` contains eight independent saved author probes: both exact units in blocked-damage, dead, route-exit and target-frozen cases, with complete JSONL events, actual disk reload and public from-head replay. Independent review, completed enemy roster, stage execution and client comparison remain false.
