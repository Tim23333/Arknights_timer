import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[]

def fixture():
 h=json.loads((ROOT/'packages/campaign/chapter02_tiles/m41.hole.profile.json').read_bytes())
 return {'manifest':{'requires':['preset/ark_standard']},'rules':deepcopy(h['rules']),
  'entities':[{'id':'unit/probe','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':321,'move_speed':2}},'resources':{'hp':{'initial':321,'capacity':321,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/contact']}}],
  'abilities':[{'id':'ability/contact','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':1}}]},'timeline':[]}],
  'scenarioDraft':{'id':'scene/peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':3,'tiles':[{'tileKey':'tile_hole' if i==1 else 'tile_floor','passableMask':3,'buildableType':0} for i in range(6)],'tile_mechanics':deepcopy(h['tile_mechanics'])},'initialEntities':[{'definition':'unit/probe','instanceAlias':'e','position':{'row':0,'col':0}}]}}

def create(p,seed=41201):
 raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':seed,'fixture':json.loads(raw)})
 return Engine.create(Compiler().compile(json.loads(raw)),seed=seed)

def test_real_source_birth_both_variants_half_open_and_disk_replay(tmp_path):
 raw=(ROOT/'packages/campaign/chapter02_units/airdrp.birth_contact.model.json').read_bytes();p=json.loads(raw);h=json.loads((ROOT/'packages/campaign/chapter02_tiles/m41.hole.profile.json').read_bytes());p['rules']+=h['rules']
 p['scenarioDraft']=fixture()['scenarioDraft'];p['scenarioDraft']['initialEntities']=[{'definition':u['id'],'instanceAlias':'born'+str(i),'position':{'row':0,'col':1}} for i,u in enumerate(p['entities'])]
 s=create(p);s.advance(45)
 assert [s.ctx.resources.current('born'+str(i),'hp') for i in range(2)]==[1450,2300]
 pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(1);r.advance(1)
 assert [s.ctx.resources.current('born'+str(i),'hp') for i in range(2)]==[0,0]
 assert [e['time'] for e in s.session.events if e['type']=='tile.contact_death']==[45,45]
 assert s.ctx.state()['kills']==2 and s.ctx.state()['leaks']==0
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_public_move_contact_is_environment_not_attack_credit(tmp_path):
 s=create(fixture());s.submit({'action':'skill','source':'e','ability':'ability/contact'},at=2);s.advance(1)
 pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(4);r.advance(4)
 assert s.ctx.resources.current('e','hp')==0 and s.ctx.state()['kills']==1 and s.ctx.state()['leaks']==0
 assert not any(e['type'] in ('damage.accepted','combat.kill') for e in s.session.events)
 assert s.ctx.state()['damage_dealt']==0
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_fly_then_ground_public_effect_checks_existing_cell():
 p=fixture();p['scenarioDraft']['initialEntities'][0].update(position={'row':0,'col':1},components={'spatial':{'motion_mode':1}})
 p['abilities'][0]['activation']['on_start']=[{'op':'set_motion_mode','target':'source','value':0}]
 s=create(p);assert s.ctx.resources.current('e','hp')==321
 s.submit({'action':'skill','source':'e','ability':'ability/contact'},at=4);s.advance(5)
 assert s.ctx.resources.current('e','hp')==0 and [e['time'] for e in s.session.events if e['type']=='tile.contact_death']==[4]
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_replaceable_deny_rule_and_real_native_mask_preserved():
 p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':'False'};p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1}
 s=create(p);s.advance(3);assert s.ctx.alive('e') and s.ctx.resources.current('e','hp')==321
 assert s.ctx.spatial.grid.tile(0,1)['passableMask']==3

def test_real_retirement_failure_restores_all_and_retry_not_poisoned():
 s=create(fixture());before=s.checkpoint();original=s.ctx.lifecycle.retire
 def fail(ref,reason):
  original(ref,reason);s.session.random.sample('imp');s.session.schedule('domain.entity.expire',{'target':ref},99);raise RuntimeError('peer failed death')
 s.ctx.lifecycle.retire=fail
 with pytest.raises(RuntimeError):s.ctx.movement.displace('e','e',{'position':{'row':0,'col':1}},None)
 assert s.checkpoint()==before and s.ctx.tile_contacts._settling==set()
 s.ctx.lifecycle.retire=original;s.ctx.movement.displace('e','e',{'position':{'row':0,'col':1}},None)
 assert not s.ctx.alive('e') and s.ctx.state()['kills']==1
