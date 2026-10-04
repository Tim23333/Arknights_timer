"""Actual source casting state timing with life and EP packets."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / 'unpack_work/campaign_c9_ability_clock_v1_candidate')); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from tools.chapter09_ability_clock_v1.flame_channel import package, providers


def sim():
    return Engine.create(Compiler(providers=providers()).compile(package()), providers=providers())


def test_source6second_cooldown_and10point6_state_end_cancels_link():
    s = sim(); s.advance(182)
    updates = [(e['time'], e['payload']['ready_at']) for e in s.session.events if e['type'] == 'ability.cooldown.updated']
    assert updates[:2] == [(0, 0), (180, 480)]
    hits = [e['time'] for e in s.session.events if e['type'] == 'damage.accepted']
    assert hits[:3] == [18, 33, 48]
    s.advance(137)
    assert s.ctx.get('source', ('runtime', 'cooldowns', 'ability/linked/fire')) == 618
    assert not s.ctx.get('source', ('runtime', 'casts'))
    assert not next(iter(s.ctx.attachments.state()['instances'].values()))['active']
    assert [e['time'] for e in s.session.events if e['type'] == 'damage.accepted'] == list(range(18, 318, 15))
    assert s.ctx.resources.current('target', 'hp') == 20000 - 20 * 48
    assert s.ctx.get('target', ('runtime', 'elemental', 'remaining', 'FIRE')) == 400


def test_silence_interrupt_cleans_cast_and_restarts_real_cooldown():
    s = sim(); s.advance(34)
    before = len([e for e in s.session.events if e['type'] == 'damage.accepted'])
    s.ctx.set('source', ('selection_state', 'abnormal_flags'), [12]); s.advance(1)
    assert not s.ctx.get('source', ('runtime', 'casts'))
    assert s.ctx.get('source', ('runtime', 'cooldowns', 'ability/linked/fire')) == 334
    s.advance(30)
    assert len([e for e in s.session.events if e['type'] == 'damage.accepted']) == before
