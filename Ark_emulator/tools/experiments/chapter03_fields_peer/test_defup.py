import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
    p=json.loads((ROOT/'packages/campaign/chapter03_tiles/defup.reference_model.json').read_bytes())
    target={'id':'unit/peer/victim','kind':'entity','tags':['player','token','victim'],'components':{'spatial':{},'selection_state':{'side':0,'category':2,'motion':2},
        'attributes':{'base':{'max_hp':10000,'def':40,'mres':40}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'buffs':{'initial':['buff/peer/ratio']},'abilities':['ability/next','ability/leave']}}
    caster={'id':'unit/peer/attacker','kind':'entity','components':{'spatial':{},'attributes':{'base':{'atk':880}},'abilities':['ability/physical','ability/arts']}}
    p['entities'] += [target,caster];p['buffs'].append({'id':'buff/peer/ratio','kind':'buff','modifiers':[{'attribute':'def','layer':'direct_ratio','value':.5}]})
    p['selectors'].append({'id':'selector/peer/victim','kind':'selector','region':{'type':'all'},'filters':[{'tag':'victim'}]})
    p['abilities']=[{'id':'ability/'+name,'kind':'ability','selector':'selector/peer/victim','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':name}]},'timeline':[]} for name in ('physical','arts')]
    p['abilities'] += [{'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':col}}]},'timeline':[]} for name,col in [('next',2),('leave',3)]]
    tiles=[{'tileKey':'tile_floor','passableMask':1,'buildableType':1}]+[{'tileKey':'defense_custom','passableMask':3,'buildableType':2,'blackboard':{'def':200.0}}]*2+[{'tileKey':'tile_floor','passableMask':1,'buildableType':1}]
    p['scenarioDraft']={'id':'scene/peer/def200','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':4,'tiles':tiles,'tile_mechanics':{'defense_custom':{'type':'occupancy_buff_field','definition':'unit/ch3/field/defup','expected_blackboard':{'def':200.0}}}},
        'initialEntities':[{'definition':target['id'],'instanceAlias':'victim','position':{'row':0,'col':1}},{'definition':caster['id'],'instanceAlias':'attacker','position':{'row':0,'col':0}}]}
    return p

def test_flying_token_category2_field_flat_def_composes_with_own_ratio_across_sources(tmp_path):
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=3503)
    for at,source,ability in [(0,'attacker','physical'),(1,'victim','next'),(2,'attacker','physical'),(3,'victim','leave'),(4,'attacker','physical')]:s.submit({'action':'skill','source':source,'ability':'ability/'+ability},at=at)
    s.advance(2);path=tmp_path/'def.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(4);r.advance(4)
    # (40+200)*1.5=360 on either field; own ratio persists after leaving:40*1.5=60.
    assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[520,520,820]
    assert s.ctx.resources.current('victim','hp')==8140 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
    fields=s.ctx.state()['tile_fields'];assert fields['0:1']['owner']!=fields['0:2']['owner']
    assert [i['definition'] for i in s.ctx.get('victim',('buffs','instances'))]==['buff/peer/ratio']

def test_DEF_field_does_not_fabricate_magic_resistance():
    p=fixture();s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'attacker','ability':'ability/arts'},at=0);s.advance(1)
    assert s.ctx.resources.current('victim','hp')==pytest.approx(10000-880*.6)

@pytest.mark.parametrize('category,damage',[(1,520),(2,520),(4,820)])
def test_native_category_mask3_differs_from_chapter2_character_only_mask(category,damage):
    p=fixture();p['entities'][-2]['components']['selection_state']['category']=category
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'attacker','ability':'ability/physical'},at=0);s.advance(1)
    assert s.ctx.resources.current('victim','hp')==10000-damage

def test_actual_raw_tile_component_qualification_is_bound_not_only_metadata():
    import UnityPy
    plan=json.loads((ROOT/'packages/campaign/chapter03_plans/source.plan.json').read_bytes());prefab=plan['selected_native_prefabs']['tile_defup'];path=ROOT.parent/prefab['source']['path'];objects={o.path_id:o for o in UnityPy.load(str(path)).objects}
    pid,row=next((int(pid),r) for pid,r in prefab['components'].items() if r['native_class']=='BuffTile');actual=objects[pid].read_typetree()
    assert actual==row['raw'] and actual['_targetOptions']['targetCategory']==3 and actual['_targetOptions']['targetMotion']==3
    p=fixture();configuration=p['selectors'][0]['eligibility']['parameters']['source_configuration']
    assert configuration['_targetCategory']==actual['_targetOptions']['targetCategory'] and configuration['_targetMotion']==actual['_targetOptions']['targetMotion']
