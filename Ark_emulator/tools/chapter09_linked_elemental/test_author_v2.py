"""Actual waiting casts and linked health/EP packets on an isolated candidate."""
import json
import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_c9_linked_elemental_v2_candidate'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter09_linked_elemental.fixture_v2 import fixture, providers


def create(**options):
    sim = Engine.create(Compiler(providers=providers()).compile(fixture(**options)), seed=90713, providers=providers())
    sim.submit({'action': 'skill', 'source': 'source', 'ability': 'ability/linked/fire'}, at=2)
    return sim


def events(sim, kind):
    return [thaw(e) for e in sim.session.events if e['type'] == kind]


def attachment(sim):
    return next(iter(sim.ctx.attachments.state()['instances'].values()))


def test_native_scales_independent_health_and_ep_three_halfsecond_packets():
    sim = create(); sim.advance(63)
    assert [e['time'] for e in events(sim, 'damage.accepted')] == [5, 20, 35]
    assert sim.ctx.resources.current('target', 'hp') == 4856
    assert sim.ctx.get('target', ('runtime', 'elemental', 'remaining', 'FIRE')) == 910
    assert attachment(sim)['packets'] == 3 and attachment(sim)['reason'] == 'complete'
    assert not sim.ctx.get('source', ('runtime', 'casts'))


def test_current_attributes_for_later_health_and_ep_packets():
    sim = create(); sim.advance(6)
    sim.ctx.set('source', ('attributes', 'base', 'atk'), 1000)
    sim.ctx.set('target', ('attributes', 'base', 'mres'), 50)
    sim.advance(15)
    assert sim.ctx.resources.current('target', 'hp') == 4892
    assert sim.ctx.get('target', ('runtime', 'elemental', 'remaining', 'FIRE')) == 910


def test_source_silence_cancels_link_before_next_packet():
    sim = create(); sim.advance(6)
    sim.ctx.set('source', ('selection_state', 'abnormal_flags'), [12]); sim.advance(16)
    assert len(events(sim, 'damage.accepted')) == 1
    assert not attachment(sim)['active'] and attachment(sim)['reason'] == 'source_flags'


def test_target_death_skips_ep_and_cancels_link():
    sim = create(hp=40); sim.advance(6)
    assert sim.ctx.get('target', ('runtime', 'state')) == 'dead'
    assert not events(sim, 'elemental.loss.accepted') and not attachment(sim)['active']


def test_compound_integral_is_explicitly_rejected():
    with pytest.raises(ValueError, match='damage_integral false'):
        Compiler(providers=providers()).compile(fixture(integral=True))


def test_actual_disk_checkpoint_in_flight_and_held_public_head(tmp_path):
    sim = create(); sim.advance(3)
    path = tmp_path / 'flight.checkpoint.json'; path.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    restored = Engine.restore(sim.program, json.loads(path.read_bytes()), providers=providers())
    sim.advance(3); restored.advance(3)
    assert sim.checkpoint() == restored.checkpoint()
    path = tmp_path / 'held.checkpoint.json'; path.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    held = Engine.restore(sim.program, json.loads(path.read_bytes()), providers=providers())
    sim.advance(50); restored.advance(50); held.advance(50)
    assert sim.checkpoint() == restored.checkpoint() == held.checkpoint()
    assert sim.snapshot() == replay(sim.program, sim.export_replay(), providers=providers()).snapshot()


def test_duplicate_unowned_step_does_not_consume_packet():
    sim = create(); sim.advance(6); before = sim.checkpoint(); record = attachment(sim)
    sim.ctx.attachments.step(sim.session, {'attachment': record['id'], 'generation': record['generation']})
    assert sim.checkpoint() == before


def test_break_lock_blocks_only_ep_while_health_packets_continue():
    sim = create(capacity=30); sim.advance(48)
    assert [e['time'] for e in events(sim, 'damage.accepted')] == [5, 20, 35]
    assert len(events(sim, 'elemental.loss.accepted')) == 1
    assert len(events(sim, 'linked.break')) == 1
    assert sim.ctx.resources.current('target', 'hp') == 4856
    assert sim.ctx.get('target', ('runtime', 'elemental', 'remaining', 'FIRE')) == 0


def test_bad_element_packet_rolls_back_health_and_attachment_packet_cursor():
    data = fixture()
    next(r for r in data['rules'] if r['id'] == 'rule/linked/packet')['implementation']['expression'] = '-1'
    sim = Engine.create(Compiler(providers=providers()).compile(data), providers=providers())
    sim.submit({'action': 'skill', 'source': 'source', 'ability': 'ability/linked/fire'}, at=2)
    sim.advance(5)
    with pytest.raises(ValueError):
        sim.advance(1)
    assert sim.ctx.resources.current('target', 'hp') == 5000
    assert sim.ctx.get('target', ('runtime', 'elemental', 'remaining', 'FIRE')) == 1000
    assert attachment(sim)['packets'] == 0
    assert not events(sim, 'damage.accepted') and not events(sim, 'elemental.loss.accepted')


def test_motion_clock_reaches_before_independent_halfsecond_packet_clock():
    sim = create(); sim.advance(5)
    assert attachment(sim)['state'] == 'flight' and attachment(sim)['packets'] == 0
    sim.advance(1)
    assert events(sim, 'attachment.reached')[0]['time'] == 5
    assert attachment(sim)['next_packet'] == 20
    sim.advance(14)
    assert attachment(sim)['packets'] == 1 and sim.ctx.resources.current('target', 'hp') == 4952
    sim.advance(1)
    assert attachment(sim)['packets'] == 2 and sim.ctx.resources.current('target', 'hp') == 4904


def test_legacy_damage_only_profile_keeps_per_step_integral_semantics():
    data = fixture()
    attachment_profile = data['definitions'][0]
    attachment_profile.pop('hit_interval_seconds')
    attachment_profile['effect'] = attachment_profile['effect']['health_effect']
    attachment_profile['damage_integral'] = True
    sim = Engine.create(Compiler(providers=providers()).compile(data), providers=providers())
    sim.submit({'action': 'skill', 'source': 'source', 'ability': 'ability/linked/fire'}, at=2)
    sim.advance(8)
    assert [e['time'] for e in events(sim, 'damage.accepted')] == [5, 6, 7]
    assert sim.ctx.resources.current('target', 'hp') == pytest.approx(4995.2)
    assert 'next_packet' not in attachment(sim)


def test_zero_packet_interval_rejected_before_runtime():
    data = fixture(); data['definitions'][0]['hit_interval_seconds'] = 0
    with pytest.raises(ValueError, match='finite positive'):
        Compiler(providers=providers()).compile(data)
