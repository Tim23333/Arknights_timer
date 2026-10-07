"""Independent frozen merge and actual simultaneous chain/death CPP."""
import sys,os,json,hashlib,ast,math,traceback
from pathlib import Path
from copy import deepcopy
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c10_joint_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter10_bloodline_v1.build import providers,entity_id
from tools.chapter10_bloodline_peer_v1.fixtures import death_scene
from tools.chapter10_chain_v1.native_module import mount
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
CORE='9a7d4a01b7fe0a8d77a39e4b280b330e65670349b6fb2716c1319dabcc491ed9';assert implementation_digest()==CORE
MERGE=ROOT/'validation/campaign/chapter10_joint_v1/merge.v2.json';record=json.loads(MERGE.read_bytes());REG=providers();LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter10_joint_peer_v1';OUT.mkdir(parents=True,exist_ok=True);FACT={};RESULT=[];ART=[];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def literals(tree):
 result={}
 for n in tree.body:
  if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
   try:value=ast.literal_eval(n.value)
   except Exception:continue
   if isinstance(value,dict) and all(isinstance(v,set) for v in value.values()):result[n.targets[0].id]=value
 return result

def merge_gate():
 assert record['core']==CORE
 for p,h in record['source_freezes'].items():assert sha(Path(p))==(record['builder_current_sha256'] if p.endswith('build_candidate.py') else h)
 for path,h in record['inventory'].items():assert sha(CAND/'ark_sim'/path)==h
 base=ROOT/'ark_sim';blood=ROOT.parent/'unpack_work/campaign_c10_bloodline_v1_candidate/ark_sim';chain=ROOT.parent/'unpack_work/campaign_c10_chain_v1_candidate/ark_sim';overlaps={x['file'] for x in record['differences'] if x['origin']=='three_way_blood_plus_chain'};assert overlaps=={'adapters/api.py','content/capabilities.py','content/schemas.py'};assert len(record['differences'])==11
 for d in record['differences']:
  if d['file'] not in overlaps:assert sha(CAND/'ark_sim'/d['file'])==sha((blood if d['origin']=='blood' else chain)/d['file'])
 unchanged=set(record['inventory'])-{d['file'] for d in record['differences']}
 for path in unchanged:assert sha(CAND/'ark_sim'/path)==sha(base/path)
 proof={}
 for path in overlaps:
  trees={k:ast.parse((folder/path).read_text(encoding='utf8')) for k,folder in [('base',base),('blood',blood),('chain',chain),('joint',CAND/'ark_sim')]};ls={k:literals(t) for k,t in trees.items()}
  for name in ls['joint']:
   for key,value in ls['joint'][name].items():assert value==ls['blood'].get(name,{}).get(key,set())|ls['chain'].get(name,{}).get(key,set())
  def terminal(t):return Counter(ast.dump(n,include_attributes=False) for n in ast.walk(t) if isinstance(n,(ast.Import,ast.ImportFrom,ast.Expr,ast.Return,ast.Raise,ast.Assert)))
  counts={k:terminal(t) for k,t in trees.items()}
  for parent in ['blood','chain']:
   for node,n in (counts[parent]-counts['base']).items():assert counts['joint'][node]>=n
  proof[path]={'field_set_union_exact':True,'new_terminal_statements_preserved_both_parents':True}
 FACT['merge']={'overlaps':proof,'nonconflict8_exact':True,'allCDF_other_sources_unchanged':True,'all_inventory_SHA_exact':True}

