"""Caster mode1 reads its own 2.5 range and preserves one area per cast."""
import pytest
from ark_sim import Compiler,Engine
from tools.chapter07_join.test_demons_current_v1 import package,NAMES


@pytest.mark.parametrize('name,attack',[(NAMES[1],350),(NAMES[2],450)])
def test_true_mode1_range_two_unequal_positions_one_cast_area(name,attack):
    p=package(name)
    p['entities'].append({'id':'unit/peer/demons/far','kind':'entity','tags':['player','ground'],
        'components':{'attributes':{'base':{'max_hp':19000,'atk':0,'def':331,'mres':43}},
            'resources':{'hp':{'initial':19000,'capacity':19000,'role':'health'}},
            'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},
            'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/demons/far',
        'instanceAlias':'far','position':{'row':0,'col':2.25}})
    p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':{'op':'transition','state':'mode1','selector':'selector/demons/peer/source'}}]
    s=Engine.create(Compiler().compile(p),seed=7195)
    s.submit({'action':'deploy','entity':'unit/peer/demons/recipient','row':0,'col':0,'alias':'recipient'},at=0)
    s.advance(2)
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    areas=[e for e in s.session.events if e['type']=='area.resolved']
    assert len(areas)==1 and len(hits)==2
    amounts={e['payload']['target']:e['payload']['amount'] for e in hits}
    assert amounts[s.session.world.resolve('recipient')]==pytest.approx(attack*.73)
    assert amounts[s.session.world.resolve('far')]==pytest.approx(attack*.57)
    assert s.ctx.get('enemy',('behavior','state'))=='mode1'
    assert all(e['payload']['ability'].endswith('/immo1') for e in hits)
