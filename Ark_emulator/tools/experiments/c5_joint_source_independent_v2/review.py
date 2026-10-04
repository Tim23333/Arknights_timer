import sys,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/c5_joint_source_independent_v2'
OUT.mkdir(parents=True,exist_ok=False)
BALL=ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/module.v2.reference.json'
FAUST=ROOT/'packages/campaign/chapter05_boss/faust/complete.v2.reference.json'
BRANCH=ROOT/'packages/campaign/chapter05_boss/faust/branch.reference.json'
FILES=[BALL,FAUST,BRANCH,Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py']
FILES+=list((ROOT/'packages/campaign/chapter05_stage_models/combined_v3').glob('*.json'))
FILES+=list((ROOT/'packages/campaign/chapter05_predefines').rglob('*.json'))
FILES+=list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():return {str(p):sha(p) for p in sorted(set(FILES))}
BEFORE=guard();assert implementation_digest()=='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def fixture(mode):
 p=read(FAUST);ball=read(BALL);b=read(BRANCH)
 for k in ['entities','abilities','selectors','rules','definitions','buffs']:
  p.setdefault(k,[]).extend(deepcopy(ball.get(k,[])))
 hero={'id':'unit/independent/ray_target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':30000,'def':100,'block_count':0}},'resources':{'hp':{'initial':30000,'capacity':30000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{'radius':0},'abilities':['ability/independent/retire_boss'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 p['entities'].append(hero)
 p['abilities'].append({'id':'ability/independent/retire_boss','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]},'timeline':[]})
 initial=[{'definition':'unit/ch5/faust/level0','instanceAlias':'boss','position':{'row':0,'col':0}},{'definition':hero['id'],'instanceAlias':'victim','position':{'row':4,'col':7}}]
 if mode=='qualified':
  for name,state,col in [('camouflaged',{'camouflage':True},9),('free',{'target_free':True},8.8),('wrong_category',{'category':4},8.6),('behind',{},5)]:
   definition=deepcopy(hero);definition['id']='unit/independent/'+name;definition['components']['selection_state'].update(state);p['entities'].append(definition)
   initial.append({'definition':definition['id'],'instanceAlias':name,'position':{'row':4,'col':col}})
 initial+=deepcopy(ball['manifest']['metadata']['native_predefined_profiles']['level_main_05-10']['initial_entities'])
 p['scenarioDraft']={'id':'scene/independent/c5_joint/'+mode,'ruleset':'ruleset/ark_standard','rules':deepcopy(p['manifest']['metadata']['stage_rules']),'branches':{'faust_ballis':deepcopy(b['program'])},'map':{'rows':8,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':0,'capacity':99}},'objectives':{'life_resource':'life'},'initialEntities':initial}
 return p
def events(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def run_case(mode):
 p=fixture(mode);(OUT/(mode+'.input.json')).write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
 s=Engine.create(Compiler().compile(p),seed=99105);ids={f'trap_007_ballis#{i}':s.session.world.resolve(f'trap_007_ballis#{i}') for i in range(1,11)}
 if mode=='cancel':s.submit({'action':'skill','source':'victim','ability':'ability/independent/retire_boss'},at=476)
 s.advance(476)
 assert not any(s.ctx.active(v) for v in ids.values())
 cp=OUT/(mode+'.ordered.cp.json');h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h))
 s.advance(177);r.advance(177)
 capture={'input':p,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'disk_sha':h}
 (OUT/(mode+'.capture.json')).write_text(json.dumps(capture,ensure_ascii=False),encoding='utf8')
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==r.snapshot()
 rr=replay(s.program,s.export_replay());assert s.checkpoint()==rr.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(rr.session.events))
 if mode=='cancel':
  assert not events(s,'entity.activated') and not any(s.ctx.active(v) for v in ids.values());assert s.ctx.branches.state()['faust_ballis']['cursor']==0
 else:
  assert [(e['time'],e['payload']['ability']) for e in events(s,'ability.started') if e['payload']['source']==2]==[(0,'ability/ch5/faust/normal'),(150,'ability/ch5/faust/normal'),(300,'ability/ch5/faust/normal'),(450,'ability/ch5/faust/summon_ballis'),(600,'ability/ch5/faust/critical')]
  assert [(e['time'],e['payload']['target']) for e in events(s,'entity.activated')]==[(477,ids['trap_007_ballis#1'])]
  assert s.ctx.branches.state()['faust_ballis']['cursor']==1
  trap=ids['trap_007_ballis#1'];assert s.ctx.attributes.values(trap)['max_hp']==100 and s.ctx.attributes.values(trap)['atk']==600
  starts=[e for e in events(s,'ability.started') if e['payload']['source']==trap];assert len(starts)==1 and starts[0]['time']==628
  payments=[e for e in events(s,'resource.changed') if e['payload']['target']==trap and e['payload']['resource']=='sp' and e['payload']['delta']<0];assert [(e['time'],e['payload']['delta'],e['payload']['value']) for e in payments]==[(628,-5,0)]
  hits=[e for e in events(s,'damage.accepted') if e['payload']['source']==trap];assert len(hits)==1 and hits[0]['payload']['target']==s.session.world.resolve('victim') and hits[0]['payload']['amount']==500 and hits[0]['time']==642 and hits[0]['payload']['damage_flags']=={'source_attack_type':'NORMAL','ignore_for_sp':False}
  assert all(not s.ctx.active(ids[f'trap_007_ballis#{i}']) for i in range(2,11))
 return {'mode':mode,'event_count':len(s.session.events),'disk_sha':h}
RESULTS=[]
for mode in ['natural','qualified','cancel']:
 try:RESULTS.append({'passed':True,**run_case(mode)})
 except Exception:RESULTS.append({'mode':mode,'passed':False,'error':traceback.format_exc()})
AFTER=guard();report={'core':implementation_digest(),'scope':'Independent controlled actual first branch and ballista consumer; not whole-stage or client acceptance','results':RESULTS,'guards_before':BEFORE,'guards_after':AFTER,'guards_equal':BEFORE==AFTER}
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'results':RESULTS,'report':str(OUT/'verification.json'),'sha':sha(OUT/'verification.json'),'guards_equal':BEFORE==AFTER},ensure_ascii=False))
