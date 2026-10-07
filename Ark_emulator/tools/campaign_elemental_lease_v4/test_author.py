import sys,os,json,traceback,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_elemental_lease_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_elemental_lease_v4.fixture import package
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_elemental_lease_v4';RESULT=[];FACT={};ART=[];REG=BUILTIN_PROVIDERS

def create(p=None):return Engine.create(Compiler().compile(p or package()),providers=REG,seed=42371797)
def cpp():
 p=package();a=create(p);a.advance(130);b=create(p)
 for t in [0,10,50,92,94,130]:
  b.advance(t-b.session.time);f=LOG/(str(t)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});before=b.checkpoint();b=Engine.restore(b.program,load_bound(f,h),providers=REG);assert b.checkpoint()==before
 h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();FACT['CPP_head']=True;FACT['endstate']=thaw(a.ctx.get('target',('runtime','elemental')))

def negatives():
 s=create();s.advance(10);cp=s.checkpoint();facts=[]
 for field in ['remaining','due','generation','task','seq','provenance']:
  bad=deepcopy(cp);actor=next(e for e in bad['kernel']['world']['entities'] if e['id']==2);state=actor['components']['runtime']['elemental'];lease=state['break']
  if field=='remaining':state['remaining']['EMBER']=1
  elif field=='provenance':lease['provenance']['request']['raw_amount']=1
  else:lease[field]+=1
  try:Engine.restore(s.program,bad,providers=REG)
  except Exception as e:facts.append({'field':field,'rejected':True,'message':str(e)})
  else:facts.append({'field':field,'rejected':False})
 FACT['six_rejections']=facts;assert all(x['rejected'] for x in facts)

def direct():
 s=create();s.advance(10);state=s.ctx.get('target',('runtime','elemental'));before=s.checkpoint();s.ctx.elemental.expire(s.session,{'target':2,'generation':state['generation']});assert before==s.checkpoint();FACT['direct_expiry_noop_full_equal']=True

def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and 'validation' not in p.parts}
BEFORE=guard()
for name,fn in [('legitimate_arbitrary_profiles_all_CPP_head_pure_restore',cpp),('six_parent_counter_fields_now_rejected',negatives),('direct_expiry_no_grant_noop_all_fields',direct)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'comparison_exclusions':[]};(OUT/'author.initial.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'actual_exit':r['actual_exit'],'results':RESULT}));raise SystemExit(r['actual_exit'])
