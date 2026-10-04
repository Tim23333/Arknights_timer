"""Actual v9 regression counter: default alive filter never includes withdrawn/dead actor."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_shared_aura_v10_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()=='b10290ea1d7f0cd4f1d49fa14f79579687e34d134743628a360371f18611216a';p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/x','kind':'entity','tags':['x'],'components':{'attributes':{'base':{}},'spatial':{}}}],'selectors':[{'id':'selector/alive','kind':'selector','region':{'type':'all'},'filters':[{'tag':'x'},{'state':'alive'}]}],'scenarioDraft':{'id':'scene/dead','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},'initialEntities':[{'definition':'unit/x','instanceAlias':'x','position':{'row':0,'col':0}}],'dependencies':['selector/alive']}};paths=[Path(__file__)]+list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'));before={str(f):sha(f) for f in paths};rows=[]
 for reason in ('withdrawn','dead','exited'):
  s=Engine.create(Compiler().compile(p));assert s.ctx.spatial.select('system/battle','selector/alive')==[2];s.ctx.lifecycle.retire('x',reason);assert not s.ctx.alive('x') and s.ctx.spatial.select('system/battle','selector/alive')==[];rows.append({'reason':reason,'actual_alive':False,'selected':[]})
 after={str(f):sha(f) for f in paths};assert before==after;out=ROOT/'validation/campaign/shared_aura_legacy_alive_v10/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':True,'actual_exit':0,'core':implementation_digest(),'source_before':before,'source_after':after,'input':p,'actual3':rows,'old_v9_actual_counter':'aliveFalse/selected[2] retained in tool output and shared_aura_self_v9 scope history, not promoted'};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out)}))
if __name__=='__main__':main()
