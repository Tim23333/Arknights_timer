"""Existing generic aura membership can model declared cell occupancy.

Virtual field owner/grid projection is an explicit model representation; this
does not recover native BuffTile target getters or physical contact callbacks.
"""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_tile_buff_models import build


def fixture():
    p=build()
    healing=next(b for b in p['buffs'] if b['id']=='buff/ch2/healing_tile_member')
    # Existing aura ownership requires independent child instances; this is a
    # declared virtual-field adapter, distinct from native maxStackCnt1 data.
    healing['stacking']={'mode':'independent'}
    healing['metadata']['virtual_cell_membership_policy']='one independent child per field owner; native override/stack callbacks pending'
    p['entities']=[{'id':'unit/field','kind':'entity','tags':['virtual_tile_field'],'components':{'spatial':{},
        'attributes':{'base':{'max_hp':1,'atk':0}},'resources':{'hp':{'initial':1,'capacity':1}},
        'buffs':{'initial':['buff/field_parent']}}},
      {'id':'unit/target','kind':'entity','tags':['player','ground'],'components':{'spatial':{},
        'attributes':{'base':{'max_hp':1000,'hp_ratio_recovery':0,'atk':0}},
        'resources':{'hp':{'initial':500,'capacity':1000,'role':'health','recovery_rule':'rule/ch2/tile_hp_ratio_recovery','recovery':{'mode':'continuous'}}},
        'abilities':['ability/enter','ability/leave','ability/retire']}}]
    p['buffs'].append({'id':'buff/field_parent','kind':'buff','aura':{'selector':'selector/cell','buff':'buff/ch2/healing_tile_member'}})
    p['selectors']=[{'id':'selector/cell','kind':'selector','region':{'type':'grid_offsets','offsets':[[0,0]],'rotate_with_facing':False},
        'filters':[{'tag':'player'},{'state':'alive'}],'parameters':{'exclude_source':True}}]
    p['abilities']=[{'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[{
        'op':'move','target':'source','position':{'row':0,'col':col}}]},'timeline':[]} for name,col in [('enter',1),('leave',2)]]
    p['abilities'].append({'id':'ability/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]},'timeline':[]})
    p['scenarioDraft']={'id':'scene/cell_field','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'objectives':{},
        'initialEntities':[{'definition':'unit/field','instanceAlias':'field','position':{'row':0,'col':1}},
                           {'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':0}}]}
    return p


def test_public_move_enters_and_leaves_one_cell_with_exact_owned_membership():
    p=fixture();s=Engine.create(Compiler().compile(p),seed=2920)
    s.submit({'action':'skill','source':'target','ability':'ability/enter'},at=3)
    s.submit({'action':'skill','source':'target','ability':'ability/leave'},at=33)
    s.advance(34);assert s.ctx.resources.current('target','hp')==pytest.approx(530)
    assert not s.ctx.get('target',('buffs','instances'))
    cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_retirement_cleans_field_membership_and_stops_regeneration():
    p=fixture();p['scenarioDraft']['initialEntities'][1]['position']['col']=1
    s=Engine.create(Compiler().compile(p),seed=2921)
    s.submit({'action':'skill','source':'target','ability':'ability/retire'},at=3);s.advance(6)
    assert s.ctx.resources.current('target','hp')==pytest.approx(503)
    assert not s.ctx.alive('target')
    parent=s.ctx.get('field',('buffs','instances'))[0]
    assert parent['aura_members']=={}
    cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
