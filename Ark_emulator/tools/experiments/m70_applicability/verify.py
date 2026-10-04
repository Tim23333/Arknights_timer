import sys,json,hashlib,difflib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m70_buff_applicability_v2_candidate';BASE=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/m70_applicability_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();files=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'}];start={str(p.relative_to(RUNTIME)):sha(p) for p in files};cases=[];inputs=[];original=Compiler.compile
 def capture(self,p,*a,**k):
  path=OUT/f'final_input_{len(inputs):03d}.json';write(path,p);inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=capture
 try:code=pytest.main([str(Path(__file__).with_name('test_applicability.py')),str(Path(__file__).with_name('test_frost_source.py')),'-q'],plugins=[Results()])
 finally:Compiler.compile=original
 assert code==0
 a=json.loads((OUT/'noopt.parent.json').read_bytes());b=json.loads((OUT/'noopt.candidate.final.json').read_bytes());differences=[]
 def compare(x,y,path):
  assert type(x)==type(y),path
  if isinstance(x,dict):
   assert x.keys()==y.keys(),path
   for k in x:compare(x[k],y[k],path+'.'+k)
  elif isinstance(x,list):
   assert len(x)==len(y),path
   for i,(v,w) in enumerate(zip(x,y)):compare(v,w,f'{path}[{i}]')
  elif x!=y:differences.append({'path':path,'parent':x,'candidate':y})
 for key in ['snapshot','checkpoint']:compare(a[key],b[key],key)
 for row in differences:
  p=row['path'];assert p in ['snapshot.program_fingerprint','snapshot.runtime_fingerprint','checkpoint.program_fingerprint','checkpoint.runtime_fingerprint'] or re.fullmatch(r'(snapshot\.events|checkpoint\.kernel\.events\.records)\[\d+\]\.payload\.trace(\.stages\[\d+\]\.trace)*\.runtime_fingerprint',p),p
 assert a['input_sha256']==b['input_sha256'] and b['core']==before
 changes={};patch=[];archive=OUT/'source_files';archive.mkdir(exist_ok=True)
 for p in files:
  rel=p.relative_to(RUNTIME);old=BASE/rel
  if not old.exists() or old.read_bytes()!=p.read_bytes():
   name=str(rel).replace('\\','/');changes[name]=sha(p);dest=archive/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());patch+=list(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],p.read_text(encoding='utf8').splitlines(True),fromfile='a/'+name if old.exists() else '/dev/null',tofile='b/'+name))
 (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8');write(OUT/'changed_files.json',changes)
 assert start=={str(p.relative_to(RUNTIME)):sha(p) for p in files} and before==implementation_digest()
 locks={str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')};names=['tools/build_frostnova_immunity_model.py','packages/campaign/chapter04_boss/m70/immunity.reference_model.json','validation/campaign/m70_applicability_v2/compat_final.log','validation/campaign/m70_applicability_v2/noopt.input.json','validation/campaign/m70_applicability_v2/noopt.parent.json','validation/campaign/m70_applicability_v2/noopt.candidate.final.json']
 locks.update({n:sha(ROOT/n) for n in names})
 report={'schema':'ark-sim/buff-applicability-review/v1','status':'passed_declared_profile','core_before':before,'core_after':before,'actual_module':sys.modules['ark_sim'].__file__,'source_before':start,'source_after':start,'source_locks':locks,'changed_files':changes,'cases':cases,'actual_inputs':inputs,'compatibility':{'cases':88,'outcome':'passed','log':'validation/campaign/m70_applicability_v2/compat_final.log'},'noopt':{'parent_core':a['core'],'candidate_core':b['core'],'event_count':len(a['snapshot']['events']),'all_world_rng_scheduler_events_values_equal_except_exact_identity_paths':True,'excluded_identity_differences':differences},'public_ordered_checkpoint_and_command_replay_cases':[r['case'] for r in cases if 'checkpoint' in r['case'] or 'public_disk_replay' in r['case']],'model_scope':['Pure applicability Bool active/control bindings; cached contribution state persists in World','Effective flags/immunities only from active Buffs; intrinsic state and combo immunity independent','Control reactivation interrupts existing cast when explicitly requested','Inactive duration/periodic clock continues; effects/hooks/reactions/modifiers/aura/toggle contributions disabled; removal callback always runs','Old active movement-damage tail settles before deactivation; inactive travel discarded before activation','Exact Frost intrinsic DB flags and raw sleep-immunity Buff plus Chen source control operands, synthetic phase-removal driver'],'remaining_scope':['True M61/M74 delayed rebirth and M70 immunity combined integration not executed in this M68-parent candidate','Whole FrostNova skills/blackice not in this immunity module','Native status duration resistance, dispatch/comparator body and client feedback remain separately pending'],'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'candidate_final.json',report);print(json.dumps({'core':before,'report_sha256':sha(OUT/'candidate_final.json'),'cases':len(cases),'compat':88,'changed':len(changes),'noopt_events':len(a['snapshot']['events'])}))
if __name__=='__main__':main()
