"""Real source anchor selection; impact defaults to actual swept hit target."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'packages/campaign/chapter05_predefines/runtime_ballista';RUNTIME=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 old=OUT/'module.reference.json';assert sha(old)=='3ed8950c8ee185de3b83d392749ad6e8a7132610c84f0d1d417fdac0230b0345';p=json.loads(old.read_bytes());effect=p['abilities'][0]['timeline'][0]['effect'];assert effect.pop('target')=='source';p['selectors'][0]['limit']=1;p['selectors'][0]['eligible_rule']='rule/ballista/actual_source_identity';p['rules'].append({'id':'rule/ballista/actual_source_identity','kind':'rule','contract':'selector.eligibility','implementation':{'type':'expression','expression':'inputs.source.id == inputs.candidate.id'}});p['manifest']['id']+='/v2';p['manifest']['metadata'].update(builder_sha=sha(Path(__file__)),previous_module_sha=sha(old),correction='Select the real source actor as launch anchor, then hit actual collision target; do not retain a target=source override inside the projectile damage packet')
 p['selectors'][0].pop('eligible_rule');anchor_parameters=deepcopy(p['definitions'][0]['collision']['parameters']['eligibility']['parameters']);anchor_parameters['source_configuration'].update(_targetSide=1,_targetCategory=4,_targetMotion=1);p['selectors'][0]['eligibility']={'rule':'rule/ballista/actual_source_identity','parameters':anchor_parameters}
 p['rules'][-1]['contract']='targeting.eligibility';p['rules'][-1]['implementation']={'type':'graph','nodes':[{'id':'result','expression':"{'accepted':inputs.source.id == inputs.candidate.id,'reason':'real_source_identity_anchor'}"}],'output':'nodes.result'}
 test=deepcopy(p);test['scenarioDraft']={'id':'scene/source_anchor_compile','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':8},'objectives':{},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'actual','position':{'row':1,'col':0},'facing':'right'}]};Compiler().compile(test);dest=OUT/'module.v2.reference.json'
 if dest.exists():raise ValueError('Preserve module revisions')
 dest.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'module_v2_sha':sha(dest)}))
if __name__=='__main__':main()
