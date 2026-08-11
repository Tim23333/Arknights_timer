"""Deterministic tests for the enemy skill system (no full level needed)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.attributes import Attributes
from ark_emulator.buffs import BuffSystem
from ark_emulator.entities import Enemy, Operator
from ark_emulator.events import EventBus
from ark_emulator.loader import DataStore
from ark_emulator.rng import SystemRandomClone
from ark_emulator.skills import EnemySkillController


class FakeBattle:
    """Minimal battle stub satisfying the skill controller interface."""

    def __init__(self):
        self.tick = 0
        self.events = EventBus()
        self.rng = SystemRandomClone(1)
        self._enemies = []
        self._ops = []
        self.buffs = BuffSystem(self)
        self.damage_log = []

    def get_enemies(self):
        return self._enemies

    def get_operators(self):
        return self._ops

    def get_tokens(self):
        return []

    def emit(self, tick, type_, data=None):
        return self.events.emit(tick, type_, data)

    def apply_damage(self, target, amount, dmg_type, source=None):
        actual = target.take_damage(amount)
        self.damage_log.append((source.inst_id, target.inst_id, amount, dmg_type))
        self.emit(self.tick, "damage", {"target": target.inst_id,
                                        "amount": actual, "type": dmg_type})
        return actual

    def add_buff(self, unit, buff):
        return self.buffs.apply(unit, buff)

    def add_abnormal(self, unit, flag, seconds):
        return self.buffs.set_abnormal(unit, flag, seconds)

    def add_ep(self, unit, ep_type, amount):
        return self.buffs.update_ep(unit, ep_type, amount)

    def spawn_projectile(self, source, target, projectile_key, damage_type,
                         atk_scale=1.0, hit_callback=None):
        """Record launched projectiles; settle damage immediately (test stub)."""
        from ark_emulator.projectiles import Projectile, projectile_speed
        p = Projectile(source, target, projectile_speed(projectile_key),
                       damage_type=damage_type, atk_scale=atk_scale,
                       key=projectile_key, hit_callback=hit_callback)
        p.on_hit(self)
        self.projectiles = getattr(self, "projectiles", []) + [p]
        return p


def _make_enemy(key, battle):
    st = DataStore()
    merged = st.build_merged_enemy(key, 0)
    data = merged["data"]
    attrs = {k: (v if v is not None else 0.0)
             for k, v in (data.get("attributes") or {}).items()}
    enemy = Enemy(key, Attributes(attrs), route_index=0, row=3, col=4)
    enemy.skills = data.get("skills") or []
    enemy.sp_max = float((data.get("spData") or {}).get("maxSp") or 0)
    enemy.sp = float((data.get("spData") or {}).get("initSp") or 0)
    entries = st.enemy_skills(key)
    enemy.skill_controller = EnemySkillController(enemy, battle, entries,
                                                  store=st)
    battle._enemies.append(enemy)
    return enemy


def _make_operator(battle):
    op = Operator("char_test", Attributes({"maxHp": 2000, "atk": 100,
                                           "def": 50, "magicResistance": 10,
                                           "cost": 10, "blockCnt": 2,
                                           "baseAttackTime": 1.0,
                                           "attackSpeed": 100,
                                           "respawnTime": 70}),
                  row=3, col=4, deploy_tick=-100)
    op.pos_x, op.pos_y = 4.0, 3.0
    battle._ops.append(op)
    return op


def test_trslim_startrun_init():
    battle = FakeBattle()
    enemy = _make_enemy("enemy_10001_trslim", battle)
    assert enemy.skill_controller is not None
    s = enemy.skill_controller.skills[0]
    assert s.prefab_key == "StartRun"
    assert s.cooldown == 10.0
    assert s.cooldown_remaining == 10.0
    print("OK test_trslim_startrun_init")


def test_sgcat_skill_casts_and_damages():
    battle = FakeBattle()
    enemy = _make_enemy("enemy_10020_sgcat", battle)
    op = _make_operator(battle)
    ctrl = enemy.skill_controller
    # force cooldowns ready, put operator in range
    for s in ctrl.skills:
        s.cooldown_remaining = 0.0
    # simulate ticks until a skill takes over an attack
    took = None
    for _ in range(10):
        if ctrl.on_attack_timer_zero():
            took = ctrl.casting
            break
    assert took is not None, "sgcat skill should take over an attack"
    assert took.skill.prefab_key in ("bigAttack", "bigAttack2")
    # drive the ability to completion
    for _ in range(60):
        ctrl.update(1 / 30.0)
        if ctrl.casting is None:
            break
    assert ctrl.casting is None
    assert battle.damage_log, "skill should have dealt damage"
    print("OK test_sgcat_skill_casts_and_damages",
          took.skill.prefab_key, "damages:", len(battle.damage_log))


def test_interrupt_on_stun():
    battle = FakeBattle()
    enemy = _make_enemy("enemy_10020_sgcat", battle)
    _make_operator(battle)
    ctrl = enemy.skill_controller
    for s in ctrl.skills:
        s.cooldown_remaining = 0.0
    assert ctrl.on_attack_timer_zero()
    # stun the enemy mid-cast
    battle.add_abnormal(enemy, 0, 3.0)
    for _ in range(30):
        ctrl.update(1 / 30.0)
    # ability should finish interrupted, not deal full damage chain
    print("OK test_interrupt_on_stun finish_reason:",
          ctrl.casting.finish_reason if ctrl.casting else "cleared")


def test_enemy_sp_recovery():
    """Enemy SP: attack-recover (spType=2) fills SP then casts SP skill."""
    from ark_emulator.loader import DataStore as _DS
    st = _DS()
    b = FakeBattle()
    merged = st.build_merged_enemy("enemy_10023_vtsnky", 0)
    data = merged["data"]
    attrs = {k: (v if v is not None else 0.0)
             for k, v in (data.get("attributes") or {}).items()}
    e = Enemy("enemy_10023_vtsnky", Attributes(attrs), route_index=0, row=0, col=0)
    e.sp_max = float((data.get("spData") or {}).get("maxSp") or 0)
    e.sp = 0.0
    e._sp_data = data.get("spData") or {}
    e.skills = data.get("skills") or []
    ctrl = EnemySkillController(e, b, st.enemy_skills("enemy_10023_vtsnky"),
                                store=st)
    e.skill_controller = ctrl
    assert e.sp_max == 3.0
    for _ in range(3):
        ctrl.on_enemy_attack()
    assert e.sp >= 3.0
    print("OK test_enemy_sp_recovery sp:", e.sp)


def test_variable_cooldown():
    """cooldown_0..N sequence drives subsequent cooldowns."""
    from ark_emulator.loader import DataStore as _DS
    st = _DS()
    b = FakeBattle()
    merged = st.build_merged_enemy("enemy_1514_smephi", 0)
    attrs = {k: (v if v is not None else 0.0)
             for k, v in (merged["data"].get("attributes") or {}).items()}
    e = Enemy("enemy_1514_smephi", Attributes(attrs), route_index=0, row=0, col=0)
    e.skills = merged["data"].get("skills") or []
    ctrl = EnemySkillController(e, b, st.enemy_skills("enemy_1514_smephi"),
                                store=st)
    s = next(x for x in ctrl.skills if x.prefab_key == "blink")
    assert s.cooldown_sequence == [75.0, 65.0, 60.0, 45.0, 30.0, 30.0]
    expected = [75.0, 65.0, 60.0, 45.0]
    for exp in expected:
        s.cooldown_remaining = 0
        s.on_cast_finish()
        assert s.cooldown_remaining == exp, (s.cooldown_remaining, exp)
    print("OK test_variable_cooldown")


def test_action_nodes():
    """Prefab _actions nodes execute (branch advance / instant kill)."""
    from ark_emulator.action_nodes import ActionNodeExecutor

    class B:
        tick = 0
        def __init__(self):
            self.events = []
            self.buffs = None
        def emit(self, t, ty, data=None):
            self.events.append((ty, data))
        def execute_branch(self, b, is_loop=False):
            self.events.append(("branch", b))
        def spawn_enemy_directive(self, *a):
            self.events.append(("spawn", a))

    class TB:
        def remove(self, *a): pass

    b = B(); b.buffs = TB()
    ex = ActionNodeExecutor(b)
    nodes = ex.parse('[{"_branchId":"faust_ballis","$type":"Torappu.Battle.Action.Nodes+MoveNextLevelBranch"}]')
    ex.execute(nodes)
    assert any(t == "branch" for t, _ in b.events)
    b2 = B(); b2.buffs = TB()
    class T:
        dead = False
        hp = 100
        inst_id = 1
        def take_damage(self, a): self.hp -= a; self.dead = True
    t = T()
    ex2 = ActionNodeExecutor(b2)
    ex2.execute([{"$type": "Torappu.Battle.Action.Nodes+InstantKill"}],
                target=t)
    assert t.dead
    print("OK test_action_nodes")


def test_ifelse_condition():
    """IfElse condition node branches on CheckBlocked."""
    from ark_emulator.action_nodes import ActionNodeExecutor

    class B:
        tick = 0
        def __init__(self):
            self.events = []
            self.buffs = None
        def emit(self, t, ty, data=None): self.events.append((ty, data))
        def execute_branch(self, b): self.events.append(("branch", b))
        def spawn_enemy_directive(self, *a): self.events.append(("spawn", a))

    class TB:
        def remove(self, *a): pass

    class U:
        dead = False
        hp = 100
        inst_id = 1
        def __init__(self, blocked=False):
            self.blocked_by = object() if blocked else None
        def take_damage(self, a): self.hp -= a; self.dead = True

    nodes = [{
        "_conditionNode": {"_targetType": "TARGET",
                           "_sourceType": "TARGET",
                           "$type": "Torappu.Battle.Action.Nodes+CheckBlocked"},
        "_succeedNodes": [
            {"$type": "Torappu.Battle.Action.Nodes+InstantKill"}],
        "$type": "Torappu.Battle.Action.Nodes+IfElse"}]
    b1 = B(); b1.buffs = TB()
    ex1 = ActionNodeExecutor(b1)
    t1 = U(blocked=True)
    ex1.execute(nodes, target=t1)
    assert t1.dead
    b2 = B(); b2.buffs = TB()
    ex2 = ActionNodeExecutor(b2)
    t2 = U(blocked=False)
    ex2.execute(nodes, target=t2)
    assert not t2.dead
    print("OK test_ifelse_condition")


def test_multi_hit_exact_onattack_frames():
    """Multi-hit skills execute effects once per calibrated OnAttack frame."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_2089_skzjkl", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col
    enemy.pos_x, enemy.pos_y = float(op.col), float(op.row)
    enemy.state = EnemyState.COMBAT
    sc = enemy.skill_controller
    multi = next(s for s in sc.skills if s.prefab_key == "M1MultiAttack")
    assert len(multi.hit_times) == 5, multi.hit_times
    sc._start_cast((multi, op))
    t0 = b.tick / 30.0
    hits = []
    last_seq = 0
    for _ in range(150):
        b.tick_once()
        for ev in b.events.snapshot_events(since_seq=last_seq):
            if ev["type"] == "attack" and ev["data"].get("skill") == "M1MultiAttack":
                hits.append(round(ev["t"], 3))
        if b.events.log:
            last_seq = b.events.log[-1].seq
        if sc.casting is None:
            break
    exp = [round(t0 + multi.pre_delay + t, 3) for t in multi.hit_times]
    assert len(hits) == len(exp), (hits, exp)
    for o, e in zip(hits, exp):
        assert abs(o - e) < 0.05, (o, e)


