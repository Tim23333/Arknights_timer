"""Observe exact current b20 duration bindings; no candidate or old receipt changes."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.adapters.api import implementation_digest
from tools.candidates.infinite_buff_plan_review.duration_scope_v1 import sha
def main():
 original=ROOT/'validation/campaign/infinite_buff_plan_duration_scope_v1/receipt.json';p=json.loads(original.read_bytes())['input'];rows=[]
 def provider(inputs,params,context):return {'accepted':True,'operations':[{'kind':'apply','buff':'buff/declared','duration_seconds':None}]}
 reg={**BUILTIN_PROVIDERS,'author/none':{'callable':provider,'version':'1'}}
 for binding in ('buff_local','source_definition','scenario','runtime_source'):
  for seconds in (0,3):
   q=deepcopy(p);q['buffs'][0].pop('rules');q['rules'][1]['implementation']['expression']=str(seconds)
   if binding=='buff_local':q['buffs'][0]['rules']={'buff.duration':'rule/finite'}
   if binding=='source_definition':q['entities'][0]['rules']={'buff.duration':'rule/finite'}
   if binding=='scenario':q['scenarioDraft']['rules']={'buff.duration':'rule/finite'}
   q['scenarioDraft']['dependencies'].append('rule/finite');s=Engine.create(Compiler(providers=reg).compile(q),providers=reg)
   if binding=='runtime_source':s.ctx.set('source',('runtime','rule_bindings'),{'buff.duration':'rule/finite'})
   s.ctx.effects.execute('source',[s.session.world.resolve('source')],{'op':'buff_application','application_rule':'rule/none','allowed':['buff/declared']});expiry=s.ctx.entity('source')['components']['buffs']['instances'][0]['expires_at'];assert expiry==(None if seconds==0 else90);rows.append({'binding':binding,'actual_seconds_rule':seconds,'actual_expiry':expiry,'input':q,'snapshot':s.snapshot()})
 out=ROOT/'validation/campaign/infinite_buff_plan_scope_matrix_v1/receipt.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'core':implementation_digest(),'eight_actual_probes':rows,'generic_None_permanent_contract_closed':False,'frozen_source_default_source_cases_still_permanent':True,'helper_sha':sha(Path(__file__)),'primary_modified':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'rows':[{k:v for k,v in x.items() if k not in ('input','snapshot')} for x in rows]}))
if __name__=='__main__':main()
