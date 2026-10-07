import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_selection_context_clock_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from tools.chapter08_bsnake.screen_policy_v1 import providers
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter08_bsnake_firecommon_guarded_v3'
def package():
 p=json.loads((ROOT/'packages/campaign/chapter08_consumers/bsnake/firecommon.module.v2.json').read_bytes());u=p['entities'][0]['id'];p['entities'].append({'id':'unit/firecommon/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':999,'mres':40}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']={'id':'scene/bsnake/firecommon','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':8},'objectives':{},'initialEntities':[{'definition':u,'instanceAlias':'boss','position':{'row':2,'col':6}}]+[{'definition':'unit/firecommon/player','instanceAlias':'row'+str(r),'position':{'row':r,'col':3}} for r in range(1,4)]+[{'definition':'unit/firecommon/player','instanceAlias':'far','position':{'row':2,'col':5}}]};return p

def make(p):reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg,seed=817);s.submit({'action':'skill','source':'boss','ability':'ability/ch8/bsnake/firecommon'},at=0);return pr,s,reg
def test_actual_three_rays_one_rng_each_three_first_arts462_CPP7_head():
 p=package();pr,s,reg=make(p);s.advance(7);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'fire7.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(pr,load_bound(cp,h),providers=reg);s.advance(90);r.advance(90);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();events=s.session.events;hits=[e for e in events if e['type']=='damage.accepted'];assert len(hits)==3 and sorted(e['payload']['target'] for e in hits)==[3,4,5];assert all(e['payload']['amount']==462 for e in hits);assert len([e for e in events if e['type']=='random.branch'])==len([e for e in events if e['type']=='projectile.launched'])==3;assert s.ctx.resources.current('far','hp')==10000;assert s.ctx.entity('boss')['components']['spatial']['position']=={'row':2,'col':6};(OUT/'fire.trace.json').write_text(json.dumps({'input':p,'snapshot':s.snapshot(),'cp_sha':h},indent=2),encoding='utf8')
if __name__=='__main__':
 pr,s,reg=make(package());s.advance(80);print([(e['type'],e['time'],e['payload']) for e in s.session.events if e['type'] in ['damage.accepted','random.branch','projectile.launched']])
