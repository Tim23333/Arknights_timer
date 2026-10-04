"""Actual 1-11 predefine and shared time-SP interoperability."""
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_chapter01_dormant_model import build


def test_actual_stage_npc_registered_then_same_actor_activated_and_counts_capacity():
    p = build(); sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()['predefined_registry']['char_211_adnach']
    assert sim.ctx.alive(ref) and not sim.ctx.active(ref)
    assert sim.ctx.resources.current(ref, 'hp') == 677 and sim.ctx.resources.current(ref, 'sp') == 0
    assert sim.ctx.get(ref, ('deployable', 'capacity')) == 1
    assert ref not in sim.checkpoint()['kernel']['world']['aliases'].values()
    sim.advance(89); cp = sim.checkpoint(); sim.advance(31)
    assert sim.ctx.active(ref) and sim.ctx.state()['predefined_registry']['char_211_adnach'] == ref
    assert sim.ctx.resources.current(ref, 'sp') == 1
    assert sim.ctx.state()['pending_waves'] == 44
    assert [(e['time'], e['payload']['target']) for e in sim.session.events if e['type'] == 'entity.activated'] == [(90, ref)]
    restored = Engine.restore(sim.program, cp); restored.advance(31)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(restored.session.events)) is None
    replayed = replay(sim.program, sim.export_replay())
    assert first_difference(sim.snapshot(), replayed.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(replayed.session.events)) is None


def test_actual_time_sp_npc_joins_ptilopsis_aura_only_after_activation():
    p = build(); p['scenarioDraft']['timeline']['waves'][0]['fragments'] = p['scenarioDraft']['timeline']['waves'][0]['fragments'][:2]
    # Preserve actual predefine/controls; isolate the real passive as initially
    # deployed, without silently turning this into a whole-stage proof.
    p['scenarioDraft']['initialEntities'].append({'definition': 'unit/char_128_plosis', 'position': {'row': 0, 'col': 0}, 'deployed': True})
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()['predefined_registry']['char_211_adnach']
    sim.advance(90)
    assert sim.ctx.resources.current(ref, 'sp') == 0
    assert sim.ctx.get(ref, ('buffs', 'instances')) == []
    sim.advance(30)
    assert abs(sim.ctx.resources.current(ref, 'sp')-1.3) < 1e-12
    assert abs(sim.ctx.attributes.value(ref, 'sp_recovery_rate')-1.3) < 1e-12
