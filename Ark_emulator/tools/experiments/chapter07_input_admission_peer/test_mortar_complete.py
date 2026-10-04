from pathlib import Path
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter07_stage_join.runner_718_providers_v1 import providers
ROOT=Path(__file__).resolve().parents[3]
MODULE=ROOT/'packages/campaign/chapter07_ranged_consumers/soticn.module.v4.json'
SOURCE=ROOT/'packages/campaign/chapter07_sources/native.reference.json'
INPUTS=[];CAPTURES=[]
def test_actual_mortar_speed4_retained_real_projectile_prehit_disk_head(tmp_path):
 m=json.loads(MODULE.read_text(encoding='utf8'));eid=m['entities'][0]['id'];p={'schemaVersion':2,'manifest':{'id':'package/peer/mortar_delay','requires':['preset/ark_standard']},'entities':[{'id':'unit/peer/player','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':5000,'atk':1,'def':31,'mres':17,'taunt_level':0}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},'spatial':{}}}],'scenarioDraft':{'id':'scene/peer/mortar_delay','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':6},'initialEntities':[{'definition':eid,'instanceAlias':'mortar','position':{'row':1,'col':0}},{'definition':'unit/peer/player','instanceAlias':'target','position':{'row':1,'col':4}}]}}
 p['abilities']=[{'id':'ability/peer/retire_mortar','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'withdraw'}}]},'timeline':[]}];p['entities'].append({'id':'unit/peer/director','kind':'entity','components':{'abilities':['ability/peer/retire_mortar'],'spatial':{}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':0}})
 INPUTS.append(p);r=providers();s=Engine.create(Compiler(providers=r).compile(p,packages=[str(MODULE)]),providers=r,seed=71842);s.submit({'action':'skill','source':'director','ability':'ability/peer/retire_mortar'},at=17);s.advance(17)
 CAPTURES.append({'case':'mortar16_vs_flight','checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()})
 native=json.loads(SOURCE.read_text(encoding='utf8'))['projectiles']['projectile_mortar']['components'];move=next(c['raw'] for c in native.values() if c['native_class']=='ParacurveMovement');hit=next(c['raw'] for c in native.values() if c['native_class']=='HitBehaviour')
 assert move['_speed']==4 and move['_raiseHeight']==1.5 and hit['_onlyCheckHitWhenReachTarget']==1
 # Four world units remain between launch and endpoint; no reached event at16.
 assert s.ctx.resources.current('target','hp')==5000

 launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==1 and launches[0]['time']==16
 pin=write_ordered(tmp_path/'mortar17.json',s.checkpoint());rest=Engine.restore(s.program,load_bound(tmp_path/'mortar17.json',pin),providers=r);s.advance(33);rest.advance(33);head=replay(s.program,s.export_replay(),providers=r)
 CAPTURES.append({'case':'retained_mortar50','checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()});assert s.checkpoint()==rest.checkpoint()==head.checkpoint()
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['time']>16 and hits[0]['payload']['amount']==419 and s.ctx.resources.current('target','hp')==4581 and not s.ctx.active('mortar')
