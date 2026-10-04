"""Actual source25s twoincarnations and retained original-source projectiles."""
import json
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_flame_device.build_module_v2 import OUT,UNIT
from tools.chapter08_flame_device.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def test_real_device_two_publicactivations_and_finitebudget_CP_head(tmp_path):
    p=json.loads(OUT.read_bytes());p['entities'].append({'id':'unit/reuseflame/director','kind':'entity','components':{'spatial':{},'abilities':['ability/reuseflame/activate']}})
    p['abilities'].append({'id':'ability/reuseflame/activate','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'activate_predefined','target':'battle','parameters':{'key':'flame1'}}]},'timeline':[]})
    p['scenarioDraft']={'id':'scene/reuseflame/source','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':3},'initialEntities':[
        {'definition':UNIT,'position':{'row':1,'col':1},'active':False,'registration_key':'flame1','reactivation':{'max_activations':2,'after_reasons':['withdrawn','dead']}},
        {'definition':'unit/reuseflame/director','instanceAlias':'director','position':{'row':0,'col':0}}]}
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);old=s.ctx.state()['predefined_registry']['flame1']
    for t in (0,760,1530):s.submit({'action':'skill','source':'director','ability':'ability/reuseflame/activate'},at=t)
    s.advance(750);cp=tmp_path/'first750.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(790);r.advance(790);head=replay(program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    new=s.ctx.state()['predefined_registry']['flame1'];assert old!=new and not s.ctx.active(old) and not s.ctx.active(new)
    launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==8
    assert {e['payload']['source'] for e in launches}=={old,new}
    assert s.ctx.resources.current(old,'hp')==s.ctx.resources.current(new,'hp')==6000
    assert [e['time'] for e in s.session.events if e['type']=='command.rejected']==[1530]
