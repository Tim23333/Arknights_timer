# -*- coding: utf-8 -*-
"""Wave timing tests (MECHANICS section 11).

Covers: chained-wave model (waves sequential, fragments concurrent within a
wave), deterministic intra-tick spawn order, hand-computed single-wave
timing, and emulator end-to-end timing.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.waves import build_wave_timeline, WaveScheduler
from ark_emulator import Simulator
from ark_emulator.consts import TIME_ROUGH_LOGIC_RATE
from ark_emulator.events import EventType
from ark_emulator.rng import SystemRandomClone


DATA = r"G:\Arknights\ark_parser\enemy\data\levels"


def _raw_waves(level_id):
    with open(os.path.join(DATA, level_id + ".json"), encoding="utf-8") as f:
        return json.load(f).get("waves") or []


def test_single_wave_expected_times():
    """main_01-01: hand-computed spawn times under the chained model."""
    tl = build_wave_timeline(_raw_waves("level_main_01-01"))
    spawns = [e for e in tl if e.get("actionType") == "SPAWN"]
    assert len(tl) == 36 and len(spawns) == 33
    assert spawns[0]["t"] == 3.0                       # first gopro_2
    assert spawns[-1]["t"] == 61.0                     # last wteeth (17+20+24)
    # fragment 2 is wave-relative (pre=17): act0 slime at 20, wteeth at 32
    frag2 = {e["action"]: e for e in tl
             if e.get("wave") == 0 and e.get("fragment") == 2
             and e.get("actionType") == "SPAWN" and e.get("seq") == 0}
    assert frag2[0]["t"] == 20.0
    assert frag2[1]["t"] == 32.0
    assert frag2[4]["t"] == 37.0
    # mocock spawns (frag1 act5 / frag2 act5) at 49 and 44
    mocock = [e for e in tl if e.get("key") == "enemy_1028_mocock"
              and e.get("actionType") == "SPAWN"]
    assert [e["t"] for e in mocock] == [44.0, 49.0]


def test_multi_wave_sequential():
    """main_08-17: waves are chained, never overlapping."""
    tl = build_wave_timeline(_raw_waves("level_main_08-17"))
    by_wave = {}
    for e in tl:
        by_wave.setdefault(e.get("wave"), []).append(e)
    waves = sorted(by_wave)
    prev_last = -1.0
    for wi in waves:
        evs = by_wave[wi]
        first = min(e["t"] for e in evs)
        last = max(e["t"] for e in evs)
        assert first >= prev_last, (wi, first, prev_last)
        prev_last = max(prev_last, last)
    # exact chained anchors: wave1 starts 5s after wave0's last spawn
    w0 = [e for e in tl if e.get("wave") == 0 and e.get("actionType") == "SPAWN"]
    w1 = [e for e in tl if e.get("wave") == 1 and e.get("actionType") == "SPAWN"]
    assert max(e["t"] for e in w0) == 48.0
    assert min(e["t"] for e in w1) == 53.0
    assert min(e["t"] for e in w1) - max(e["t"] for e in w0) == 5.0


def test_same_tick_order_deterministic():
    """Intra-tick spawn order = (wave, fragment, action, seq); stable."""
    waves = _raw_waves("level_main_03-06")
    tl = build_wave_timeline(waves)
    assert build_wave_timeline(waves) == tl          # deterministic
    from collections import defaultdict
    groups = defaultdict(list)
    for e in tl:
        groups[e["t"]].append(e)
    for t, evs in groups.items():
        if len(evs) < 2:
            continue
        key = lambda e: (e.get("wave"), e.get("fragment"),
                         e.get("action"), e.get("seq"))
        assert [key(e) for e in evs] == sorted(key(e) for e in evs), t


def test_emulator_wave_chain_integration():
    """End-to-end: the simulator spawns wave1 only after wave0 finished."""
    sim = Simulator(level_id="level_main_08-17")
    b = sim.battle
    b.life_point = 1000.0
    spawn_events = []
    last_seq = 0
    while b.tick < 60 * 30 and not b.finished:
        b.tick_once()
        for ev in b.events.snapshot_events(since_seq=last_seq):
            if ev["type"] == EventType.ENEMY_SPAWN:
                spawn_events.append((b.tick, ev["data"].get("key")))
        if b.events.log:
            last_seq = b.events.log[-1].seq
    # wave0 first enemy at t=0 (recorded tick is +1 after tick_once)
    assert spawn_events[0][0] in (0, 1), spawn_events[0]
    w0_last = max(t for t, k in spawn_events if k != "enemy_1108_uterer")
    # wave-1 uterer group spawns at tick 1590 (t=53.0), not earlier; the
    # same key also appears in wave 0 so filter to after wave 0 ended
    late = [t for t, k in spawn_events
            if k == "enemy_1108_uterer" and t >= 1500]
    assert late, "no wave-1 enemies spawned"
    assert min(late) >= 1589, min(late)
    assert w0_last <= 48 * 30 + 1, w0_last


def test_hidden_group_preserved_in_timeline():
    """Wave actions carrying hiddenGroup keep it on flattened events."""
    tl = build_wave_timeline(_raw_waves("level_act13side_sub-1-1"))
    hg = [e for e in tl if e.get("hiddenGroup")]
    assert len(hg) == 4, [e.get("key") for e in hg]
    assert all(e["hiddenGroup"] == "raid" for e in hg)
    keys = sorted(e.get("key") for e in hg)
    assert keys == ["enemy_1182_flasrt_2", "enemy_1182_flasrt_2",
                    "enemy_1183_mlasrt_2", "enemy_1183_mlasrt_2"]
    # non-hidden events carry None, so the field is always present
    assert all("hiddenGroup" in e for e in tl)


def test_hidden_group_difficulty_gating():
    """level_act13side_sub-1-1 enables group 'raid' only on FOUR_STAR:
    NORMAL skips all 4 hidden actions, FOUR_STAR spawns the 2 extra
    enemies; snapshot exposes the enabled/disabled group sets."""
    def run(diff):
        sim = Simulator(level_id="level_act13side_sub-1-1",
                        rune_difficulty=diff)
        b = sim.battle
        b.life_point = 10000.0
        skipped = []
        spawned = {"enemy_1182_flasrt_2": 0, "enemy_1183_mlasrt_2": 0}
        last_seq = 0
        while b.tick < 800 and not b.finished:
            b.tick_once()
            for ev in b.events.snapshot_events(since_seq=last_seq):
                if ev["type"] == "hidden_group_action_skipped":
                    skipped.append(ev["data"].get("hiddenGroup"))
                elif ev["type"] == EventType.ENEMY_SPAWN:
                    k = (ev["data"].get("key") or "").split("#")[0]
                    if k in spawned:
                        spawned[k] += 1
            if b.events.log:
                last_seq = b.events.log[-1].seq
        return skipped, spawned, b.snapshot().get("hiddenGroups")

    skipped, spawned, hg = run(1)
    assert skipped.count("raid") == 4, skipped
    assert spawned == {"enemy_1182_flasrt_2": 0, "enemy_1183_mlasrt_2": 0}
    assert hg == {"enable": [], "disable": []}

    skipped, spawned, hg = run(2)
    assert skipped == []
    assert spawned == {"enemy_1182_flasrt_2": 1, "enemy_1183_mlasrt_2": 1}
    assert hg == {"enable": ["raid"], "disable": []}


def test_route_index_none_defaults_to_zero():
    """FlatBuffers omits routeIndex when it is 0; timeline and spawn must
    treat None as route 0 instead of dropping the action."""
    tl = build_wave_timeline(_raw_waves("level_act11d0_01"))
    spawns = [e for e in tl if e.get("actionType") == "SPAWN"]
    assert spawns, "expected SPAWN events"
    # the omitted-field SPAWN (routeIndex None) now materialises as 0;
    # explicitly-set routes keep their original value
    assert spawns[0]["routeIndex"] == 0
    assert spawns[0]["key"] == "enemy_1007_slime"
    assert spawns[0]["t"] == 3.0
    assert all(isinstance(e.get("routeIndex"), int) for e in spawns)
    assert any(e["routeIndex"] > 0 for e in spawns), "explicit routes lost"


def test_route_index_none_end_to_end_spawn():
    """level_act11d0_01: first SPAWN has routeIndex omitted; the slime
    must actually spawn at t=3.0 under both NORMAL and FOUR_STAR runes."""
    for diff in (1, 2):
        sim = Simulator(level_id="level_act11d0_01", rune_difficulty=diff)
        b = sim.battle
        b.life_point = 10000.0
        spawned = []
        last_seq = 0
        while b.tick < 150 and not b.finished:
            b.tick_once()
            for ev in b.events.snapshot_events(since_seq=last_seq):
                if ev["type"] == EventType.ENEMY_SPAWN:
                    spawned.append((b.tick, ev["data"].get("key"),
                                    ev["data"].get("routeIndex")))
            if b.events.log:
                last_seq = b.events.log[-1].seq
        assert (91, "enemy_1007_slime", 0) in spawned, (diff, spawned)


def _resolved_groups(tl):
    """groupKey -> first event per (wave, fragment, key) group."""
    out = {}
    for e in tl:
        gk = e.get("groupKey")
        if not gk:
            continue
        out.setdefault((e["wave"], e["fragment"], gk), e)
    return out


def test_random_group_resolution_deterministic_and_unique():
    """lt01_01: each (wave, fragment, key) group resolves to exactly one
    candidate when a battle RNG is supplied; same seed reproduces the same
    timeline, and the unresolved static view keeps every candidate."""
    waves = _raw_waves("level_lt01_01")
    a = build_wave_timeline(waves, rng=SystemRandomClone(4242))
    b = build_wave_timeline(waves, rng=SystemRandomClone(4242))
    assert a == b
    groups = _resolved_groups(a)
    assert len(groups) == 4, groups          # g1..g4
    for gid, ev in groups.items():
        assert ev.get("key") is not None, (gid, ev)
    static = build_wave_timeline(waves)
    assert len(static) > len(a)


def test_random_group_weighted_distribution():
    """lt01_01 w2 g2: ucommd weight 60 vs handax 40; 1200 seeds land near
    the intended 60% / 40% split."""
    waves = _raw_waves("level_lt01_01")
    from collections import Counter
    c = Counter()
    for seed in range(1200):
        tl = build_wave_timeline(waves, rng=SystemRandomClone(700000 + seed))
        for e in tl:
            if e.get("groupKey") == "g2" and e.get("wave") == 2:
                c[e["key"]] += 1
                break
    n = sum(c.values())
    assert n == 1200
    frac = c.get("enemy_1111_ucommd", 0) / n
    assert 0.55 <= frac <= 0.66, (frac, c)


def test_random_group_empty_candidate():
    """rogue3_1-3 w1 bonus group: empty candidate weight 85 vs three
    5-weight enemies; most seeds resolve to the empty no-spawn pick."""
    waves = _raw_waves("level_rogue3_1-3")
    empty = 0
    n = 200
    for seed in range(n):
        tl = build_wave_timeline(waves, rng=SystemRandomClone(900000 + seed))
        bonus = [e for e in tl if e.get("groupKey") == "bonus"]
        assert len(bonus) == 1, seed
        if bonus[0].get("isEmpty"):
            empty += 1
        else:
            assert bonus[0]["key"] in ("enemy_2001_duckmi",
                                       "enemy_2002_bearmi",
                                       "enemy_2034_sythef"), seed
    assert empty > n * 0.7, empty


def test_random_group_pack_pairing():
    """rogue3_1-3 w0 f1: dx/ns groups pair a SPAWN with its PREVIEW_CURSOR
    companion through packKey; losing packs leave no events behind."""
    waves = _raw_waves("level_rogue3_1-3")
    for seed in range(30):
        tl = build_wave_timeline(waves, rng=SystemRandomClone(100 + seed))
        f1 = [e for e in tl if e.get("wave") == 0 and e.get("fragment") == 1]
        for prefix in ("dx", "ns"):
            spawn = [e for e in f1 if e.get("groupKey") == prefix]
            preview = [e for e in f1
                       if e.get("actionType") == "PREVIEW_CURSOR"
                       and e.get("packKey")
                       and e["packKey"].startswith(prefix)]
            assert len(spawn) == 1, (seed, prefix, f1)
            assert len(preview) == 1, (seed, prefix)
            assert spawn[0]["packKey"] == preview[0]["packKey"], (seed, prefix)


def test_random_group_pack_only_action_kept():
    """rogue1_1-2: an action with packKey but no groupKey (hidden 'extra'
    pack) is a plain scheduled action and survives resolution."""
    waves = _raw_waves("level_rogue1_1-2")
    for seed in range(20):
        tl = build_wave_timeline(waves, rng=SystemRandomClone(500 + seed))
        extra = [e for e in tl if e.get("packKey") == "extra"]
        assert len(extra) == 1, seed
        assert extra[0]["hiddenGroup"] == "extra"
        assert extra[0]["key"] == "enemy_1080_sotidp_2"


def test_random_group_resolution_drives_wave_chaining():
    """The resolved winner (not the raw candidates) sets the wave's end and
    therefore the next wave's start time (wave postDelay 10s)."""
    waves = [
        {"preDelay": 0.0, "postDelay": 10.0,
         "fragments": [{"preDelay": 0.0, "actions": [
             {"actionType": {"value": 0, "name": "SPAWN"},
              "key": "enemy_a", "count": 1, "preDelay": 5.0,
              "interval": 1.0, "routeIndex": 0,
              "randomSpawnGroupKey": "g1", "weight": 50},
             {"actionType": {"value": 0, "name": "SPAWN"},
              "key": "enemy_b", "count": 1, "preDelay": 40.0,
              "interval": 1.0, "routeIndex": 1,
              "randomSpawnGroupKey": "g1", "weight": 50},
         ]}]},
        {"preDelay": 0.0, "postDelay": -1.0,
         "fragments": [{"preDelay": 0.0, "actions": [
             {"actionType": {"value": 0, "name": "SPAWN"},
              "key": "enemy_c", "count": 1, "preDelay": 0.0,
              "interval": 1.0, "routeIndex": 2},
         ]}]},
    ]
    for seed in range(10):
        tl = build_wave_timeline(waves, rng=SystemRandomClone(seed))
        w0 = [e for e in tl if e["wave"] == 0]
        w1 = [e for e in tl if e["wave"] == 1]
        assert len(w0) == 1 and len(w1) == 1
        assert w0[0]["t"] in (5.0, 40.0)
        assert abs(w1[0]["t"] - (w0[0]["t"] + 10.0)) < 1e-6
    # unresolved static view chains by the latest candidate (t=40)
    tls = build_wave_timeline(waves)
    w0s = [e for e in tls if e["wave"] == 0]
    w1s = [e for e in tls if e["wave"] == 1]
    assert len(w0s) == 2
    assert abs(w1s[0]["t"] - 50.0) < 1e-6


