import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m42_aura_remove_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay

def fixture():
    unit=lambda name,tags,buffs=[]:{'id':'unit/'+name,'kind':'entity','tags':tags,'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'def':10}},'resources':{'hp':{'initial':100,'capacity':100}},'buffs':{'initial':buffs}}}
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[unit('parent',['emitter'],['buff/parent']),unit('a',['member']),unit('b',['member'])],
       'buffs':[{'id':'buff/parent','kind':'buff','aura':{'selector':'selector/members','buff':'buff/child'}},
                {'id':'buff/child','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':5}]}],
       'selectors':[{'id':'selector/members','kind':'selector','region':{'type':'circle','radius':2},'filters':[{'tag':'member'},{'state':'alive'}]}],
       'abilities':[{'id':'ability/leave','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':3}}]},'timeline':[]}],
       'scenarioDraft':{'id':'scene/peer/remove','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':4},
          'initialEntities':[{'definition':'unit/parent','instanceAlias':'parent','position':{'row':0,'col':0}},
                             {'definition':'unit/a','instanceAlias':'a','position':{'row':0,'col':1}},
                             {'definition':'unit/b','instanceAlias':'b','position':{'row':0,'col':2}}]}}
    p['entities'][1]['components']['abilities']=['ability/leave'];return p

def test_child_cleanup_callback_removes_parent_without_recreating_ghost_sibling():
    p=fixture();p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    p['entities'][1]['components']['attributes']['base']['atk']=100
    p['entities'][2]['tags'].append('victim')
    p['selectors'].append({'id':'selector/victim','kind':'selector','region':{'type':'all'},'filters':[{'tag':'victim'}]})
    p['abilities'][0]['selector']='selector/victim'
    p['abilities'][0]['activation']['on_start'].append({'op':'damage','damage_type':'physical'})
    s=Engine.create(Compiler().compile(p),seed=4242);assert len(s.ctx.get('b',('buffs','instances')))==1;s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=0);s.advance(1)
    assert not s.ctx.alive('parent')
    assert s.ctx.resources.current('b','hp')==10
    assert s.ctx.get('a',('buffs','instances'))==[] and s.ctx.get('b',('buffs','instances'))==[]

def test_outer_remove_on_remove_installs_replacement_parent_without_stale_child():
    p=fixture();p['buffs'][0]['on_remove']=[{'op':'apply_buff','target':'source','buff':'buff/replacement'}]
    p['buffs'] += [{'id':'buff/replacement','kind':'buff','aura':{'selector':'selector/members','buff':'buff/newchild'}},
                    {'id':'buff/newchild','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':20}]}]
    p['entities'][0]['components']['abilities']=['ability/switch'];p['abilities'].append({'id':'ability/switch','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':'source','buff':'buff/parent'}]},'timeline':[]})
    program=Compiler().compile(p);s=Engine.create(program,seed=4244);s.submit({'action':'skill','source':'parent','ability':'ability/switch'},at=0);s.advance(1)
    for ref in ('a','b'):assert [i['definition'] for i in s.ctx.get(ref,('buffs','instances'))]==['buff/newchild']
    assert s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling and s.snapshot()==replay(program,s.export_replay()).snapshot()
