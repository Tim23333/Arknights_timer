import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/experiments/chapter02_twelve'))
from test_module import scene,uid
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]
def module():return json.loads((ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.combat_guard.reference_module.json').read_bytes())
def fixture(name,taunt,blocked=True):
 p=scene(module(),name,[('blocker',3,0),('other',3,1)],True)
 # Use a recorded deployment, keeping the initial blocker outside the remaining path.
 p['scenarioDraft']['initialEntities'][1]['position']={'row':0,'col':0}
 p['scenarioDraft']['roster']=['unit/fixture/target'];p['scenarioDraft']['resources']={'dp':{'initial':100,'capacity':100}}
 p['buffs']=[{'id':'buff/fixture/preblock','kind':'buff','duration_seconds':1/30,'control':{'attack':False}}];p['scenarioDraft']['initialEntities'][0]['components']={'buffs':{'initial':['buff/fixture/preblock']}}
 alt=deepcopy(p['definitions'][-1]);alt['id']='unit/fixture/taunt';alt['components']['attributes']['base'].update(taunt_level=taunt,block_count=0);alt['components'].pop('deployable');p['definitions'].append(alt);p['scenarioDraft']['initialEntities'][-1]['definition']=alt['id']
 if blocked:p['scenarioDraft']['initialEntities'].pop(1)
 if not blocked:p['scenarioDraft']['initialEntities'][1]['position']={'row':3,'col':.5};p['scenarioDraft']['initialEntities'][1]['components']={'attributes':{'base':{'block_count':0}}}
 return p
def create(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':48141,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=48141)
def exact(s,tmp_path):
 h=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',h));s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
@pytest.mark.parametrize('name', ['enemy_1011_wizard','enemy_1028_mocock','enemy_1018_aoemag'])
@pytest.mark.parametrize('taunt',[20,1000000,-1000000])
def test_real_deployed_blocker_is_only_primary_for_any_taunt(name,taunt,tmp_path):
 s=create(fixture(name,taunt));s.submit({'action':'deploy','entity':'unit/fixture/target','position':{'row':3,'col':0},'alias':'realblocker'},at=0);s.advance(1)
 assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('realblocker')
 s.advance(30);started=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==s.session.world.resolve('enemy')]
 assert len(started)==1 and list(started[0]['payload']['targets'])==[s.session.world.resolve('realblocker')]
 # Aoemag legitimately splashes other as well; this assertion concerns primary, not damage immunity.
 if name!='enemy_1018_aoemag':assert s.ctx.resources.current('other','hp')==10000
 exact(s,tmp_path)
@pytest.mark.parametrize('deny',['free','geometry','filter'])
def test_ineligible_current_blocker_has_no_fallback_other(deny,tmp_path):
 p=fixture('enemy_1011_wizard',1000000)
 if deny=='free':p['definitions'][-2]['components']['selection_state']['target_free']=True
 elif deny=='filter':p['definitions'][-2]['tags']=['foreign']
 elif deny=='geometry':
  sid=next(r['selector'] for r in p['manifest']['metadata']['combat_guard_bindings'] if 'wizard' in r['variant_id']);selector=next(d for d in p['definitions'] if d['id']==sid);selector['region']['offsets']=[[0,1]];selector['region'].pop('radius');selector['region']['type']='grid_offsets'
 s=create(p);s.submit({'action':'deploy','entity':'unit/fixture/target','position':{'row':3,'col':0},'alias':'realblocker'},at=0);s.advance(1);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('realblocker')
 s.advance(29);assert not any(e['type']=='ability.started' and e['payload']['source']==s.session.world.resolve('enemy') for e in s.session.events);assert s.ctx.resources.current('other','hp')==10000;exact(s,tmp_path)
def test_unblocked_declared_taunt_still_chooses_farther_target(tmp_path):
 s=create(fixture('enemy_1011_wizard',20,False));s.advance(30);started=[e for e in s.session.events if e['type']=='ability.started'];assert len(started)==1 and list(started[0]['payload']['targets'])==[s.session.world.resolve('other')];exact(s,tmp_path)
def test_only_expected_three_consumers_and_score_changed_boss_stats_untouched():
 parent=json.loads((ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json').read_bytes());p=module();old={d['id']:d for d in parent['definitions']};new={d['id']:d for d in p['definitions']};changed={key for key in old if old[key]!=new[key]};expected={'rule/ch2_10/combat_priority'}|{x['selector'] for x in p['manifest']['metadata']['combat_guard_bindings']}
 assert changed==expected and set(new)-set(old)=={'rule/ch2_10/combat_target_guard'}