class _FakeBattle:
    """Minimal battle surface for WaveScheduler unit tests."""
    def __init__(self, seed):
        self.tick = 0
        self.rng = SystemRandomClone(seed)
        self.events = []
        self.spawned = []
        self._rune_hidden_groups = {}

    def emit(self, tick, type_, data):
        self.events.append((tick, type_, data))

    def spawn_enemy(self, key, route_index, source_ev=None):
        self.spawned.append((key, route_index))
        return object()

    def activate_predefined(self, key):
        self.emit(self.tick, "predefined_activated", {"key": key})


def test_random_group_empty_event_at_runtime():
    """An empty group pick emits random_group_empty and spawns nothing; a
    non-empty pick spawns exactly its key (WaveScheduler.update)."""
    waves = [
        {"preDelay": 0.0, "postDelay": -1.0,
         "fragments": [{"preDelay": 0.0, "actions": [
             {"actionType": {"value": 0, "name": "SPAWN"},
              "key": None, "count": 1, "preDelay": 1.0, "interval": 1.0,
              "routeIndex": 0, "randomSpawnGroupKey": "bonus", "weight": 85},
             {"actionType": {"value": 0, "name": "SPAWN"},
              "key": "duckmi", "count": 1, "preDelay": 1.0, "interval": 1.0,
              "routeIndex": 1, "randomSpawnGroupKey": "bonus", "weight": 5},
             {"actionType": {"value": 0, "name": "SPAWN"},
              "key": "bearmi", "count": 1, "preDelay": 1.0, "interval": 1.0,
              "routeIndex": 2, "randomSpawnGroupKey": "bonus", "weight": 5},
             {"actionType": {"value": 0, "name": "SPAWN"},
              "key": "sythef", "count": 1, "preDelay": 1.0, "interval": 1.0,
              "routeIndex": 3, "randomSpawnGroupKey": "bonus", "weight": 5},
         ]}]},
    ]
    empty_total = 0
    for seed in range(40):
        battle = _FakeBattle(seed)
        tl = build_wave_timeline(waves, rng=battle.rng)
        sched = WaveScheduler(tl, battle)
        assert len(sched.random_groups) == 1
        battle.tick = int(1.0 * TIME_ROUGH_LOGIC_RATE)
        spawned = sched.update()
        assert len(spawned) <= 1
        if spawned:
            assert spawned[0] in ("duckmi", "bearmi", "sythef")
            assert len(battle.spawned) == 1
            assert battle.spawned[0][0] == spawned[0]
        else:
            empty_total += 1
            assert not battle.spawned
            assert any(t == "random_group_empty"
                       for _, t, _ in battle.events)
        assert sched.finished
    assert empty_total > 0


