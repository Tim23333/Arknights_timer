"""Read-only adversarial probe: declared no duration field but explicit rule scope."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.adapters.api import implementation_digest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 def provider(inputs,params,context):return {'accepted':True,'operations':[{'kind':'apply','buff':'buff/declared','duration_seconds':None}]}
 reg={**BUILTIN_PROVIDERS,'author/none':{'callable':provider,'version':'1'}}
 p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'rules':[{'id':'rule/none','kind':'rule','contract':'buff.application','implementation':{'type':'provider','provider':'author/none'}},{'id':'rule/finite','kind':'rule','contract':'buff.duration','implementation':{'type':'expression','expression':'3'}}],'buffs':[{'id':'buff/declared','kind':'buff','rules':{'buff.duration':'rule/finite'}}],'entities':[{'id':'unit/author','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'atk':100}},'spatial':{}}}],'scenarioDraft':{'id':'scene/none/custom_scope','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},'initialEntities':[{'definition':'unit/author','instanceAlias':'source','position':{'row':0,'col':0}}],'dependencies':['rule/none','buff/declared']}}
 s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.ctx.effects.execute('source',[s.session.world.resolve('source')],{'op':'buff_application','application_rule':'rule/none','allowed':['buff/declared']});instances=s.snapshot()['entities'];instance=s.ctx.entity('source')['components']['buffs']['instances'][0];assert instance['expires_at']==90;out=ROOT/'validation/campaign/infinite_buff_plan_duration_scope_v1/receipt.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'core':implementation_digest(),'actual_custom_scope_infinity_gap':True,'expected_declared_None_permanent':None,'actual_expiry':instance['expires_at'],'input':p,'snapshot':s.snapshot(),'helper_sha':sha(Path(__file__)),'frozen_b20_modified':False,'primary_modified':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'actual_expiry':instance['expires_at']}))
if __name__=='__main__':main()
