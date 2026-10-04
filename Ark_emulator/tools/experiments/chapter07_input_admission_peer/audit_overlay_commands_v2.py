import json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter07_inputs_overlay_peer_v2';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
files=[Path(__file__)];rows=[]
for sid,births in [('level_main_07-15',37),('level_main_07-16',45)]:
 parent=ROOT/'packages/campaign/chapter07_stage_models'/(sid+'.native_draft.v2.json');overlay=parent.with_name(sid+'.native_draft.v2.life99999.strict_v2.json');cmd=ROOT/'scenarios/campaign/chapter07'/sid/'public_plan_v2/commands.json';files += [parent,overlay,cmd];a=load(parent);b=load(overlay);commands=load(cmd);restored=deepcopy(b);goal=restored['manifest']['metadata'].pop('goal_base_life_authoring');profile=restored['scenarioDraft']['metadata'].pop('runthrough_profile');assert goal['selected_initial']==goal['selected_capacity']==99999 and type(goal['selected_initial']) is int and exact(goal['native'],a['scenarioDraft']['resources']['life']);assert profile['public_commands_sha256']==sha(cmd) and profile['source_births']==births and profile['deploy_capacity']==9 and exact(profile['fixed12'],a['scenarioDraft']['roster']);restored['scenarioDraft']['resources']['life']=deepcopy(a['scenarioDraft']['resources']['life']);assert exact(restored,a)
 defs={d['id']:d for d in a['definitions']};aliases={};deploys=[];skills=[];last=-1
 for c in commands:
  assert type(c['at']) is int and c['at']>=last;last=c['at'];kind=c['action']
  if kind=='deploy':
   eid=c.get('entity',c.get('definition'));assert eid in a['scenarioDraft']['roster']+a['scenarioDraft'].get('cards',[]) and c['alias'] not in aliases;aliases[c['alias']]=eid;deploys.append(eid);assert type(c['row']) is int and type(c['col']) is int and 0<=c['row']<a['scenarioDraft']['map']['rows'] and 0<=c['col']<a['scenarioDraft']['map']['cols'];tile=a['scenarioDraft']['map']['tiles'][c['row']*a['scenarioDraft']['map']['cols']+c['col']];terrain=defs[eid]['components']['deployable']['terrain'];mask={'ground':1,'highland':2,'high':2,'any':3}[terrain];assert tile['buildableType']&mask
  elif kind=='skill':assert c['source'] in aliases and c['ability'] in defs[aliases[c['source']]]['components']['abilities'];skills.append(c['ability'])
  elif kind=='withdraw':assert c['source'] in aliases
  else:raise ValueError('Unexpected command type '+kind)
 assert set(a['scenarioDraft']['roster'])<=set(deploys)
 negatives=[]
 for name,key,value in [('slots','deploy_capacity',True),('slots','deploy_capacity',12)]:
  dirty=deepcopy(restored);dirty['scenarioDraft']['parameters'][key]=value;assert not exact(dirty,a);negatives.append(name+str(value))
 dirty=deepcopy(restored);dirty['definitions'][0]['id']+='bad';assert not exact(dirty,a);negatives.append('definition_mutation')
 rows.append({'stage':sid,'source_package_sha':sha(parent),'overlay_sha':sha(overlay),'commands_sha':sha(cmd),'births':births,'life_only_type_exact':True,'negative_changes_rejected':negatives,'selected_roster':a['scenarioDraft']['roster'],'cards':a['scenarioDraft'].get('cards',[]),'scheduled_selected_deploy_ids':deploys,'command_count':len(commands),'selected_skill_and_terrain_bindings_static_valid':True,'actual_acceptance_and_deployment_coverage':'Pending actual whole outcomes; time plan does not guarantee all12 remain deployable/affordable/alive or allskills accepted.'})
before={str(p):sha(p) for p in files};report={'passed':True,'stages':rows,'source_guards':before,'guards_end':{str(p):sha(p) for p in files},'scope':'Read-only lifeonly/profile/command data bindings; no execution/registry/fullstage approval. Metadata_false is not auto refusal; executable profile selected explicitly.'};assert report['source_guards']==report['guards_end']
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'commands':[r['command_count'] for r in rows]}))