def test_action_node_tile_and_release_handlers():
    """Enemy action nodes: ReleaseFromBlocker/ChangeMotionMode change state;
    tile/visual nodes surface observer events."""
    from ark_emulator import Simulator
    from ark_emulator.action_nodes import ActionNodeExecutor
    from ark_emulator.consts import EnemyState
    sim = Simulator("level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.state = EnemyState.COMBAT
    e.blocked_by = op
    op.add_blockee(e)
    ex = ActionNodeExecutor(b)
    ex.execute([
        {"$type": "Torappu.Battle.Action.Nodes+ReleaseFromBlocker",
         "_target": "TARGET"},
        {"$type": "Torappu.Battle.Action.Nodes+ChangeMotionMode",
         "_target": "TARGET", "_motionMode": "FLY"},
        {"$type": "Torappu.Battle.Action.Nodes+IgniteAllReedTile"},
        {"$type": "Torappu.Battle.Action.Nodes+SwitchDynamicBuffTileMode",
         "_modeIndex": 1, "_tileType": "REED_TILE"},
        {"$type": "Torappu.Battle.Action.Nodes+SetBodyDirection",
         "_direction": "DOWN"},
        {"$type": "Torappu.Battle.Action.Nodes+CreateTileEffect",
         "_effectKey": "fx"},
    ], source=e, target=e, owner=None)
    assert e.blocked_by is None and e.state == EnemyState.MOVE
    assert not op.blocked_enemies
    assert e._motion_mode == 1          # FLY
    evs = [ev["type"] for ev in b.events.snapshot_events()
           if ev["type"] in ("enemy_released", "enemy_motion_mode",
                             "tiles_ignite", "tile_mode_switch",
                             "enemy_facing", "tile_effect")]
    # tile_mode_switch now fires per switched reed tile (real state
    # change), so assert every node type surfaces at least once instead
    # of an exact count
    assert {"enemy_released", "enemy_motion_mode", "tiles_ignite",
            "tile_mode_switch", "enemy_facing", "tile_effect"} <= set(evs), evs


def test_action_node_wave_teleport_transport_summon():
    """FinishCurrentWave / ForceSetToTilePosition / Transport /
    SummonEnemiesOnTargetTile produce real battle-state changes."""
    from ark_emulator import Simulator
    from ark_emulator.action_nodes import ActionNodeExecutor
    from ark_emulator.consts import EnemyState

    sim = Simulator("level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.state = EnemyState.COMBAT
    ex = ActionNodeExecutor(b)
    # FinishCurrentWave: skip remaining events of the current wave
    before = b.waves.remaining()
    ex.execute([{"$type": "Torappu.Battle.Action.Nodes+FinishCurrentWave"}],
               source=e, target=e, owner=None)
    assert b.waves.remaining() < before, (before, b.waves.remaining())
    # ForceSetToTilePosition: release from blocker + teleport to passable tile
    e.blocked_by = op
    op.add_blockee(e)
    ex.execute([{"$type": "Torappu.Battle.Action.Nodes+ForceSetToTilePosition",
                 "_targetType": "SOURCE"}], source=e, target=e, owner=None)
    assert e.blocked_by is None and not op.blocked_enemies
    # Transport: swap source/target tiles
    e2row, e2col = 5, 5
    e.row, e.col = e2row, e2col
    e.pos_x, e.pos_y = float(e2col), float(e2row)
    orow, ocol = op.row, op.col
    ex.execute([{"$type": "Torappu.Battle.Action.Nodes+Transport",
                 "_sourceType": "TARGET", "_targetType": "SOURCE"}],
               source=e, target=op, owner=None)
    assert op.row == e2row and op.col == e2col, (op.row, op.col)
    assert e.row == orow and e.col == ocol, (e.row, e.col)
    # SummonEnemiesOnTargetTile
    n0 = len(b.enemies)
    ex.execute([{"$type": "Torappu.Battle.Action.Nodes+SummonEnemiesOnTargetTile",
                 "_enemyKey": "enemy_1000_gopro", "_summonCount": 1}],
               source=e, target=e, owner=None)
    assert len(b.enemies) == n0 + 1, (n0, len(b.enemies))


def test_enemy_skill_targets_blocker():
    """A blocked enemy's abilities target its blocker first (MECHANICS 5.1),
    even when another operator is closer within range."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator("level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 5, 4)     # blocker (farther from enemy)
    blocker = b.operators[0]
    b.deploy("char_102_texas", 3, 5)     # closer operator
    b.spawn_enemy("enemy_2089_skzjkl", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = 3, 4
    enemy.state = EnemyState.COMBAT
    enemy.blocked_by = blocker
    sc = enemy.skill_controller
    multi = next(s for s in sc.skills if s.prefab_key == "M1MultiAttack")
    target = sc._find_target(multi)
    assert target is blocker, target.char_id if target else None


def test_action_node_effect_audio_events():
    """Enemy action nodes CreateEffect/PlayAudio surface as observer
    events (skill_effect / skill_audio) without changing battle state."""
    from ark_emulator import Simulator
    from ark_emulator.action_nodes import ActionNodeExecutor
    sim = Simulator("level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    ex = ActionNodeExecutor(b)
    ex.execute([
        {"$type": "Torappu.Battle.Action.Nodes+CreateEffect",
         "_effectKey": "test_boom"},
        {"$type": "Torappu.Battle.Action.Nodes+PlayAudio",
         "_audioSignal": "sfx_test"},
    ], source=e, target=e, owner=None)
    evs = [ev for ev in b.events.snapshot_events()
           if ev["type"] in ("skill_effect", "skill_audio")]
    assert len(evs) == 2, evs
    assert evs[0]["type"] == "skill_effect" and evs[0]["data"]["effect"] == \
        "test_boom"
    assert evs[1]["type"] == "skill_audio" and evs[1]["data"]["audio"] == \
        "sfx_test"


if __name__ == "__main__":

    test_trslim_startrun_init()
    test_sgcat_skill_casts_and_damages()
    test_interrupt_on_stun()
    test_enemy_sp_recovery()
    test_variable_cooldown()
    test_action_nodes()
    test_ifelse_condition()
    test_multi_hit_exact_onattack_frames()
    print("all skill system tests passed")



def test_interrupt_enters_cooldown_and_restores_state():
    """Stunning an enemy mid-cast interrupts the ability: the interrupted
    skill enters its cooldown (no instant recast), the enemy state returns
    to COMBAT after the stun, and a recast happens once the cooldown has
    elapsed."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_127_estell", 3, 4)
    b.spawn_enemy("enemy_10020_sgcat", 0, overrides={
        "attributes": {"atk": 50.0}, "row": 3, "col": 5})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    for _ in range(600):
        b.tick_once()
        if sc.casting_state() is not None:
            break
    assert sc.casting_state() is not None, "enemy should start a cast"
    b.add_abnormal(e, 0, 3.0)          # stun mid-cast
    for _ in range(30):
        b.tick_once()
    assert sc.casting_state() is None, "cast must be interrupted"
    fins = [x for x in b.events.snapshot_events()
            if x["type"] == "skill_finish"]
    assert fins and fins[-1]["data"]["reason"] == 1, fins
    cast = next(s for s in sc.skills if s.prefab_key ==
                "bigAttack" or s.prefab_key == "bigAttack2")
    # interrupted skill entered its cooldown (no instant recast)
    assert cast.cooldown_remaining > 0.0, cast.cooldown_remaining
    # after the stun the enemy returns to COMBAT (not stuck in MOVE)
    for _ in range(200):
        b.tick_once()
    assert e.state == EnemyState.COMBAT, e.state
    # once the cooldown elapses the enemy casts again
    recast = None
    for _ in range(300):
        b.tick_once()
        if sc.casting_state() is not None:
            recast = sc.casting_state()
            break
    assert recast is not None, "enemy must recast after cooldown"


def test_wait_for_attack_event_zero_fires_at_spell_start():
    """_waitForAttackEvent=false executes effects right after preDelay
    instead of waiting for the calibrated OnAttack frame (game
    EasyToStartAbility semantics; Frost Star ArcticBlast: wait=0,
    preDelay 0.933s, onAttack 0.5667s -> effects at ~0.93s, not ~1.5s)."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    e = b.spawn_enemy("enemy_1505_frstar", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    ab = next(s for s in sc.skills if s.prefab_key == "ArcticBlast")
    assert ab.wait_for_attack_event is False
    assert len(ab.hit_times) >= 1, ab.hit_times
    assert ab.pre_delay > 0.0
    b.events.log = []
    sc._start_cast((ab, op))
    cast_tick = b.tick
    effect_tick = None
    last_seq = 0
    for _ in range(120):
        b.tick_once()
        for ev in b.events.snapshot_events(since_seq=last_seq):
            if ev["type"] == "attack" and \
                    ev["data"].get("skill") == "ArcticBlast":
                effect_tick = ev["tick"]
        if b.events.log:
            last_seq = b.events.log[-1].seq
        if sc.casting is None:
            break
    assert effect_tick is not None, "ArcticBlast effects never fired"
    pre_ticks = int(round(ab.pre_delay * 30))
    assert cast_tick + pre_ticks <= effect_tick <= cast_tick + pre_ticks + 2, \
        (cast_tick, effect_tick, pre_ticks)
    # must NOT also wait the calibrated OnAttack frames
    extra = int(round(ab.hit_times[0] * 30))
    assert effect_tick < cast_tick + pre_ticks + extra, \
        (effect_tick, ab.hit_times)


def test_wait_for_attack_event_one_keeps_onattack_frames():
    """_waitForAttackEvent=true still defers effects to the calibrated
    OnAttack frame after preDelay (Faust CriticalHit: wait=1, preDelay 0,
    onAttack 1.3333s -> effects at ~40 frames)."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    e = b.spawn_enemy("enemy_1508_faust", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    ch = next(s for s in sc.skills if s.prefab_key == "CriticalHit")
    assert ch.wait_for_attack_event is True
    assert len(ch.hit_times) == 1, ch.hit_times
    b.events.log = []
    sc._start_cast((ch, op))
    cast_tick = b.tick
    effect_tick = None
    last_seq = 0
    for _ in range(200):
        b.tick_once()
        for ev in b.events.snapshot_events(since_seq=last_seq):
            if ev["type"] == "attack" and \
                    ev["data"].get("skill") == "CriticalHit":
                effect_tick = ev["tick"]
        if b.events.log:
            last_seq = b.events.log[-1].seq
        if sc.casting is None:
            break
    assert effect_tick is not None, "CriticalHit effects never fired"
    pre_ticks = int(round(ch.pre_delay * 30))
    hit_ticks = int(round(ch.hit_times[0] * 30))
    assert cast_tick + pre_ticks + hit_ticks <= effect_tick <= \
        cast_tick + pre_ticks + hit_ticks + 2, \
        (cast_tick, effect_tick, pre_ticks, hit_ticks)


def test_wait_one_uses_max_pre_delay_vs_onattack():
    """wait=1 with preDelay>0: spell_on at max(preDelay, OnAttack), not
    preDelay + OnAttack (Spy Lasso: preDelay 0.4s == onAttack 0.4s ->
    effects at 0.4s = 12 ticks, not 24)."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    e = b.spawn_enemy("enemy_10134_pycspy", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    la = next(s for s in sc.skills if s.prefab_key == "Lasso")
    assert la.wait_for_attack_event is True
    assert abs(la.pre_delay - 0.4) < 0.01, la.pre_delay
    assert len(la.hit_times) == 1 and abs(la.hit_times[0] - 0.4) < 0.01, \
        la.hit_times
    b.events.log = []
    sc._start_cast((la, op))
    cast_tick = b.tick
    effect_tick = None
    last_seq = 0
    for _ in range(120):
        b.tick_once()
        for ev in b.events.snapshot_events(since_seq=last_seq):
            if ev["type"] == "attack" and \
                    ev["data"].get("skill") == "Lasso":
                effect_tick = ev["tick"]
        if b.events.log:
            last_seq = b.events.log[-1].seq
        if sc.casting is None:
            break
    assert effect_tick is not None, "Lasso effects never fired"
    assert cast_tick + 12 <= effect_tick <= cast_tick + 13, \
        (cast_tick, effect_tick)
    # must NOT add the OnAttack time on top of preDelay
    assert effect_tick < cast_tick + 24, effect_tick


def test_wait_one_action_node_fires_at_onattack_frame():
    """wait=1 action nodes (summon/branch) fire at the calibrated OnAttack
    frame together with effects (Faust SummonBallis: preDelay 0, onAttack
    0.9s -> faust_ballis branch at 27 frames, not cast start)."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    e = b.spawn_enemy("enemy_1508_faust", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    sb = next(s for s in sc.skills if s.prefab_key == "SummonBallis")
    assert sb.wait_for_attack_event is True
    assert len(sb.hit_times) == 1 and abs(sb.hit_times[0] - 0.9) < 0.01, \
        sb.hit_times
    b.events.log = []
    sc._start_cast((sb, op))
    cast_tick = b.tick
    branch_tick = None
    last_seq = 0
    for _ in range(120):
        b.tick_once()
        for ev in b.events.snapshot_events(since_seq=last_seq):
            if ev["type"] == "level_branch" and \
                    ev["data"].get("branch") == "faust_ballis":
                branch_tick = ev["tick"]
        if b.events.log:
            last_seq = b.events.log[-1].seq
        if sc.casting is None:
            break
    assert branch_tick is not None, "faust_ballis branch never fired"
    assert cast_tick + 27 <= branch_tick <= cast_tick + 28, \
        (cast_tick, branch_tick)
    # must NOT fire at cast start
    assert branch_tick > cast_tick + 5, branch_tick


def test_no_attack_component_skill_deals_no_damage():
    """Pure summon/branch skills (SummonBallis: no _damageType, no atk_scale)
    deal no damage, while attack skills (CriticalHit) still land hits."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    e = b.spawn_enemy("enemy_1508_faust", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    sb = next(s for s in sc.skills if s.prefab_key == "SummonBallis")
    assert sb.prefab_damage_type is None
    assert "atk_scale" not in sb.blackboard
    b.events.log = []
    sc._start_cast((sb, op))
    guard = 0
    while sc.casting is not None and guard < 300:
        b.tick_once()
        guard += 1
    dmg = [ev for ev in b.events.snapshot_events()
           if ev["type"] == "damage" and
           ev["data"].get("source") == e.inst_id]
    assert not dmg, dmg
    # positive control: CriticalHit still deals atk x 2.0 damage
    ch = next(s for s in sc.skills if s.prefab_key == "CriticalHit")
    assert ch.prefab_damage_type is not None
    assert ch.blackboard.get("atk_scale") == 2.0
    b.events.log = []
    sc._start_cast((ch, op))
    guard = 0
    while sc.casting is not None and guard < 300:
        b.tick_once()
        guard += 1
    dmg2 = [ev for ev in b.events.snapshot_events()
            if ev["type"] == "damage" and
            ev["data"].get("source") == e.inst_id and
            ev["data"].get("target") == op.inst_id]
    assert dmg2, "CriticalHit must deal damage"


def test_enemy_bb_atk_key_is_attack_scale():
    """bb 'atk' on attack-typed skills is the attack multiplier
    (Electrify 0.5 / Roar2 0.2); buff skills (AtkUp) deal no damage."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState

    def cast_damage(ek, pk, atk):
        sim = Simulator(level_id="level_main_01-01")
        sim.run_ticks(15)
        b = sim.battle
        b.max_cost = 100000.0; b.cost = 0.0; b.cost_increase_time = 1e7
        b.battle_cost_add(100.0)
        b.deploy("char_127_estell", 3, 4)
        op = b.operators[0]
        for _ in range(30):
            b.tick_once()
        op.max_hp = 1e9
        op.hp = 1e9
        op_def = float(op.attributes.get("def") or 0.0)
        e = b.spawn_enemy(ek, 0, overrides={
            "attributes": {"atk": atk}, "row": 3, "col": 8})
        e.state = EnemyState.COMBAT
        sc = e.skill_controller
        sk = next(s for s in sc.skills if s.prefab_key == pk)
        sc._start_cast((sk, op))
        b.events.log = []
        guard = 0
        while sc.casting is not None and guard < 600:
            b.tick_once()
            guard += 1
        dmg = [x["data"] for x in b.events.snapshot_events()
               if x["type"] == "damage" and
               x["data"].get("source") == e.inst_id and
               x["data"].get("target") == op.inst_id and
               x["data"].get("amount", 0.0) > 0.0]
        return max((d["amount"] for d in dmg), default=0.0), op_def

    atk = 100000.0
    el, op_def = cast_damage("enemy_1573_pyczog", "Electrify", atk)
    ro, _ = cast_damage("enemy_1573_pyczog", "Roar2", atk)
    assert abs(el - (atk * 0.5 - op_def)) < atk * 0.01, (el, op_def)
    assert abs(ro - (atk * 0.2 - op_def)) < atk * 0.01, (ro, op_def)
    au, _ = cast_damage("enemy_10209_mubag", "AtkUp", atk)
    assert au == 0.0, au


def test_enemy_negative_atk_key_applies_atk_debuff():
    """Negative bb 'atk' is a target atk debuff (AtkDesWeaken -0.5 ->
    x0.5, SandStorm -0.7 -> x0.3), measured inside the debuff window."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState

    def cast_and_read(ek, pk, read_ticks):
        sim = Simulator(level_id="level_main_01-01")
        sim.run_ticks(15)
        b = sim.battle
        b.max_cost = 100000.0; b.cost = 0.0; b.cost_increase_time = 1e7
        b.battle_cost_add(100.0)
        b.deploy("char_127_estell", 3, 4)
        op = b.operators[0]
        for _ in range(30):
            b.tick_once()
        op.max_hp = 1e9
        op.hp = 1e9
        atk0 = float(op.attributes.get("atk"))
        e = b.spawn_enemy(ek, 0, overrides={
            "attributes": {"atk": 1000.0}, "row": 3, "col": 8})
        e.state = EnemyState.COMBAT
        sc = e.skill_controller
        sk = next(s for s in sc.skills if s.prefab_key == pk)
        sc._start_cast((sk, op))
        guard = 0
        while sc.casting is not None and guard < 600:
            b.tick_once()
            guard += 1
        for _ in range(read_ticks):
            b.tick_once()
        return atk0, float(op.attributes.get("atk"))

    a0, a1 = cast_and_read("enemy_1104_lfkght", "AtkDesWeaken", 60)
    assert abs(a1 - a0 * 0.5) < 1.0, (a0, a1)
    s0, s1 = cast_and_read("enemy_1509_mousek", "SandStorm", 60)
    assert abs(s1 - s0 * 0.3) < 1.0, (s0, s1)


def test_enemy_atk_scale_variant_key():
    """Skills with only an atk_scale variant key use it as the multiplier
    (M0SplashCannon magic_atk_scale 3.0 -> atk x 3.0 MAGICAL)."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState, DamageType
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0; b.cost = 0.0; b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    for _ in range(30):
        b.tick_once()
    op.max_hp = 1e9
    op.hp = 1e9
    e = b.spawn_enemy("enemy_10047_shrknt", 0, overrides={
        "attributes": {"atk": 1000.0}, "row": 3, "col": 8})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    sk = next(s for s in sc.skills if s.prefab_key == "M0SplashCannon")
    sc._start_cast((sk, op))
    b.events.log = []
    guard = 0
    while guard < 600:
        b.tick_once()
        guard += 1
        if sc.casting is None and not b.projectiles:
            break
    dmg = [x["data"] for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("source") == e.inst_id and
           x["data"].get("target") == op.inst_id]
    assert dmg, "M0SplashCannon must deal damage on projectile hit"
    assert abs(dmg[-1]["amount"] - 3000.0) < 1.0, dmg[-1]
    assert dmg[-1]["type"] == DamageType.MAGICAL, dmg[-1]

