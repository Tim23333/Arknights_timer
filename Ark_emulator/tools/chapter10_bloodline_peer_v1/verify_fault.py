"""Fresh bloodline peer; frozen core argument mandatory before any actual run."""
import os,sys,json,hashlib,traceback,math,re
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c10_bloodline_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT));EXPECTED=sys.argv[1]
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter10_bloodline_v1.build import providers,KEYS,entity_id,BLOCK
from tools.chapter10_bloodline_peer_v1.fixtures import resistance_scene,death_scene,blocking_scene
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
assert implementation_digest()==EXPECTED
OUT=ROOT/'validation/campaign/chapter10_bloodline_peer_v1';OUT.mkdir(parents=True,exist_ok=True);LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();RESULT=[];FACT={};ART=[]
def create(p,reg=None):return Engine.create(Compiler(providers=reg or REG).compile(p),providers=reg or REG,seed=3491977747)
def cpp(p,end,pins,label):
 a=create(p);a.advance(end);b=create(p)
 for tick in pins:
  b.advance(tick-b.session.time);f=LOG/(label+str(tick)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});b=Engine.restore(b.program,load_bound(f,h),providers=REG)
 b.advance(end-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==h.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==h.session.random.snapshot();return a

def resistance():
 p=resistance_scene();s=cpp(p,40,[10,25],'DR');events=[thaw(e) for e in s.session.events if e['type']=='damage.accepted'];facts=[]
 for key in KEYS:
  target=s.session.world.resolve(key);attrs=s.ctx.entity(target)['components']['attributes']['base'];reduced='dzoms' in key or 'dzomg' in key
  expected={'physical':max(331-attrs['def'],331*.05)*(0.1 if reduced else 1),'arts':331*(1-attrs['mres']*.01)*(0.1 if reduced else 1),'true':331}
  hits={e['payload']['ability'].rsplit('/',1)[1]:e['payload']['amount'] for e in events if e['payload']['target']==target};facts.append({'key':key,'expected':expected,'actual':hits,'native_HP':attrs['max_hp'],'native_def':attrs['def'],'native_res':attrs['mres'],'death_spawns':thaw(s.ctx.get(target,('lifecycle','death_spawns')))})
 FACT['DR_facts']=facts
 for f in facts:
  assert set(f['actual'])==set(f['expected']) and all(math.isclose(f['actual'][k],v,abs_tol=1e-8) for k,v in f['expected'].items())
  assert bool(f['death_spawns'])==('dpvt' in f['key'])

def death():
 p=death_scene();s=cpp(p,60,[12,40,42],'death');ledger=thaw(s.ctx.state()['death_spawns']);entry=next(iter(ledger.values()));row=entry['rows'][0];child=row['child'];issued=next(thaw(e) for e in s.session.events if e['id']==entry['issued_event']);births=[thaw(e) for e in s.session.events if e['type']=='descendant.born'];before=issued['payload']['snapshot']['components']['spatial'];now=thaw(s.ctx.entity(child));FACT['death_facts']={'ledger':ledger,'births':births,'snapshot_spatial':before,'child':now,'pending_waves':s.ctx.state()['pending_waves'],'timeline':thaw(s.ctx.state()['timeline']),'keeper_HP':s.ctx.resources.current('keeper','hp')}
 assert len(births)==1 and births[0]['time']==41 and row['due']==41 and row['status']=='born';assert now['definition_id']==entity_id('enemy_1220_dzoms_2');assert now['components']['spatial']['movement']['wait_until']==before['movement']['wait_until'];assert now['components']['spatial']['timing_origins']==before['timing_origins'];assert now['components']['spatial']['route']['endPosition']=={'row':3,'col':11};assert s.ctx.state()['pending_waves']==0 and s.ctx.alive(child) and s.ctx.alive('keeper');assert s.ctx.resources.current('keeper','hp')==34919
 origin=before['position'];pos=births[0]['payload']['position'];assert all(abs(pos[k]-origin[k])<=.10000000149011612 for k in ['row','col']);assert str(child) in s.ctx.state()['timeline']['members'];FACT['public_death11_birth41_real_route_WAIT_offsets_RNG_CPP']=True

def blocking():
 p=blocking_scene();s=create(p);s.advance(3);blocker=s.session.world.resolve('blocker');owned=[e for e in s.session.world.entities() if e['components'].get('runtime',{}).get('blocked_by')==blocker];instances=thaw(s.ctx.buffs._instances(blocker));child=next(b for b in instances if b['definition']==BLOCK);FACT['blocking_initial']={'actual_blockers':[e['id'] for e in owned],'block_count':s.ctx.attributes.value(blocker,'block_count'),'child':child};assert len(owned)==7 and s.ctx.attributes.value(blocker,'block_count')==7 and len(child['aura_leases'])==7
 old_source=child['source'];old_id=child['id'];s.ctx.effects.execute('system/battle',[old_source],{'op':'retire','parameters':{'reason':'withdraw'}});s.advance(1);child=next(b for b in s.ctx.buffs._instances(blocker) if b['definition']==BLOCK);FACT['blocking_rebind']={'source':child['source'],'id':child['id'],'leases':thaw(child['aura_leases']),'block_count':s.ctx.attributes.value(blocker,'block_count')};assert child['source']!=old_source and child['id']==old_id
 for e in list(s.session.world.entities()):
  if e['definition_id']==entity_id('enemy_1220_dzoms_2') and s.ctx.active(e['id']):s.ctx.effects.execute('system/battle',[e['id']],{'op':'retire','parameters':{'reason':'withdraw'}})
 s.advance(1);assert not any(b['definition']==BLOCK for b in s.ctx.buffs._instances(blocker)) and s.ctx.attributes.value(blocker,'block_count')==1;FACT['actual_shared_lease_cap6_source_release_no_unblocked_buff']=True

def paths(obj,test,path=()):
 if isinstance(obj,dict):
  for k,v in obj.items():
   if test(k,v):yield path+(k,)
   yield from paths(v,test,path+(k,))
 elif isinstance(obj,list):
  for i,v in enumerate(obj):yield from paths(v,test,path+(i,))
def get(obj,path):
 for key in path:obj=obj[key]
 return obj
def replace(obj,path,value):
 owner=get(obj,path[:-1]);owner[path[-1]]=value

def restore_security():
 p=death_scene();s=create(p);s.advance(12);cp=s.checkpoint();state=thaw(s.ctx.state()['death_spawns']);ledgerpath=next(paths(cp['kernel']['world'],lambda k,v:k=='death_spawns' and v==state));ledgerpath=('kernel','world')+ledgerpath;facts=[]
 def denied(label,mutate,checkpoint=cp):
  bad=deepcopy(checkpoint);mutate(bad)
  try:Engine.restore(s.program,bad,providers=REG)
  except Exception as e:facts.append({'case':label,'rejected':True,'exception':type(e).__name__,'message':str(e)})
  else:facts.append({'case':label,'rejected':False})
 denied('pending_missing_ledger',lambda c:replace(c,ledgerpath,{}));denied('wrong_due',lambda c:next(iter(get(c,ledgerpath).values()))['rows'][0].update(due=42));denied('copied_parent_lineage',lambda c:next(iter(get(c,ledgerpath).values()))['stamp'].update(life=999))
 s.advance(30);born=s.checkpoint();bornstate=thaw(s.ctx.state()['death_spawns']);bornpath=('kernel','world')+next(paths(born['kernel']['world'],lambda k,v:k=='death_spawns' and v==bornstate));denied('born_missing_ledger',lambda c:replace(c,bornpath,{}),born)
 lineagepath=('kernel','world')+next(paths(born['kernel']['world'],lambda k,v:k=='spawn_lineage'))
 denied('born_foreign_parent',lambda c:get(c,lineagepath).update(parent=999),born)
 FACT['restore_security']=facts;assert all(f['rejected'] for f in facts)

def direct_permission():
 s=create(death_scene());s.advance(12);entry=next(iter(s.ctx.state()['death_spawns'].values()));payload={'ledger':str(entry['source'])+'/'+str(entry['stamp']['death']),'slot':entry['rows'][0]['slot']};before=s.checkpoint()
 try:s.ctx.death_spawns._dispatch(s.session,payload)
 except Exception as e:FACT['direct_dispatch']={'exception':type(e).__name__,'message':str(e)}
 else:raise AssertionError('Direct callback granted postdeath spawn')
 assert before==s.checkpoint();before=s.checkpoint()
 try:s.ctx.death_spawns.issue(entry['source'],entry['death_event'])
 except Exception as e:FACT['repeat_issuance']={'exception':type(e).__name__,'message':str(e)}
 else:raise AssertionError('Repeated same death granted additional spawn')
 assert before==s.checkpoint()

def fault():
 p=death_scene();child=next(e for e in p['entities'] if e['id']==entity_id('enemy_1220_dzoms_2'));child['components']['resources']['hp']['capacity_rule']='rule/independent/capacityfault';p['rules'].append({'id':'rule/independent/capacityfault','kind':'rule','contract':'resource.capacity','implementation':{'type':'provider','provider':'independent.capacityfault'}})
 reached=[]
 def fail(inputs,params,context):
  reached.append({'rng_count':s.session.random.snapshot(),'task':s.session.current_task})
  raise ValueError('blood-peer-capacity-after-RNG')
 reg={**REG,'independent.capacityfault':{'callable':fail,'version':'peer-fresh-child-late-fault-v1'}};s=create(p,reg);s.advance(41);observed=[]
 def stores():return {'world':s.session.world.snapshot(),'jobs':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'events':thaw(list(s.session.events)),'cache':s.ctx.attributes.checkpoint_cache()}
 def capture():
  task=s.session.current_task
  return {'task':task,'depth':s.session._atomic_depth,'stores':stores()} if task and task['kind']=='domain.death_spawn' else None
 def restore(saved):
  if saved is not None:observed.append({'task':saved['task'],'depth':saved['depth'],'before':saved['stores'],'after':stores()})
 s.session.register_atomic_participant('peer.actual_death_fault_stores',capture,restore)
 before=s.checkpoint();path=LOG/'before-fault.checkpoint.json';pin=write_ordered(path,before);ART.append({'path':str(path),'sha256':pin,'bytes':path.stat().st_size})
 try:s.advance(1)
 except Exception as e:FACT['fault_exception']={'type':type(e).__name__,'message':str(e)};assert 'blood-peer-capacity-after-RNG' in str(e)
 else:raise AssertionError('Real child callback did not reach fault provider')
 FACT['fault_reached']=reached;assert reached and reached[0]['task']['kind']=='domain.death_spawn'
 outer=[o for o in observed if o['depth']==0];assert len(outer)==1
 proof=outer[0];equal={key:proof['before'][key]==proof['after'][key] for key in proof['before']};FACT['fault_full_store_equality']=equal;FACT['fault_boundary']={'actual_task':proof['task'],'capture_depth':proof['depth'],'failure_checkpoint_available':True}
 facts=LOG/'actual-fault-stores.json';facts.write_text(json.dumps(proof,indent=2),encoding='utf8');ART.append({'path':str(facts),'sha256':hashlib.sha256(facts.read_bytes()).hexdigest(),'bytes':facts.stat().st_size});assert all(equal.values())
 restored=Engine.restore(s.program,load_bound(path,pin),providers=reg);assert restored.checkpoint()==before;FACT['restore_prefault_CP_full_equal']=True

def guard():
 assert implementation_digest()==EXPECTED
 files=[ROOT/'tools/chapter10_bloodline_v1/build.py',Path(__file__),Path(__file__).with_name('fixtures.py'),ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json',ROOT/'packages/campaign/chapter10_source_prepare/bson.transitive.v2.json']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts]
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
BEFORE=guard()
try:fault();RESULT.append({'case':'real_postdeath_child_fault_five_stores_and_restore','passed':True})
except Exception:RESULT.append({'case':'real_postdeath_child_fault_five_stores_and_restore','passed':False,'traceback':traceback.format_exc()})
after=guard();r={'core':EXPECTED,'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'comparison_exclusions':[],'whole_stage':False};(OUT/'peer.faultactual.v2.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({'results':RESULT,'actual_exit':r['actual_exit']}));raise SystemExit(r['actual_exit'])
