"""Candidate-only regressions; run against the isolated runtime until integration."""
import pytest

from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from test_m8_timeline import data, spawn, wave


@pytest.mark.parametrize('where', ['same_fragment', 'next_fragment', 'next_wave', 'initial', 'suffix'])
def test_duplicate_timeline_alias_rejected_before_world_creation(where):
    a = spawn('duplicate', blocks_wave=False)
    d = data([wave([a])])
    b = spawn('duplicate', blocks_wave=False)
    if where == 'same_fragment':
        d['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append(b)
    elif where == 'next_fragment':
        d['scenarioDraft']['timeline']['waves'][0]['fragments'].append({'pre_delay_seconds': 0, 'actions': [b]})
    elif where == 'next_wave':
        d['scenarioDraft']['timeline']['waves'].append(wave([b]))
    elif where == 'initial':
        d['scenarioDraft']['initialEntities'] = [{'definition': 'unit/timeline', 'instanceAlias': 'duplicate'}]
    else:
        a['count'] = 2
        b['spawn']['instanceAlias'] = 'duplicate/1'
        d['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append(b)
    with pytest.raises(ValueError, match='duplicate instance alias'):
        Compiler().compile(d)


@pytest.mark.parametrize('alias', ['', 0, False, [], {}])
def test_nonstring_or_empty_alias_rejects_compile(alias):
    a = spawn(alias, blocks_wave=False)
    with pytest.raises(ValueError, match='nonempty instance alias'):
        Compiler().compile(data([wave([a])]))


def test_flat_wave_alias_collides_with_initial_or_reserved_system():
    for alias in ('duplicate', 'system/battle'):
        d = data([])
        d['scenarioDraft'].pop('timeline')
        d['scenarioDraft']['initialEntities'] = [{'definition': 'unit/timeline', 'instanceAlias': 'duplicate'}]
        d['scenarioDraft']['waves'] = [{'at': 30, 'definition': 'unit/timeline', 'instanceAlias': alias}]
        with pytest.raises(ValueError, match='duplicate instance alias'):
            Compiler().compile(d)


def test_repeated_base_is_free_and_distinct_generated_aliases_execute():
    a = spawn('repeat', blocks_wave=False); a['count'] = 2
    d = data([wave([a, spawn('repeat', blocks_wave=False), spawn(None, blocks_wave=False)])])
    sim = Engine.create(Compiler().compile(d)); sim.advance(1)
    assert len({sim.session.world.resolve(x) for x in ('repeat', 'repeat/0', 'repeat/1')}) == 3
    assert sim.ctx.state()['pending_waves'] == 0


def test_alias_retirement_does_not_release_alias_for_new_birth():
    d = data([wave([spawn('reused', blocks_wave=False)]), wave([spawn('reused', blocks_wave=False)])])
    with pytest.raises(ValueError, match='duplicate instance alias'):
        Compiler().compile(d)


def test_resource_alias_and_integer_events_share_actor_identity():
    d = data([])
    d['scenarioDraft']['initialEntities'] = [{'definition': 'unit/timeline', 'instanceAlias': 'actor'}]
    s = Engine.create(Compiler().compile(d))
    ref = s.session.world.resolve('actor')
    s.ctx.resources.adjust('actor', 'hp', delta=-1, source='actor')
    alias_payload = thaw([e for e in s.session.events if e['type'] == 'resource.changed'][-1]['payload'])
    s.ctx.resources.adjust(ref, 'hp', delta=-1, source=ref)
    integer_payload = thaw([e for e in s.session.events if e['type'] == 'resource.changed'][-1]['payload'])
    assert alias_payload['source'] == alias_payload['target'] == ref
    assert integer_payload['source'] == integer_payload['target'] == ref
    assert alias_payload['value'] == 99 and integer_payload['value'] == 98


def test_unknown_source_is_rejected_before_resource_write_or_event():
    d = data([])
    d['scenarioDraft']['initialEntities'] = [{'definition': 'unit/timeline', 'instanceAlias': 'actor'}]
    s = Engine.create(Compiler().compile(d)); before = s.checkpoint()
    with pytest.raises(KeyError, match='Unknown entity alias'):
        s.ctx.resources.adjust('actor', 'hp', delta=-1, source='absent')
    assert s.checkpoint() == before
