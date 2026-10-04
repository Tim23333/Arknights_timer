# Exact snowwolf and icebreaker author batch

This module is bound to only `enemy_1065_snwolf_2@0/a153592b593567e5` and `enemy_1069_icebrk@0/2115d20b3e309ca7`. It preserves source level/overrides, native roots/movers/PPtrs, raw DB wrappers, every passive component and actual OnAttack records in variant bindings. No runtime, prior45/42-pin delivery, registry or live file is changed.

| Variant | HP | ATK | DEF | RES | Interval | OnAttack | TARGETFROZEN |
|---|---:|---:|---:|---:|---:|---:|---:|
| snwolf_2 |4650|430|0|30|1.4s /42ticks|16frames|1.5|
| icebrk |16000|830|500|20|3s /90ticks|29frames|2.5|

Each exact prefab has one PassiveBuffAbility carrying e2c_frozen_atkscale, no flag/attribute modifiers, isSilenceable0 and no EnemySkill/continuous HP/SP recovery. The builder rejects extra modes, animation drivers, skills, recovery or passive dependencies. Both actors reference the immutable source Cold module's actual TARGETFROZEN damage consumer. Their permanent source buffs do not change self ATK and are not silenced; the native flag16 predicate is checked at damage impact before per-target defense.

Actual ATK430/DEF100 packets are330 normally and545 on Frozen target. Actual ATK830/DEF100 packets are730 normally and1975 on Frozen target. Cold23 alone never grants the multiplier. Icebreaker's first cast begins before target freeze, but its30-tick hit receives1975 after public Cold20/21; this proves hit-time rather than stale cast-time qualification. Target expiration restores ordinary damage. Public Silence10 keeps the native nonsilenceable passive effect.

Native affectedBySlowDown1/timeMode0 is consumed by explicit seconds/max(effectiveASPD,.01) followed by existing ceil quantization. Under real public source Cold,16/.7 becomes23ticks and29/.7 becomes42ticks. Minimum speed and native maximum animation-scale/body relationship are explicit replaceable reference policies; both native maxAnimScale values are retained, not claimed client-calibrated. Undefined DB immunity wrappers remain raw; getter defaults are reference policy and are not encodedFalse claims.

30 author tests passed on read-only `campaign_chapter06_complete_base_v5_candidate`, Python corea7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a. They execute exact stats, real blocking and frames/intervals, public incoming physical/arts damage (RES30→875 andRES20→1000), no healing, DP7 cost/duplicate rejection, public withdrawal, death cancelling windup, source routes/base leak1, targetFrozen versus Cold-only, silence, scaled source clocks and actual diskCP/head replay.

Six persisted probes cover each unit with targetFrozen, sourceSilence and sourceCold. All actually reload disk checkpoints and replay the full public input records from start, comparing full event/snapshot/continuation hashes; complete JSONL journals are retained. Their runtime identity staysa705 rather than being reassigned to another candidate.

Independent review, complete_source_policies, whole-stage and client gates remain false. The nine-variant dependency priority matrix remains a source inventory, not a completed6-16/6-17 stage.
