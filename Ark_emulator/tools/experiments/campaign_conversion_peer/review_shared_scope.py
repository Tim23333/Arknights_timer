"""Bounded frozen shared-actor scope. Genuine multi-case execution, no fake sims."""
import sys,json,hashlib,importlib,inspect,ast
from pathlib import Path
from collections import Counter
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m12_projection_candidate'))
sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools import propose_witness_scope_00_11 as proposal
CORE=proposal.CORE
SOURCE=proposal.BASELINE
TARGETS={'m14':ROOT/'packages/campaign/mainline_models/level_main_00-10.m14_timeline.json','00_11':proposal.SOURCE}
MULTI={'bpipe_deck_sp_and_refund_cap','failed_dp_and_position','bird_enemy_death_and_owner_retire','taunt_filter_and_retire','sp_near_and_far'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str).encode()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def result_roundtrips(v):
 out=[]
 if isinstance(v,dict):
  if 'checkpoint_equal' in v:out.append({k:v.get(k) for k in ('checkpoint_equal','replay_equal','program_fingerprint','runtime_fingerprint','tick')})
  for x in v.values():out.extend(result_roundtrips(x))
 elif isinstance(v,list):
  for x in v:out.extend(result_roundtrips(x))
 return out

def execute_multi(modules,fn,target,name):
 changes=[];makes=[]
 try:
  for m in modules:
   if hasattr(m,'PACKAGE'):changes.append((m,'PACKAGE',m.PACKAGE));m.PACKAGE=target
   if hasattr(m,'make') and callable(m.make):
    original=m.make;changes.append((m,'make',original));signature=inspect.signature(original)
    def record(*args,_fn=original,_sig=signature,**kwargs):
     b=_sig.bind(*args,**kwargs);b.apply_defaults();data=b.arguments['data'];seed=b.arguments.get('seed',11)
     sim=_fn(*args,**kwargs)
     assert hasattr(sim,'session') and sim.__class__.__module__.startswith('ark_sim')
     makes.append({'seed':seed,'fixture_sha256':identity(data),'program_fingerprint':sim.program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,'scenario':thaw(sim.program.scenario),'loaded_source_anchor':data['manifest']['metadata']['dependency_source']['native_level_sha256'],'reachable_definitions':{i:identity(thaw(sim.program.definitions[i])) for i in sim.program.dependency_ids if sim.program.definitions[i]['kind']!='scenario'},'rule_fingerprint':sim.ctx.rules.fingerprint,'provider_fingerprint':identity({n:thaw(v[2]) for n,v in sim.ctx.rules.providers.items()}),'initial_world_sha256':identity(sim.session.world.snapshot()),'initial_rng_sha256':identity(sim.session.random.snapshot())})
     return sim
    m.make=record
  result=fn();roundtrips=result_roundtrips(result)
  assert len(makes)>=2 and len(roundtrips)==len(makes) and all(x['checkpoint_equal'] and x['replay_equal'] for x in roundtrips)
  assert Counter(x['program_fingerprint'] for x in roundtrips)==Counter(x['program_fingerprint'] for x in makes)
  return {'passed':True,'case':name,'target_content_sha256':sha(target),'implementation_sha256':CORE,'actual_make_inputs':makes,'per_fixture_roundtrips':roundtrips,'actual_original_assertion_result':result,'scope':'Target original function genuinely executed; original helper and assertions unchanged','tests':[]}
 finally:
  for m,k,v in reversed(changes):setattr(m,k,v)

