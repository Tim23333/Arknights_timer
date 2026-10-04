from pathlib import Path
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.chapter07_stage_join.runner_718_providers_v1 import providers
ROOT=Path(__file__).resolve().parents[3]
MODULE=ROOT/'packages/campaign/chapter07_ranged_consumers/soticn.module.v4.json'
SOURCE=ROOT/'packages/campaign/chapter07_sources/native.reference.json'
INPUTS=[];CAPTURES=[]
def test_actual_mortar_speed4_reached_only_must_not_damage_at_launch_frame16():
 m=json.loads(MODULE.read_text(encoding='utf8'));eid=m['entities'][0]['id'];p={'schemaVersion':2,'manifest':{'id':'package/peer/mortar_delay','requires':['preset/ark_standard']},'entities':[{'id':'unit/peer/player','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':5000,'atk':1,'def':31,'mres':17,'taunt_level':0}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},'spatial':{}}}],'scenarioDraft':{'id':'scene/peer/mortar_delay','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':6},'initialEntities':[{'definition':eid,'instanceAlias':'mortar','position':{'row':1,'col':0}},{'definition':'unit/peer/player','instanceAlias':'target','position':{'row':1,'col':4}}]}}
 INPUTS.append(p);r=providers();s=Engine.create(Compiler(providers=r).compile(p,packages=[str(MODULE)]),providers=r,seed=71842);s.advance(17)
 CAPTURES.append({'case':'mortar16_vs_flight','checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()})
 native=json.loads(SOURCE.read_text(encoding='utf8'))['projectiles']['projectile_mortar']['components'];move=next(c['raw'] for c in native.values() if c['native_class']=='ParacurveMovement');hit=next(c['raw'] for c in native.values() if c['native_class']=='HitBehaviour')
 assert move['_speed']==4 and move['_raiseHeight']==1.5 and hit['_onlyCheckHitWhenReachTarget']==1
 # Four world units remain between launch and endpoint; no reached event at16.
 assert s.ctx.resources.current('target','hp')==5000