def fixture():
 p=death_scene();mage={'id':'unit/independent/joint/mage','kind':'entity','tags':['enemy','mage'],'components':{'attributes':{'base':{}},'resources':{'hp':{'role':'health','initial':16000,'capacity':16000}},'selection_state':{'side':1,'category':1,'motion':1,'unit_type':2},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}};provenance=mount(p,mage);mage['components']['attributes']['base']=deepcopy(provenance['source_attributes']);mage['metadata']={'sourced_fragment':provenance};p['entities'].append(mage);public='ability/independent/joint/public_chain';p['abilities'].append({'id':public,'kind':'ability','activation':{'mode':'manual'},'parameters':{'blocks_attacks':False},'timeline':[{'at':0,'effects':[{'op':'modify_resource','target':'source','resource':'peer_cast_gate','value':1},{'op':'trigger_ability','target':'source','ability':'ability/c10/dkmage_chain'}]}]});mage['components']['abilities'].append(public);mage['components']['resources']['peer_cast_gate']={'initial':0,'capacity':1};next(a for a in p['abilities'] if a['id']=='ability/c10/dkmage_chain')['activation']['condition']='inputs.source.components.resources.peer_cast_gate.current == 1'
 p['buffs'].append({'id':'buff/independent/joint/atk250','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':250}]});mage['dependencies']=['buff/independent/joint/atk250']
 p['scenarioDraft']['initialEntities'].append({'definition':mage['id'],'instanceAlias':'mage','position':{'row':4,'col':4}})
 profile={'capacity':10000,'resistance':0,'recovery_rate':0,'break_duration_seconds':1,'rules':{k:'rule/c10/dkmage_chain/ep_'+k.rsplit('.',1)[1] for k in ['elemental.capacity','elemental.loss','elemental.recovery','elemental.break_duration']},'on_break':[],'on_end':[]}
 for i,(col,res) in enumerate([(6,33),(7.5,14),(9,25)]):
  eid='unit/independent/joint/target'+str(i);p['entities'].append({'id':eid,'kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':31997,'atk':0,'def':900,'mres':res}},'resources':{'hp':{'role':'health','initial':31997,'capacity':31997}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'elemental':{'eligibility_rule':'rule/c10/dkmage_chain/ep_eligible','elements':{'DARK':deepcopy(profile)}},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']['initialEntities'].append({'definition':eid,'instanceAlias':'chainTarget'+str(i),'position':{'row':4,'col':col}})
 p['scenarioDraft']['commands'].insert(0,{'at':0,'action':'skill','source':'mage','ability':public});mage_index=len(p['scenarioDraft']['initialEntities'])-3;# caster1, mage2, targets3..5, timeline parent/keeper later
 p['scenarioDraft']['scheduledEffects']=[{'at':39,'effect':{'op':'apply_buff','target':3,'buff':'buff/independent/joint/atk250'}}]
 # Entity IDs follow initial registration order: battle1,caster2,mage3.
 return p

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=61947747)
def run_combination():
 p=fixture();a=create(p);a.advance(80);b=create(p);overlap={}
 for tick in [40,43,48]:
  b.advance(tick-b.session.time)
  if tick==40:
   ledger=thaw(b.ctx.state()['death_spawns']);projectiles=thaw(b.ctx.projectiles._state());overlap={'tick':tick,'ledger':ledger,'projectiles':projectiles};assert next(iter(ledger.values()))['rows'][0]['status']=='pending';assert any(x['state']=='active' and 'chain' in x for x in projectiles['instances'].values())
  path=LOG/(str(tick)+'.checkpoint.json');h=write_ordered(path,b.checkpoint());ART.append({'path':str(path),'sha256':h,'bytes':path.stat().st_size});b=Engine.restore(b.program,load_bound(path,h),providers=REG)
 b.advance(80-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==h.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==h.session.random.snapshot()
 births=[thaw(e) for e in a.session.events if e['type']=='descendant.born'];hits=[thaw(e) for e in a.session.events if e['type']=='damage.accepted' and e['payload'].get('ability')=='ability/c10/dkmage_chain'];hp=[a.ctx.resources.current('chainTarget'+str(i),'hp') for i in range(3)];ep=[thaw(a.ctx.get('chainTarget'+str(i),('runtime','elemental'))) for i in range(3)];FACT['combination']={'overlap':overlap,'births':births,'chain_damage':hits,'HP':hp,'EP':ep,'chain_events':[thaw(e) for e in a.session.events if e['type'].startswith('projectile.chain')],'child_member':thaw(a.ctx.state()['timeline']['members'].get(str(births[0]['payload']['child'])))}
 assert len(births)==1 and births[0]['time']==41 and a.ctx.alive(births[0]['payload']['child']);assert len(hits)==3
 expected=[800*.67,800*.85*.86,800*.85**2*.75];assert all(math.isclose(31997-hp[i],expected[i],abs_tol=1e-8) for i in range(3));assert all(math.isclose(ep[i]['remaining']['DARK'],10000-800*.3*.85**i,abs_tol=1e-8) for i in range(3));assert FACT['combination']['child_member']['wave']==0;assert a.ctx.get(births[0]['payload']['child'],('runtime','spawn_lineage'))['parent']==a.session.world.resolve('parent');assert a.ctx.resources.current('keeper','hp')==34919

def find(obj,key,condition=lambda x:True,path=()):
 if isinstance(obj,dict):
  for k,v in obj.items():
   if k==key and condition(v):yield path+(k,)
   yield from find(v,key,condition,path+(k,))
 elif isinstance(obj,list):
  for i,v in enumerate(obj):yield from find(v,key,condition,path+(i,))
def get(obj,path):
 for key in path:obj=obj[key]
 return obj

def permissions():
 s=create(fixture());s.advance(40);cp=s.checkpoint();instances=thaw(s.ctx.projectiles._state()['instances']);x=next(v for v in instances.values() if v['state']=='active' and 'chain' in v);path=next(find(cp['kernel']['world'],'chain',lambda v:isinstance(v,dict) and 'hop' in v));bad=deepcopy(cp);get(bad,('kernel','world')+path)['hop']+=1
 try:Engine.restore(s.program,bad,providers=REG)
 except Exception as e:FACT['chain_hop_tamper_rejected']={'type':type(e).__name__,'message':str(e)}
 else:raise AssertionError('Single-field chain hop restore tamper accepted')
 before=s.checkpoint();task=next(t for t in s.session.scheduler.pending if t['kind']=='domain.projectile.step' and t['payload']['projectile']==x['id'])
 try:s.ctx.projectiles.step(s.session,deepcopy(task['payload']))
 except Exception as e:FACT['direct_chain_step_rejected']={'type':type(e).__name__,'message':str(e)}
 else:raise AssertionError('Direct chain callback granted impact permission')
 assert s.checkpoint()==before

def guard():
 assert implementation_digest()==CORE
 files=[MERGE,Path(__file__),ROOT/'tools/chapter10_bloodline_peer_v1/fixtures.py',ROOT/'tools/chapter10_bloodline_v1/build.py',ROOT/'tools/chapter10_chain_v1/native_module.py',ROOT/'tools/chapter10_chain_v1/fixture.py']+[CAND/'ark_sim'/p for p in record['inventory']]+[Path(p) for p in record['source_freezes']]
 return {str(p):sha(p) for p in files}
BEFORE=guard()
for name,fn in [('frozen_three_overlap_union_and8exact_source_merge',merge_gate),('public_death_and_three_impacts_simultaneous_CPPhead',run_combination),('single_field_restore_and_illegal_chain_task_scope',permissions)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'comparison_exclusions':[],'whole_stage':False};(OUT/'peer.fixturefixed.v3.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'actual_exit':r['actual_exit'],'results':RESULT}));raise SystemExit(r['actual_exit'])