def run():
 assert implementation_digest()==CORE
 modules=[importlib.import_module('tools.'+n) for n in proposal.MODULES]
 paths=[Path(m.__file__) for m in modules]+[Path(__file__),SOURCE,*TARGETS.values()]
 hashes={str(p):sha(p) for p in paths}
 # Frozen runtime source audit: domains pass scenario.rules/parameters/map/etc,
 # never scenario.metadata into calculators/providers. Program.metadata is distinct
 # compiler/catalog descriptor and must not be mistaken for scenario metadata.
 core=ROOT.parent/'unpack_work/campaign_m12_projection_candidate/ark_sim'
 consumers=[]
 for p in sorted(core.rglob('*.py')):
  text=p.read_text(encoding='utf8');ast.parse(text)
  lines=[{'line':i,'text':l.strip()} for i,l in enumerate(text.splitlines(),1) if 'scenario' in l and ('metadata' in l or '.get(' in l)]
  if lines:consumers.append({'path':str(p),'sha256':sha(p),'scenario_accesses':lines})
 assert not any("scenario.get(\"metadata\"" in r['text'] or "scenario['metadata']" in r['text'] or 'scenario["metadata"]' in r['text'] for f in consumers for r in f['scenario_accesses'])
 helper_metadata=[]
 for m in modules:
  lines=[{'line':i,'text':l.strip()} for i,l in enumerate(Path(m.__file__).read_text(encoding='utf8').splitlines(),1) if 'metadata' in l]
  helper_metadata.append({'path':str(Path(m.__file__).relative_to(ROOT)).replace('\\','/'),'lines':lines})
 source_multis={}
 for m in modules:
  for name,fn in getattr(m,'CASES',{}).items():
   if name in MULTI:
    print(json.dumps({'target':'source0fb_new_independent_scope','execute':name}),flush=True)
    actual=execute_multi(modules,fn,SOURCE,name);path=ROOT/f'validation/campaign/shared_actor_source0fb_{name}.json';write(path,actual);source_multis[name]=(actual,path)
 for label,target in TARGETS.items():
  rows=[]
  for m in modules:
   cases=getattr(m,'CASES',None)
   if cases is None:cases={'probe':m.probe} if m.__name__.endswith('witness_canonical_lisk_defense') else {'friend_damage_capacity_source_exit':m.run} if m.__name__.endswith('witness_angel_blessing_damage') else {}
   for name,fn in cases.items():
    row={'helper_path':str(Path(m.__file__).relative_to(ROOT)).replace('\\','/'),'helper_sha256':sha(m.__file__),'case':name,'source_content_sha256':sha(SOURCE),'target_content_sha256':sha(target),'target_case_executed':False}
    a,b=proposal.capture(modules,fn,SOURCE),proposal.capture(modules,fn,target)
    if not isinstance(a,proposal.CapturedFixture) or not isinstance(b,proposal.CapturedFixture):
     assert isinstance(a,dict) and isinstance(b,dict) and a['status']==b['status']=='source_config_only' and a['actual_static_result']==b['actual_static_result']
     row.update(status='static_source_only',source_static_result=a,target_static_result=b,approved_for_battle_witness=False)
    else:
     proof=proposal.evaluate(a,b)
     actualanchor=json.loads(target.read_bytes())['manifest']['metadata']['dependency_source']['native_level_sha256']
     loader=proof['source_loader_anchor']==json.loads(SOURCE.read_bytes())['manifest']['metadata']['dependency_source']['native_level_sha256'] and proof['target_loader_anchor']==actualanchor
     structural=loader and proof['dependency_id_sets_equal'] and not proof['changed_reachable_definitions'] and proof['effective_scenario_inputs_equal'] and set(proof['scenario_changed_keys'])<={'metadata','seed'} and proof['source_rule_fingerprint']==proof['target_rule_fingerprint'] and proof['provider_descriptors_equal'] and proof['initial_world_equal'] and proof['initial_events_equal'] and proof['initial_rng_equal']
     proof['actual_target_loader_anchor_verified']=loader;proof['structural_equivalence_candidate']=structural
     row.update(proof=proof,status='approved_frozen_shared_actor_scope' if structural else 'rejected_changed_dependency',structural_equivalence=structural)
     if name in MULTI:
      print(json.dumps({'target':label,'execute':name}),flush=True)
      actual=execute_multi(modules,fn,target,name);out=ROOT/f'validation/campaign/shared_actor_{label}_{name}.json';write(out,actual)
      src,srcpath=source_multis[name];assert len(src['actual_make_inputs'])==len(actual['actual_make_inputs'])
      pairs=[]
      for x,y in zip(src['actual_make_inputs'],actual['actual_make_inputs']):
       xs=deepcopy(x['scenario']);ys=deepcopy(y['scenario']);xs.pop('metadata',None);ys.pop('metadata',None);xs['seed']=x['seed'];ys['seed']=y['seed']
       assert xs==ys and x['seed']==y['seed']
       for key in ('reachable_definitions','rule_fingerprint','provider_fingerprint','initial_world_sha256','initial_rng_sha256'):assert x[key]==y[key]
       pairs.append({'source_fixture_sha256':x['fixture_sha256'],'target_fixture_sha256':y['fixture_sha256'],'effective_scenario_sha256':identity(xs),'every_reachable_definition_rules_providers_initial_world_rng_equal':True,'seed':x['seed']})
      row['all_fixture_source_target_comparison']=pairs;row['new_source_execution_artifact']={'path':str(srcpath.relative_to(ROOT)).replace('\\','/'),'sha256':sha(srcpath)}
      row.update(target_case_executed=True,multi_actual_artifact={'path':str(out.relative_to(ROOT)).replace('\\','/'),'sha256':sha(out)},status='target_original_assertions_executed' if structural else 'executed_but_sharing_rejected')
    rows.append(row)
  assert len(rows)==86 and sum(r['target_case_executed'] for r in rows)==5
  assert hashes=={str(p):sha(p) for p in paths} and implementation_digest()==CORE
  report={'schema':'ark-sim/shared-mechanism-review/v2','passed':True,'implementation_sha256':CORE,'source_content_sha256':sha(SOURCE),'target_content_sha256':sha(target),'status':'bounded_frozen_scope_review','reviewer':'campaign_catalog','helper_and_input_locks':hashes,'case_reviews':rows,'metadata_nonconsumption_evidence':{'runtime_access_source_rows':consumers,'helper_metadata_source_rows':helper_metadata,'reviewed_dataflow':'Only scenario rules/map/resources/parameters/objectives/initial/waves are used in actor runtime calculations; scenario.metadata changes identity only in this frozen core. Actor definition metadata is equal, compiler program.metadata/catalog is separately equal. Explicit make seed replaces scenario seed. Rules/providers are reachable-definition and descriptor fingerprint locked.','future_policy':'Any core/helper/provider/rule/fixture hash change invalidates this scope; future nonconsumption not presumed'},'static_cases_policy':'Four original source assertions executed but are not simulation witnesses','multi_first_capture_rejection_repaired':'Five proposal cases lacked all-fixture proof; target original assertions now genuinely executed for every make and CP/replay recorded; source old0fb evidence identity untouched','no_target_execution_claim_for_structural_only':True,'formal_approval':False,'model_receipt':False}
  write(ROOT/f'validation/campaign/shared_actor_scope_{label}_review.json',report)
  print(json.dumps({'target':label,'counts':dict(Counter(r['status'] for r in rows))}),flush=True)
if __name__=='__main__':run()
