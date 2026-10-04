import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.campaign_content_composition_v2 import reachable_content,compose_modules
from tools.chapter06.cold.policies import providers as cold
from tools.chapter06_npcs.huang_v6_policy import providers as huang
OUT=ROOT/'validation/campaign/chapter06_composition_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[ROOT/'tools/campaign_content_composition_v2.py',ROOT/'tools/campaign_content_composition.py',ROOT/'packages/campaign/chapter06_npcs/huang.v7.model.json',ROOT/'packages/campaign/chapter06_cold/model.json',ROOT/'tools/chapter06/cold/policies.py',ROOT/'tools/chapter06_npcs/huang_v6_policy.py',ROOT/'tools/chapter06_npcs/policies.py',Path(__file__)]+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guards():return {str(p):sha(p) for p in sorted(paths)}
before=guards();assert implementation_digest()=='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b'
h=json.loads(paths[2].read_bytes());c=json.loads(paths[3].read_bytes());reg={**cold(),**huang()}
actor={'id':'unit/peer/coldcaller','kind':'entity','components':{'attributes':{'base':{'max_hp':999}},'resources':{'hp':{'initial':999,'capacity':999,'role':'health'}},'abilities':['ability/peer/cold'],'spatial':{}}}
ability={'id':'ability/peer/cold','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'buff_application','target':'source','application_rule':'rule/ch6/cold/application','allowed':['buff/ch6/cold/e2c_cold','buff/ch6/cold/e2c_freeze'],'parameters':{'duration_seconds':10}}]},'timeline':[]}
unused={'id':'unit/peer/unused','kind':'entity','components':{'abilities':['ability/peer/unused']}}
uability={'id':'ability/peer/unused','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'buff_application','application_rule':'rule/peer/missingprovider','allowed':['buff/peer/unused']}]},'timeline':[]}
urule={'id':'rule/peer/missingprovider','kind':'rule','contract':'buff.application','implementation':{'type':'provider','provider':'not.registered.unused'}}
ubuff={'id':'buff/peer/unused','kind':'buff'}
modules=[('frozenHuang',h),('frozenCold',c),('fresh',{'definitions':[actor,ability,unused,uability,urule,ubuff]})]
scene={'id':'scene/peer/closure','kind':'scenario','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},'objectives':{},'initialEntities':[{'definition':h['entities'][0]['id'],'instanceAlias':'npc','position':{'row':0,'col':0}},{'definition':actor['id'],'instanceAlias':'coldcaller','position':{'row':1,'col':2}}]}
rows=[];captures=[];trial_inputs=[]
def good():
 defs,_=compose_modules(modules);p=Compiler(providers=reg).compile(scene,packages={'schemaVersion':2,'definitions':list(defs.values())});result,report=reachable_content(scene,modules,providers=reg);q=Compiler(providers=reg).compile(result)
 assert all(thaw(getattr(p,k))==thaw(getattr(q,k)) for k in ['definitions','scenario','ruleset','rules'])
 assert set(report['removed_ids'])=={'unit/peer/unused','ability/peer/unused','rule/peer/missingprovider','buff/peer/unused'}
 assert all(id in report['retained_ids'] for id in ['rule/ch6/npc/huang_low_hp_application','rule/ch6/cold/application'])
 assert thaw(p.metadata['providers'])==thaw(q.metadata['providers'])
 assert result['scenarioDraft']==scene
 for d in result['definitions']:assert d==defs[d['id']]
 s=Engine.create(q,providers=reg);s.submit({'action':'skill','source':'coldcaller','ability':'ability/peer/cold'},at=1);s.advance(3);assert any(b['definition']=='buff/ch6/cold/e2c_cold' for b in s.ctx.get('coldcaller',('buffs','instances'),[]))
 captures.append({'package':result,'report':report,'expected_program':p.fingerprint,'pruned_program':q.fingerprint,'provider_locks':thaw(q.metadata['providers']),'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'commands':s.export_replay()})
 return result,p
try:result,program=good()
except Exception as e:rows.append({'case':'actual_source_customprovider_closure_raw_program_unchanged','passed':False,'failure':repr(e)});result=program=None
else:rows.append({'case':'actual_source_customprovider_closure_raw_program_unchanged','passed':True})
def reject(name,fn,data=None):
 trial_inputs.append({'case':name,'data':data})
 try:fn()
 except ValueError as e:rows.append({'case':name,'passed':True,'rejection':str(e)})
 except Exception as e:rows.append({'case':name,'passed':False,'wrong_error':repr(e)})
 else:rows.append({'case':name,'passed':False,'unexpected_acceptance':True})
reject('no_explicit_source_providers',lambda:reachable_content(scene,modules))
for name in ['reference.c6.cold_application','reference.c6.npc_low_hp','reference.c6.npc_owner_heal']:
 bad=reg.copy();bad.pop(name);reject('required_provider_missing_'+name,lambda bad=bad:reachable_content(scene,modules,providers=bad))
bad=reg.copy();bad['reference.c6.npc_low_hp']={'callable':None,'version':'1.0.0'};reject('required_provider_wrong_body',lambda:reachable_content(scene,modules,providers=bad))
wrong=deepcopy(h);wrong['entities'][0]['components']['attributes']['base']['max_hp']+=1;reject('conflicting_source_body',lambda:reachable_content(scene,modules+[('wrong',wrong)],providers=reg),wrong)
wrong=deepcopy(c);r=next(r for r in wrong['rules'] if r['id']=='rule/ch6/cold/application');r['contract']='damage.request';reject('wrong_source_rule_contract',lambda:reachable_content(scene,[('Huang',h),('wrongCold',wrong),modules[-1]],providers=reg),wrong)
wrong=deepcopy(c);r=next(r for r in wrong['rules'] if r['id']=='rule/ch6/cold/application');r['id']='rule/ch6/cold/renamed';reject('missing_allowed_rule_reference',lambda:reachable_content(scene,[('Huang',h),('wrongCold',wrong),modules[-1]],providers=reg),wrong)
replace={actor['id']:{'definition':{'id':actor['id'],'kind':'buff'},'reason':'explicit','source':'fresh'}};reject('replacement_kind_mismatch',lambda:reachable_content(scene,modules,replace,providers=reg),replace)
replace={actor['id']:{'definition':actor,'reason':'','source':'fresh'}};reject('replacement_missing_reason',lambda:reachable_content(scene,modules,replace,providers=reg),replace)
# Versions and callback bodies are part of the compiled identity; module labels are provenance, not an external file-SHA verification interface.
if program:
 changed=reg.copy();changed['reference.c6.npc_low_hp']={**reg['reference.c6.npc_low_hp'],'version':'fresh_identity_2'}
 rr,rp=reachable_content(scene,modules,providers=changed);qq=Compiler(providers=changed).compile(rr);assert qq.fingerprint!=program.fingerprint and thaw(qq.definitions)==thaw(program.definitions);rows.append({'case':'provider_version_pin_changes_program_identity','passed':True})
 after=guards()
else:after=guards()
report={'core':implementation_digest(),'cases':rows,'passed':sum(x['passed'] for x in rows),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Explicit custom providers used in both compile passes; source raw/executable closure and provider-lock equality. Only reachable definitions compiled; unused unknown-provider body deliberately pruned. No semantic acceptance of arbitrary callable provider bodies, external-SHA authentication, source NPC whole/native coroutine claim.'}
for name,obj in [('inputs.json',{'scene':scene,'modules':modules,'negative_inputs':trial_inputs}),('captures.json',captures),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
print(json.dumps({'cases':len(rows),'passed':report['passed'],'sha':sha(OUT/'verification.json'),'guards_equal':before==after,'failures':[r for r in rows if not r['passed']]}))
