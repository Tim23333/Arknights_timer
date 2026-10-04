import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from tools.chapter07_ranged_consumers.policies_v1 import live_taunt_score,strength_application
from tools.chapter07_ranged_consumers.mortar_box_v2 import mortar_box
REG={**BUILTIN_PROVIDERS,'reference.c7.ranged_live_taunt':{'callable':live_taunt_score,'version':'1'},'reference.c7.ranged_strength':{'callable':strength_application,'version':'1'},'reference.c7.mortar_box':{'callable':mortar_box,'version':'2'}}
def package():
 p=json.loads((ROOT/'packages/campaign/chapter07_ranged_consumers/soticn.module.v4.json').read_bytes());u=p['entities'][0]['id'];p['entities'].append({'id':'unit/mortar/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':111,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});fly=json.loads(json.dumps(p['entities'][-1]));fly['id']='unit/mortar/fly';fly['components']['selection_state'].update(motion=2,camouflage=True);p['entities'].append(fly);p['scenarioDraft']={'id':'scene/mortar/source','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':8},'objectives':{},'initialEntities':[{'definition':u,'instanceAlias':'mortar','position':{'row':2,'col':1}},{'definition':'unit/mortar/player','instanceAlias':'primary','position':{'row':2,'col':5}},{'definition':'unit/mortar/fly','instanceAlias':'corner','position':{'row':3.5,'col':6.5}},{'definition':'unit/mortar/fly','instanceAlias':'outside','position':{'row':3.50000001,'col':5}}]};return p
if __name__=='__main__':
 p=package();s=Engine.create(Compiler(providers=REG).compile(p),providers=REG);s.session.advance(180)
 for e in s.snapshot()['events']:
  if e['type'] in ('ability.started','projectile.launched','area.resolved','damage.accepted','projectile.hit'):print(json.dumps(e))
 out=ROOT/'validation/campaign/chapter07_ranged_soticn_probe_v3';out.mkdir(parents=True,exist_ok=True);(out/'trace.json').write_text(json.dumps({'input':p,'snapshot':s.snapshot()},indent=2),encoding='utf8')
