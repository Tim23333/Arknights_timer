import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m85_death_sequence_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
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

def test_two_valid_specs_retain_two_independent_blasts_public_disk_and_replay(tmp_path):
 p=fixture();p['entities'][0]['components']['lifecycle']['death_projectiles']*=2;s=make(p);s.advance(15);h=write_ordered(tmp_path/'two.ordered.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'two.ordered.json',h));s.advance(20);r.advance(20)
 assert len(events(s,'projectile.launched'))==2 and [e['payload']['amount'] for e in events(s,'damage.accepted') if e['payload']['source']==s.session.world.resolve('slime')]==[840,840]
 assert s.ctx.resources.current('hero','hp')==8320 and s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_withdraw_callback_does_not_delete_first_retained_projectile(monkeypatch):
 p=fixture();p['entities'][0]['components']['lifecycle']['death_projectiles']*=2;s=make(p);old=s.ctx.buffs.toggles.pulse;once=[]
 def pulse(event,payload):
  old(event,payload)
  if event=='projectile.launched' and not once:once.append(True);s.ctx.lifecycle.retire('slime','withdrawn')
 monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',pulse);s.advance(35)
 assert len(events(s,'projectile.launched'))==1 and s.ctx.resources.current('hero','hp')==9160 and s.ctx.state()['kills']==0

def test_terminal_callback_stops_second_spec_and_cancels_only_committed_pending_projectile(monkeypatch):
 p=fixture();p['entities'][0]['components']['lifecycle']['death_projectiles']*=2;p['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'};p['scenarioDraft']['resources']={'life':{'initial':10,'capacity':10}};s=make(p);old=s.ctx.buffs.toggles.pulse;once=[]
 def pulse(event,payload):
  old(event,payload)
  if event=='projectile.launched' and not once:once.append(True);s.ctx.resources.adjust('system/battle','life',value=0);s.ctx.lifecycle.tick(s.session)
 monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',pulse);s.advance(35)
 assert s.ctx.state()['result']=='defeat' and len(events(s,'projectile.launched'))==1 and s.ctx.resources.current('hero','hp')==10000 and not s.ctx.projectiles.completion_pending()

def test_optional_actual_epoch_change_stops_future_specs_without_inventing_new_actor_epoch(monkeypatch):
 p=fixture();p['entities'][0]['components']['lifecycle']['death_projectiles']*=2;s=make(p);s.ctx.set('slime',('runtime','death_generation'),1);old=s.ctx.buffs.toggles.pulse;once=[]
 def pulse(event,payload):
  old(event,payload)
  if event=='projectile.launched' and not once:once.append(True);s.ctx.set('slime',('runtime','death_generation'),2)
 monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',pulse);s.advance(3);assert len(events(s,'projectile.launched'))==1 and s.ctx.get('slime',('runtime','death_generation'))==2

def test_later_spec_pure_failure_rolls_back_first_launch_hp_rng_events_scheduler_and_guards(monkeypatch):
 p=fixture();p['entities'][0]['components']['lifecycle']['death_projectiles']*=2;p['entities'][0]['components']['lifecycle']['death_projectiles'][1]=deepcopy(p['entities'][0]['components']['lifecycle']['death_projectiles'][1]);p['entities'][0]['components']['lifecycle']['death_projectiles'][1]['rule']='rule/peer/failure';p['rules'].append({'id':'rule/peer/failure','kind':'rule','contract':'lifecycle.death_emission','implementation':{'type':'expression','expression':'1/0'}});s=make(p);old=s.ctx.buffs.toggles.pulse
 def pulse(event,payload):
  old(event,payload)
  if event=='projectile.launched':s.ctx.effects.execute('hero',['hero'],{'op':'random','stream':'imp','probability':1,'on_success':[]})
 monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',pulse);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.resources.adjust('slime','hp',-5000,source='hero')
 assert s.checkpoint()==before and not s.ctx.get('slime',('runtime','death_emission_in_progress'),False)
