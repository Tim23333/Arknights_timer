import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_pillar_channel_joint_v1_candidate').resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_pillar_lifecycle_v1.build import build,providers,READY
p=build();p['entities'].append({'id':'unit/source/pull','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':8000,'atk':500,'def':400,'mres':0}},'resources':{'hp':{'role':'health','initial':8000,'capacity':8000}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']={'id':'scene/pullcounter','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':5},'initialEntities':[{'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':2,'col':2}},{'definition':'unit/source/pull','instanceAlias':'source','position':{'row':2,'col':1}}]}
s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());s.ctx.effects.execute('source',['pillar'],{'op':'apply_buff','buff':READY});s.ctx.effects.execute('source',['pillar'],{'op':'damage','damage_type':'true','scale':1})
assert s.ctx.resources.current('pillar','hp')==4500 and not s.ctx.get('pillar',('runtime','casts'),{})
r={'core':implementation_digest(),'actual_counter_reproduced':True,'source_hp500_atk500_actual_pillar_hp':4500,'actual_casts':s.ctx.get('pillar',('runtime','casts'),{}),'expected_source':'PullDupilr applies candead before500 true damage; source ON_TAKE_DAMAGE requires candead and no DeadLike, not HP0. Therefore actual positive-HP owned collapse is required.','native_complete':False};(ROOT/'validation/campaign/chapter09_duspfr_v1/parent.pillar_positive.counter.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
