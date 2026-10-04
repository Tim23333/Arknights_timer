"""Additional source-conserved branch program metadata; preserve earlier module bytes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'packages/campaign/chapter06_predefines_consumer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parent=OUT/'module.reference.json';p=json.loads(parent.read_bytes());profile=json.loads((OUT/'source.profile.json').read_bytes());b=profile['native_branch'];assert len(b['phases'])==1
program={'loop':False,'phases':[]}
for phase in b['phases']:
 actions=[]
 for a in phase['actions']:
  assert a['actionType']=='ACTIVATE_PREDEFINED' and a['count']==1 and a['managedByScheduler'] is True and a['interval']==0
  actions.append({'delay_seconds':a['preDelay'],'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':a['key']}}]})
 program['phases'].append({'pre_delay_seconds':phase['preDelay'],'actions':actions})
p['manifest']['metadata'].update({'parent_module_sha':sha(parent),'native_branch_programs':{'level_main_06-14':{'frstar_frosts':program}},'branch_scope':'Exact native branch action conversion only; request/skill trigger belongs to source Boss consumer and remains separate.','branch_builder_sha':sha(Path(__file__))});p['manifest']['id']='package/ch6/predefined/frosts/source_consumer_v2';out=OUT/'module.v2.reference.json';assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'two_native_actions':len(actions),'parent_sha':sha(parent)}))