def test_random_group_end_to_end_spawn():
    """lt01_01: the resolved g1 pick (aghost route 11 or ucommd route 12)
    actually spawns in the simulator; identical seeds reproduce the exact
    enemy sequence."""
    waves = _raw_waves("level_lt01_01")
    tl = build_wave_timeline(waves, rng=SystemRandomClone(7))
    g1 = [e for e in tl if e.get("groupKey") == "g1"]
    assert len(g1) == 1
    expected = (g1[0]["key"], g1[0]["routeIndex"])

    def run(seed):
        sim = Simulator(level_id="level_lt01_01", seed=seed)
        b = sim.battle
        b.life_point = 10000.0
        spawned = []
        last_seq = 0
        while b.tick < 30 * 60 and not b.finished:
            b.tick_once()
            for ev in b.events.snapshot_events(since_seq=last_seq):
                if ev["type"] == EventType.ENEMY_SPAWN:
                    d = ev["data"]
                    spawned.append((d.get("key"), d.get("routeIndex")))
            if b.events.log:
                last_seq = b.events.log[-1].seq
        return spawned

    a1 = run(7)
    a2 = run(7)
    assert a1 == a2
    assert expected in a1, (expected, a1[:8])


def test_random_group_hidden_difficulty_gating():
    """rogue3_1-2: random-group candidates are still gated by hidden-group
    runes -- NORMAL enables 'n' (only dmgswd spawns), FOUR_STAR enables 'h'
    (dbskar+dmgswd spawn), the disabled group's winner is skipped."""
    def run(diff):
        sim = Simulator(level_id="level_rogue3_1-2", rune_difficulty=diff,
                        seed=11)
        b = sim.battle
        b.life_point = 10000.0
        spawned = []
        skipped = []
        last_seq = 0
        while b.tick < 40 * 30 and not b.finished:
            b.tick_once()
            for ev in b.events.snapshot_events(since_seq=last_seq):
                if ev["type"] == EventType.ENEMY_SPAWN:
                    spawned.append(ev["data"].get("key"))
                elif ev["type"] == "hidden_group_action_skipped":
                    skipped.append(ev["data"].get("hiddenGroup"))
            if b.events.log:
                last_seq = b.events.log[-1].seq
        return spawned, skipped

    s1, sk1 = run(1)
    s2, sk2 = run(2)
    assert s1[:2] == ["enemy_1075_dmgswd", "enemy_1075_dmgswd"], s1[:4]
    assert sk1.count("h") == 2, sk1
    assert "n" not in sk1
    assert set(s2[:2]) <= {"enemy_1074_dbskar", "enemy_1075_dmgswd"}, s2[:4]
    assert len(s2[:2]) == 2
    assert sk2.count("n") == 2, sk2
    assert "h" not in sk2


def test_random_group_snapshot_exposes_winners():
    """Battle snapshot exposes the resolved random-group winners."""
    sim = Simulator(level_id="level_lt01_01", seed=7)
    rg = sim.battle.snapshot()["waves"]["randomGroups"]
    assert len(rg) == 4, rg
    g1 = [g for g in rg if g["groupKey"] == "g1"]
    assert len(g1) == 1
    assert g1[0]["key"] in ("enemy_1026_aghost", "enemy_1111_ucommd")
    assert g1[0]["isEmpty"] is False


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("OK", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    print("all wave timing tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)
