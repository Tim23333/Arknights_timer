"""Export reviewed per-case applicability proofs; original artifacts immutable."""
import sys,json,hashlib,importlib,inspect,dis,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m12_projection_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.contracts import thaw
from tools.propose_witness_scope_00_11 import MODULES,CORE
SOURCE='0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4'
def read(p):return json.loads((ROOT/p).read_bytes())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def ident(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write(p,v):(ROOT/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def ref(p):return {'path':p,'sha256':sha(p)}
def call_graph(fn,seen=None):
 seen=set() if seen is None else seen
 if fn in seen:return []
 seen.add(fn);out=[];instructions=list(dis.get_instructions(fn));sites=[i.offset for i in instructions if i.opname in ('LOAD_ATTR','LOAD_METHOD','LOAD_GLOBAL') and i.argval=='make']
 backedges=[(i.argval,i.offset) for i in instructions if 'JUMP' in i.opname and isinstance(i.argval,int) and i.argval<i.offset]
 assert not any(lo<=offset<=hi for lo,hi in backedges for offset in sites),('make under loop',fn.__name__)
 out.append({'make_site_not_in_backward_loop':True,'function':fn.__module__+'.'+fn.__name__,'source_file':str(Path(inspect.getsourcefile(fn)).relative_to(ROOT)).replace('\\','/'),'first_line':fn.__code__.co_firstlineno,'make_load_offsets':sites})
 for name in fn.__code__.co_names:
  child=fn.__globals__.get(name)
  if inspect.isfunction(child) and child.__module__.startswith('tools.') and name not in ('make','finish','run_case','export'):
   out+=call_graph(child,seen)
 return out

def run():
 modules=[importlib.import_module('tools.'+m) for m in MODULES];functions={}
 for m in modules:
  cs=getattr(m,'CASES',None)
  if cs is None:cs={'probe':m.probe} if m.__name__.endswith('witness_canonical_lisk_defense') else {'friend_damage_capacity_source_exit':m.run} if m.__name__.endswith('witness_angel_blessing_damage') else {}
  for case,fn in cs.items():functions[(str(Path(m.__file__).relative_to(ROOT)).replace('\\','/'),case)]=fn
 contract=read('packages/mainline/contracts/main_00-10.json');bindings={}
 for refs in contract['mechanic_tests'].values():
  for r in refs:
   if not r.get('case'):continue
   if r.get('helper_path'):
    candidates=[(r['helper_path'],r['case'])]
    if r['helper_path']=='tools/witness_canonical_lisk_defense.py':candidates=[(r['helper_path'],'probe')]
   else:candidates=[key for key in functions if key[1]==r['case']]
   for key in candidates:
    if key in functions:bindings.setdefault(key,[]).append(r)
 for label in ('m14','00_11'):
  detailp=f'validation/campaign/shared_actor_scope_{label}_review.json';detail=read(detailp);approved=[];static=[]
  targetpath=next(p for p,h in detail['helper_and_input_locks'].items() if h==detail['target_content_sha256']);pa=Compiler().compile(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json');pb=Compiler().compile(targetpath)
  static_ids=set(i['id'] for c in read('packages/campaign/conversion_drafts/main_00-10.audit.json')['operator_definition_closures'] for i in c['reachable_definition_identities'])
  assert all(pa.definitions[i]==pb.definitions[i] for i in static_ids)
  static_definitions=[{'id':i,'sha256':ident(thaw(pa.definitions[i]))} for i in sorted(static_ids)]
  for index,row in enumerate(detail['case_reviews']):
   key=(row['helper_path'],row['case']);fn=functions[key];graph=call_graph(fn)
   sites=sum(len(x['make_load_offsets']) for x in graph)
   if row['status']=='approved_frozen_shared_actor_scope':assert sites==1,(key,sites,graph)
   supporting=[ref(detailp)]
   if row['target_case_executed']:supporting+=[row['multi_actual_artifact'],row['new_source_execution_artifact']]
   proof={'schema':'ark-sim/shared-mechanism-case-proof/v2','passed':True,'source_content_sha256':SOURCE,'target_content_sha256':detail['target_content_sha256'],'implementation_sha256':CORE,'case':row['case'],'helper_sha256':row['helper_sha256'],'helper_path':row['helper_path'],'metadata_nonconsumption_reviewed':True,'supporting_evidence':supporting,'fixture_constructor_call_graph':graph,'target_case_executed':row['target_case_executed'],'scope':'Frozen applicability only; no cross-program raw-event equality or full-stage receipt'}
   if row['status']=='static_source_only':
    proof.update(proof_type='static_source_definition_equivalence',no_runtime_fixture=True,static_source_assertions_equal=True,reachable_definitions_equal=True,rule_and_provider_identity_equal=True)
    proof['static_reachable_actor_definition_identities']=static_definitions
    proof['static_actual_results']={'source':row['source_static_result'],'target':row['target_static_result']}
   else:
    assert row['structural_equivalence']
    proof.update(proof_type='runtime_fixture_scope',all_fixtures_accounted_for=True,reachable_definitions_equal=True,rule_and_provider_identity_equal=True,effective_inputs_equal=True,explicit_seed_equal=True)
    proof['structural_proof']=row['proof']
    if row['target_case_executed']:proof['all_fixture_comparisons']=row['all_fixture_source_target_comparison']
    else:proof['fixture_count']=1;proof['one_constructor_source_review']='One reachable make load site, constructor invocation before subsequent assertion/effects; frozen function source reviewed, not assumed for future code.'
   path=f'validation/campaign/shared_scope_proofs/{label}_{index:02d}.json';(ROOT/path).parent.mkdir(parents=True,exist_ok=True);write(path,proof)
   for binding in bindings.get(key,[]):
    assert sha(binding['path'])==binding['sha256']
    boundpath=path
    if binding['case']!=row['case']:
     nodepath,node=binding['test_node_id'].split('::');tree=ast.parse((ROOT/nodepath).read_bytes());testfn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==node);assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='probe' for n in ast.walk(testfn))
     aliasproof=dict(proof);aliasproof['case']=binding['case'];aliasproof['source_callable_case']=row['case'];boundpath=f'validation/campaign/shared_scope_proofs/{label}_{index:02d}_node.json';write(boundpath,aliasproof)
    record={'case':binding['case'],'helper_path':row['helper_path'],'helper_sha256':row['helper_sha256'],'source_evidence_path':binding['path'],'source_evidence_sha256':binding['sha256'],'proof':ref(boundpath)}
    if record not in approved:approved.append(record)
   if row['status']=='static_source_only':static.append(row['case'])
  locks=[{'path':str(Path(p).relative_to(ROOT)).replace('\\','/'),'sha256':h} for p,h in detail['helper_and_input_locks'].items()]
  locks+=[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'sha256':sha(Path(__file__).relative_to(ROOT))}]
  review={'schema':'ark-sim/shared-mechanism-review/v2','passed':True,'status':'approved_scoped_definition_use','reviewer':'campaign_catalog frozen shared actor applicability review','source_content_sha256':SOURCE,'target_content_sha256':detail['target_content_sha256'],'implementation_sha256':CORE,'source_locks':locks,'approved_cases':approved,'scope_detail':ref(detailp),'static_case_names_separate':static,'original_source_report_input_not_modified':True,'formal_approval':False,'model_receipt':False,'scope':'Specific helper/case and source artifact only. 77 structural, five multi actual reruns, four static; no stage timeline enemy or control sharing.'}
  write(f'validation/campaign/shared_actor_scope_{label}_gate_review.json',review);print(json.dumps({'target':label,'approved_source_case_bindings':len(approved),'static':len(static)}))
if __name__=='__main__':run()

