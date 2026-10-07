import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from tools.chapter07_ranged_consumers.policies_v1 import providers
MODULE=ROOT/'packages/campaign/chapter07_ranged_consumers/sotisp.module.v3.json'
def package():
 p=json.loads(MODULE.read_bytes());u=p['entities'][0]['id'];p['entities'].append({'id':'unit/ranged/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':111,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']={'id':'scene/sniper/probe','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'objectives':{},'initialEntities':[{'definition':u,'instanceAlias':'sniper','position':{'row':1,'col':1}},{'definition':'unit/ranged/target','instanceAlias':'t1','position':{'row':1,'col':2}},{'definition':'unit/ranged/target','instanceAlias':'t2','position':{'row':1,'col':3}}]};return p
if __name__=='__main__':
 p=package();s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());s.session.advance(110)
 for e in s.snapshot()['events']:
  if e['type'] in ['ability.started','damage.accepted','projectile.launched','projectile.hit','buff.applied','behavior.transitioned']:print(json.dumps(e))
 out=ROOT/'validation/campaign/chapter07_ranged_sotisp_probe_v2';out.mkdir(parents=True,exist_ok=True);(out/'probe.json').write_text(json.dumps({'input':p,'snapshot':s.snapshot()},indent=2),encoding='utf8')
