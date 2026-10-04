"""Frozen82 actual qualification counterexample, not an accepted actor recipe."""
import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_more_content.build_v1 import providers,CORE,SOURCE,sha
def main():
 assert implementation_digest()==CORE
 data=json.loads(SOURCE.read_bytes());row=next(r for r in data['variants'].values() if r['prefab_key']=='enemy_1175_dushdo')
 native=next(x for x in row['passive_and_skill_components'] if x['class']=='ToggleablePassiveBuffAbility')['raw']['_buffs'][0]
 assert native['attributes']['abnormalFlags']==[9]
 dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';assert 'public const AbnormalFlag INVISIBLE = 9;' in dump.read_text(encoding='utf8')
 module=ROOT/'packages/campaign/chapter09_consumers/more_ordinary/enemy_1168_dumage.module.v1.json';p=json.loads(module.read_bytes())
 p['buffs'].append({'id':'buff/coupled/probe/invisible','kind':'buff','selection_flags':{'abnormal_flags':[9]},'metadata':{'source_inline':native}})
 p['entities'].append({'id':'unit/coupled/probe/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':9000,'def':0,'mres':23}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'buffs':{'initial':['buff/coupled/probe/invisible']},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
 p['scenarioDraft']={'id':'scene/coupled/probe/invisible','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'attacker','position':{'row':0,'col':0}},{'definition':'unit/coupled/probe/target','instanceAlias':'target','position':{'row':0,'col':2}}]}
 reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg,seed=9951);s.advance(20)
 log=Path('E:/ArkSimLogs/runs/chapter09_coupled_invisible_counterexample');log.mkdir(parents=True,exist_ok=True);cp=log/'invisible.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(pr,load_bound(cp,pin),providers=reg);s.advance(10);r.advance(10);h=replay(pr,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 hits=[{'time':e['time'],'amount':e['payload']['amount']} for e in s.session.events if e['type']=='damage.accepted'];assert hits==[{'time':25,'amount':231}]
 from ark_sim.domains.selection import project_state,DEFAULT_STATE
 state=project_state(s.ctx,'target',DEFAULT_STATE);assert 9 in state['abnormal_flags'] and state['target_free']==state['camouflage']==False
 cleanup=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),'--apply','--run-dir',str(log),'--minimum-age-minutes','0'],capture_output=True,text=True);assert cleanup.returncode==0
 out=ROOT/'validation/campaign/chapter09_coupled_author';out.mkdir(parents=True,exist_ok=True)
 receipt={'schema':'ark-sim/c9-coupled-invisible-counterexample/v1','runtime':CORE,'module_sha':sha(module),'source_sha':sha(SOURCE),'native_invisible':native,'actual_state':state,'actual_damage':hits,'CP_and_head_equal':True,'CP_sha':pin,'CP_deleted_after_verification':True,'cleanup':json.loads(cleanup.stdout),'counterexample':'Native INVISIBLE9 remains visible to existing model.targeting.eligibility, even when target-free and camouflage bypasses disabled.','actor_admission':False,'whole_stage':False}
 (out/'invisible.counterexample.receipt.v1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'counterexample_reproduced':True,'damage':hits,'CP_and_head_equal':True,'cleanup':json.loads(cleanup.stdout)}))
if __name__=='__main__':main()


