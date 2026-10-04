from copy import deepcopy
import json
from pathlib import Path

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_tile_fields import build, state
from tools.campaign_ordered_checkpoint import write_ordered, load_bound

ROOT=Path(__file__).resolve().parents[1]


def fixture(key='tile_healing'):
    p=build();operands=json.loads((ROOT/'packages/campaign/chapter02_tiles/buffs.motion_state.partial.json').read_bytes())
    p['buffs']+=operands['buffs'];p['rules']+=operands['rules']
    board=({'HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO':.03} if key=='tile_healing' else {'atk_scale':1.7,'attack_speed':-20.0})
    target={'id':'unit/test_target','kind':'entity','tags':['player','ground'],
        'components':{'spatial':{},'selection_state':state(),
        'attributes':{'base':{'max_hp':1000,'atk':100,'def':0,'mres':0,'hp_ratio_recovery':0,'attack_speed_ratio':1}},
        'resources':{'hp':{'initial':500,'capacity_attribute':'max_hp','role':'health','recovery_rule':'rule/ch2/tile_hp_ratio_recovery','recovery':{'mode':'continuous'}}},
        'abilities':['ability/test_enter','ability/test_leave']}}
    p['entities'].append(target)
    p['abilities']=[{'id':'ability/test_'+name,'kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'move','target':'source','position':{'row':0,'col':col}}]},'timeline':[]} for name,col in [('enter',1),('leave',2)]]
    p['scenarioDraft']={'id':'scene/test/reference_field','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':1,'cols':3,'tiles':[{'tileKey':'tile_floor','buildableType':1,'passableMask':1},
            {'tileKey':key,'buildableType':1,'passableMask':1,'blackboard':board},
            {'tileKey':'tile_floor','buildableType':1,'passableMask':1}],
            'tile_mechanics':{key:{'type':'occupancy_buff_field','definition':'unit/ch2/field/'+key,'expected_blackboard':board}}},
        'initialEntities':[{'definition':target['id'],'instanceAlias':'target','position':{'row':0,'col':0}}]}
    return p


def test_source_healing_entry_leave_and_saved_checkpoint_replay(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=42001)
    s.submit({'action':'skill','source':'target','ability':'ability/test_enter'},at=3)
    s.submit({'action':'skill','source':'target','ability':'ability/test_leave'},at=33)
    s.advance(20);path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint())
    restored=Engine.restore(s.program,load_bound(path,pin));s.advance(15);restored.advance(15)
    assert s.ctx.resources.current('target','hp')==pytest.approx(530)
    assert s.ctx.get('target',('buffs','instances'))==[]
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay()).snapshot()


@pytest.mark.parametrize('patch',[{'side':1},{'category':2},{'target_free':True},{'ally_target_free':True},{'camouflage':True}])
def test_source_masks_and_live_free_flags_exclude_ineligible_members(patch):
    p=fixture();p['entities'][-1]['components']['selection_state'].update(patch)
    p['scenarioDraft']['initialEntities'][0]['position']['col']=1
    s=Engine.create(Compiler().compile(p));s.advance(30)
    assert s.ctx.resources.current('target','hp')==500
    assert s.ctx.get('target',('buffs','instances'))==[]


def test_all_motion_source_mask_accepts_typed_flying_ally():
    p=fixture();p['entities'][-1]['components']['selection_state']['motion']=2
    p['scenarioDraft']['initialEntities'][0]['position']['col']=1
    s=Engine.create(Compiler().compile(p));s.advance(30)
    assert s.ctx.resources.current('target','hp')==pytest.approx(530)


def test_gazebo_applies_attack_speed_and_clears_on_same_frame_exit():
    s=Engine.create(Compiler().compile(fixture('tile_gazebo')))
    s.submit({'action':'skill','source':'target','ability':'ability/test_enter'},at=0)
    s.advance(1);assert s.ctx.attributes.value('target','attack_speed_ratio')==pytest.approx(.8)
    s.submit({'action':'skill','source':'target','ability':'ability/test_leave'},at=1)
    s.advance(1);assert s.ctx.attributes.value('target','attack_speed_ratio')==1
    # Attribute evaluation emits calculation evidence. Reproduce the public
    # queries at the same ticks instead of comparing to a query-free replay.
    record=s.export_replay();record['until']=1;record['commands']=record['commands'][:1]
    restored=replay(s.program,record)
    assert restored.ctx.attributes.value('target','attack_speed_ratio')==pytest.approx(.8)
    restored.submit({'action':'skill','source':'target','ability':'ability/test_leave'},at=1)
    restored.advance(1)
    assert restored.ctx.attributes.value('target','attack_speed_ratio')==1
    assert s.snapshot()==restored.snapshot()


def test_actual_field_owner_drives_typed_air_damage_hook_and_exit_removal():
    p=fixture('tile_gazebo')
    p['entities'][-1]['components']['abilities']+=['ability/test_hit_ground','ability/test_hit_fly']
    for name,motion,col in [('ground',1,0),('fly',2,2)]:
        target={'id':'unit/test_'+name,'kind':'entity','tags':['enemy','test_target_'+name],
            'components':{'spatial':{},'selection_state':{**state(),'side':1,'motion':motion,'unit_type':2},
                'attributes':{'base':{'max_hp':1000,'def':10,'mres':0}},
                'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}}}}
        p['entities'].append(target)
        p['scenarioDraft']['initialEntities'].append({'definition':target['id'],'instanceAlias':name,'position':{'row':0,'col':col}})
        p['selectors'].append({'id':'selector/test_'+name,'kind':'selector','region':{'type':'all'},'filters':[{'tag':'test_target_'+name},{'state':'alive'}]})
        p['abilities'].append({'id':'ability/test_hit_'+name,'kind':'ability','selector':'selector/test_'+name,
            'activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]})
    s=Engine.create(Compiler().compile(p),seed=42002)
    for tick,ability in [(0,'enter'),(1,'hit_ground'),(2,'hit_fly'),(3,'leave'),(4,'hit_fly')]:
        s.submit({'action':'skill','source':'target','ability':'ability/test_'+ability},at=tick)
    s.advance(5)
    hits=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']
    assert hits==[90,160,90]
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
