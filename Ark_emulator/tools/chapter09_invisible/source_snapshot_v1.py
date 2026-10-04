"""Raw ordered snapshots for exact parent/candidate legacy source pairing."""
import sys,json
from pathlib import Path
runtime=Path(sys.argv[1]);output=Path(sys.argv[2]);ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.chapter08_bsnake_combat.policies_v1 import providers
def main():
 cases={};reg=providers()
 for key in ('enemy_1165_duhond','enemy_1166_dusbr','enemy_1167_dubow'):
  p=json.loads((ROOT/'packages/campaign/chapter09_consumers/ordinary'/(key+'.module.v1.json')).read_bytes());uid=p['entities'][0]['id'];ranged=key.endswith('dubow')
  p['entities'].append({'id':'unit/legacy/guard','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':9000,'def':193,'mres':87,'block_count':1}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'base_cost':1,'terrain':'ground','capacity':1,'cooldown_seconds':0},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
  p['scenarioDraft']={'id':'scene/legacy/'+key,'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'resources':{'dp':{'initial':10,'capacity':99}},'roster':['unit/legacy/guard'],'commands':[{'at':0,'action':'deploy','entity':'unit/legacy/guard','alias':'guard','row':0,'col':1}],'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':0,'col':0 if ranged else 1},**({} if ranged else {'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':3},'checkpoints':[]}})}]}
  pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg,seed=99831);captures=[]
  for t in (0,20,100):
   s.advance(t-s.session.time);captures.append({'time':t,'checkpoint':s.checkpoint(),'context_state':thaw(s.ctx.state()),'events':thaw(list(s.session.events))})
  cases[key]={'program_fingerprint':pr.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,'program_definitions':thaw(pr.definitions),'program_scenario':thaw(pr.scenario),'program_metadata':thaw(pr.metadata),'captures':captures}
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps({'implementation':implementation_digest(),'cases':cases},ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
if __name__=='__main__':main()
