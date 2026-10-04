"""Adversarial checks for explicit W profiles, separate from native verification."""
import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_chapter01_w_model import build, fixture, C4, MODE


def manual_scene(positions=((3, 4),), mode=0):
    data = fixture(build(), positions=positions, automatic=False)
    resources = data['entities'][0]['components']['resources']
    resources['mode']['initial'] = mode
    resources[f'c4_clock_{mode}']['initial'] = 20
    return data


def start(sim, mode=0):
    sim.submit({'action': 'skill', 'source': 'w', 'ability': C4+str(mode)})
    sim.advance(1)


@pytest.mark.parametrize('hp,expected', [(5001, 0), (5000, 1), (4999, 1)])
def test_boundary_is_inclusive_model_and_never_invents_atk_up(hp, expected):
    sim = Engine.create(Compiler().compile(fixture(build(), positions=(), automatic=False)))
    sim.ctx.resources.adjust(sim.session.world.resolve('w'), 'hp', value=hp)
    sim.advance(2)
    assert sim.ctx.resources.current('w', 'mode') == expected
    assert sim.ctx.attributes.values('w')['atk'] == 470
    assert any(b['definition'] == MODE for b in sim.ctx.get('w', ('buffs', 'instances'), [])) == bool(expected)


def test_dead_hp_does_not_create_second_mode_or_bombs():
    sim = Engine.create(Compiler().compile(fixture(build(), positions=(), automatic=False)))
    sim.ctx.resources.adjust(sim.session.world.resolve('w'), 'hp', value=0)
    sim.advance(2)
    assert not sim.ctx.alive('w')
    assert sim.ctx.resources.current('w', 'mode') == 0
    assert not [e for e in sim.session.events if e['type'] == 'ability.started']


def test_bomb_uses_target_position_at_explosion_and_source_attack_at_cast():
    sim = Engine.create(Compiler().compile(manual_scene(((3, 4), (8, 8)))))
    start(sim)
    # Move captured target beside a previously out-of-range recipient. Changing
    # source ATK after casting must not rewrite its frozen attack operand.
    sim.ctx.set('target0', ('spatial', 'position'), {'row': 8, 'col': 7})
    sim.ctx.set('w', ('attributes', 'base', 'atk'), 1000)
    sim.advance(114)
    assert [sim.ctx.resources.current(f'target{i}', 'hp') for i in range(2)] == [4254, 4254]


def test_dead_captured_actor_retains_explosion_center_in_this_profile():
    sim = Engine.create(Compiler().compile(manual_scene(((3, 4), (3, 5)))))
    start(sim)
    sim.ctx.lifecycle.retire('target0', 'withdrawn')
    sim.advance(114)
    assert not sim.ctx.alive('target0')
    assert sim.ctx.resources.current('target1', 'hp') == 4254
    # Source death is a different explicit policy and cancels pending cast work.
    dead = Engine.create(Compiler().compile(manual_scene()))
    start(dead)
    dead.ctx.lifecycle.retire('w', 'dead')
    dead.advance(114)
    assert dead.ctx.resources.current('target0', 'hp') == 5000


def test_half_hp_during_c4_keeps_existing_bomb_and_restore_resets_default_clock():
    sim = Engine.create(Compiler().compile(manual_scene()))
    start(sim)
    sim.ctx.resources.adjust(sim.session.world.resolve('w'), 'hp', value=5000)
    sim.advance(2)
    assert sim.ctx.resources.current('w', 'mode') == 1
    assert any(c['ability'] == C4+'0' for c in sim.ctx.get('w', ('runtime', 'casts')).values())
    sim.ctx.resources.adjust(sim.session.world.resolve('w'), 'hp', value=5001)
    sim.advance(2)
    assert sim.ctx.resources.current('w', 'mode') == 0
    # Resource recovery precedes the passive reset in that tick; only the next
    # tick contributes a new quantum after the reset to11.
    assert sim.ctx.resources.current('w', 'c4_clock_0') == pytest.approx(11+1/30)
    sim.advance(110)
    assert sim.ctx.resources.current('target0', 'hp') == 4254


def test_three_captured_bombs_overlap_without_deduplicating_area_members():
    data = manual_scene(((3, 4),)*4, mode=1)
    program = Compiler().compile(data)
    sim = Engine.create(program)
    start(sim, mode=1)
    sim.advance(49)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(65); restored.advance(65)
    assert [sim.ctx.resources.current(f'target{i}', 'hp') for i in range(4)] == [2762]*4
    assert len([e for e in sim.session.events if e['type'] == 'damage.accepted']) == 12
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def test_partial_boss_metadata_does_not_claim_native_callback_or_stage_completion():
    meta = build()['manifest']['metadata']
    assert meta['full_enemy_implemented'] is False
    assert meta['formal_stage_approved'] is False
    assert 'normal_attack_not_authored' in meta['model_gaps']
    assert 'native_C4_projectile_attach_callbacks_and_expiry_not_recovered' in meta['client_pending']
    assert not build()['buffs'][0].get('modifiers')
