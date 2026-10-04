"""Generic field scope/bit predicates consume actual definition metadata."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m15_category_candidate'
sys.path.insert(0,str(RUNTIME))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay


def scene(value='missing',predicate=None):
    data=json.loads((ROOT/'packages/campaign/chapter01_devices/emp.category.json').read_bytes())
    data['scenarioDraft']['initialEntities'][0]['components']={'resources':{'sp':{'initial':5}}}
    enemy={'id':'unit/field_enemy','kind':'entity','tags':['enemy','ground'],
        'components':{'attributes':{'base':{'max_hp':3000,'def':0,'mres':20}},'spatial':{},
            'resources':{'hp':{'initial':3000,'capacity':3000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    if value!='missing':enemy['metadata']={'native_category':value}
    data['entities'].append(enemy)
    data['scenarioDraft']['initialEntities'].append({'definition':enemy['id'],'instanceAlias':'enemy','position':{'row':5,'col':6}})
    if predicate is not None:data['selectors'][0]['filters'][-1]={'field':predicate}
    return data


@pytest.mark.parametrize('value,hits',[('missing',1),(1,1),(2,0),(3,1),(4,0),(0,0),(True,0),('1',0),(None,0)])
def test_native_default_mask_bit_test_in_definition_scope(value,hits):
    s=Engine.create(Compiler().compile(scene(value)),seed=15)
    uid=next(e['id'] for e in s.session.world.entities() if e['definition_id']=='unit/chapter01_emp')
    s.submit({'action':'skill','source':uid,'ability':'ability/chapter01_emp/burst'});s.advance(24)
    packets=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(packets)==hits and s.ctx.resources.current('enemy','hp')==3000-800*hits
    assert 'metadata' not in s.ctx.entity('enemy') # field predicate read the definition deliberately
    cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


@pytest.mark.parametrize('scope,hits',[('runtime',1),('definition',0)])
def test_missing_runtime_metadata_is_distinct_from_definition_metadata(scope,hits):
    p=scene(2,{'scope':scope,'path':['metadata','native_category'],'equals':1,'default':1})
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':2,'ability':'ability/chapter01_emp/burst'});s.advance(24)
    assert len([e for e in s.session.events if e['type']=='damage.accepted'])==hits


@pytest.mark.parametrize('predicate',[
    {'scope':'unknown','path':['metadata'],'equals':1},
    {'path':[],'equals':1},{'path':[True],'equals':1},{'path':[-1],'equals':1},
    {'path':['metadata'],'equals':1,'bits_any':1},{'path':['metadata']},
    {'path':['metadata'],'bits_any':True},{'path':['metadata'],'bits_any':-1},
    {'path':['metadata'],'equals':{}},{'path':['metadata'],'equals':1,'default':[]}])
def test_invalid_field_operator_path_mask_or_scope_rejected(predicate):
    with pytest.raises(ValueError):Compiler().compile(scene(1,predicate))
