import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
 p=json.loads((ROOT/'packages/campaign/chapter04_units/bslime.reference_model.json').read_bytes());slime=p['entities'][0]['id'];p['entities'].append({'id':'unit/peer/attacker','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},'attributes':{'base':{'atk':5000,'def':200,'mres':0,'max_hp':10000}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer/kill']}})
 p['selectors'].append({'id':'selector/peer/slime','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['abilities'].append({'id':'ability/peer/kill','kind':'ability','selector':'selector/peer/slime','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'true'}]},'timeline':[]})
 p['scenarioDraft']={'id':'scene/peer/death','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':5},'initialEntities':[{'definition':slime,'instanceAlias':'slime','position':{'row':1,'col':1}},{'definition':'unit/peer/attacker','instanceAlias':'hero','position':{'row':1,'col':2}}]};return p

def make(p=None):
 s=Engine.create(Compiler().compile(p or fixture()),seed=760070);s.submit({'action':'skill','source':'hero','ability':'ability/peer/kill'},at=1);return s

def events(s,name):return [e for e in s.session.events if e['type']==name]

def test_multiple_death_specs_stop_when_first_launch_callback_withdraws_actual_source(monkeypatch):
 p=fixture();specs=p['entities'][0]['components']['lifecycle']['death_projectiles'];specs.append(deepcopy(specs[0]));s=make(p);old=s.ctx.buffs.toggles.pulse;once=[]
 def pulse(event,payload):
  old(event,payload)
  if event=='projectile.launched' and not once:
   once.append(True);s.ctx.lifecycle.retire('slime','withdrawn')
 monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',pulse);s.advance(3)
 assert s.ctx.get('slime',('runtime','state'))=='withdrawn' and s.ctx.state()['kills']==0
 assert len(events(s,'projectile.launched'))==1
