"""Native finite cards remain separate from the fixed twelve selected units."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_content_composition_v2 import compose_modules
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[3]
CARD='unit/ch7/predefined/mine/level1'


def package():
    roster=json.loads((ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json').read_bytes())
    mine=json.loads((ROOT/'packages/campaign/chapter07_predefines_consumer/mine.module.v2.json').read_bytes())
    definitions,_=compose_modules([('fixed12',roster),('native_mine',mine)])
    return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},
        'definitions':list(definitions.values()),'scenarioDraft':{
            'id':'scene/cards/native_mine_fixed12','ruleset':'ruleset/ark_standard',
            'map':{'rows':1,'cols':3},'objectives':{},'roster':deepcopy(roster['manifest']['metadata']['roster']),
            'cards':[CARD],'resources':{'dp':{'initial':10,'capacity':99},
                                      'stock_ch7_mine':{'initial':15,'capacity':15}},
            'parameters':{'deploy_capacity':9}}}


def test_public_native_card_fixed12_unchanged_and_reject_atomic(tmp_path):
    p=package();s=Engine.create(Compiler().compile(p),seed=7193)
    assert len(s.program.scenario['roster'])==12 and CARD not in s.program.scenario['roster']
    s.submit({'action':'deploy','entity':CARD,'row':0,'col':0,'alias':'mine1'},at=0)
    s.submit({'action':'deploy','entity':CARD,'row':0,'col':1,'alias':'mine2'},at=1)
    s.advance(2)
    assert s.ctx.resources.current('system/battle','stock_ch7_mine')==14
    assert s.ctx.resources.current('system/battle','dp')==5
    assert [e['type'] for e in s.session.events if e['type'].startswith('command.')]==['command.accepted','command.rejected']
    file=tmp_path/'cards2.json';pin=write_ordered(file,s.checkpoint());r=Engine.restore(s.program,load_bound(file,pin))
    s.advance(4);r.advance(4);assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay()).checkpoint()


def test_absent_cards_keeps_original_roster_gate():
    p=package();p['scenarioDraft'].pop('cards');p['scenarioDraft']['dependencies']=[CARD]
    s=Engine.create(Compiler().compile(p));s.submit({'action':'deploy','entity':CARD,'row':0,'col':0},at=0);s.advance(1)
    assert s.ctx.resources.current('system/battle','stock_ch7_mine')==15
    assert s.ctx.resources.current('system/battle','dp')==10
    assert any(e['type']=='command.rejected' for e in s.session.events)


@pytest.mark.parametrize('value',[True,'unit/not_a_list',[CARD,CARD],[False]])
def test_cards_typed_and_unique_declaration(value):
    p=package();p['scenarioDraft']['cards']=value
    with pytest.raises(ValueError):Compiler().compile(p)


def test_card_definition_cannot_overlap_selected_roster():
    p=package();p['scenarioDraft']['cards']=[p['scenarioDraft']['roster'][0]]
    with pytest.raises(ValueError,match='disjoint'):Compiler().compile(p)


@pytest.mark.parametrize('mutation',['missing_stock_resource','bool_initial','wrong_definition_kind','missing_deployable'])
def test_card_required_stock_and_definition_preflight(mutation):
    p=package();unit=next(d for d in p['definitions'] if d['id']==CARD)
    if mutation=='missing_stock_resource':p['scenarioDraft']['resources'].pop('stock_ch7_mine')
    elif mutation=='bool_initial':p['scenarioDraft']['resources']['stock_ch7_mine']['initial']=True
    elif mutation=='wrong_definition_kind':p['scenarioDraft']['cards']=[next(d['id'] for d in p['definitions'] if d['kind']=='buff')]
    else:unit['components'].pop('deployable')
    with pytest.raises(ValueError):Compiler().compile(p)
