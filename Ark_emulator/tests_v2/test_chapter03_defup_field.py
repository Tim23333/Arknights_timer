from copy import deepcopy

import pytest

from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter03_defup_field import build
from tools.build_chapter02_tile_fields import state
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture():
    p=build();unit={'id':'unit/test_def_target','kind':'entity','tags':['test_target','player'],
        'components':{'spatial':{},'selection_state':{**state(),'category':2},'attributes':{'base':{'max_hp':3000,'def':100,'mres':0}},
            'resources':{'hp':{'initial':3000,'capacity':3000,'role':'health'}},'abilities':['ability/leave']}}
    caster={'id':'unit/test_caster','kind':'entity','components':{'spatial':{},'attributes':{'base':{'atk':1000}},'abilities':['ability/shot']}}
    p['entities'] += [unit,caster];p['selectors'].append({'id':'selector/test_target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'test_target'}]})
    p['abilities']=[{'id':'ability/shot','kind':'ability','selector':'selector/test_target','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]},
        {'id':'ability/leave','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':2}}]},'timeline':[]}]
    p['scenarioDraft']={'id':'scene/test/defup200','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3,'tiles':[
        {'tileKey':'tile_floor','buildableType':1,'passableMask':1},{'tileKey':'arbitrary_defense_cell','buildableType':2,'passableMask':3,'blackboard':{'def':200.0}},
        {'tileKey':'tile_floor','buildableType':1,'passableMask':1}],
        'tile_mechanics':{'arbitrary_defense_cell':{'type':'occupancy_buff_field','definition':'unit/ch3/field/defup','expected_blackboard':{'def':200.0}}}},
        'initialEntities':[{'definition':unit['id'],'instanceAlias':'target','position':{'row':0,'col':1}},
            {'definition':caster['id'],'instanceAlias':'caster','position':{'row':0,'col':0}}]}
    return p


def test_source_flat_def200_true_damage_values_enter_leave_disk_replay(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=3500)
    s.submit({'action':'skill','source':'caster','ability':'ability/shot'},at=1)
    s.submit({'action':'skill','source':'target','ability':'ability/leave'},at=2)
    s.submit({'action':'skill','source':'caster','ability':'ability/shot'},at=3)
    s.advance(2);cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    s.advance(3);r.advance(3)
    assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[700,900]
    assert s.ctx.resources.current('target','hp')==1400
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


@pytest.mark.parametrize('patch',[{'side':1},{'category':4},{'target_free':True}])
def test_actual_source_side_category_and_free_permission_reject(patch):
    p=fixture();p['entities'][-2]['components']['selection_state'].update(patch)
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'caster','ability':'ability/shot'},at=0);s.advance(1)
    assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[900]
