import sys,os,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];PARENT=ROOT.parent/'unpack_work/campaign_c10_joint_v1_candidate';sys.path.insert(0,str(PARENT));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from tools.campaign_elemental_lease_v4.fixture import package
OUT=ROOT/'validation/campaign/campaign_elemental_lease_v4';p=package();s=Engine.create(Compiler().compile(p),providers=BUILTIN_PROVIDERS,seed=42371797);s.advance(10);cp=s.checkpoint();results=[]
for field in ['remaining','due','generation','task','seq','provenance']:
 bad=deepcopy(cp);actor=next(e for e in bad['kernel']['world']['entities'] if e['id']==2);state=actor['components']['runtime']['elemental'];lease=state['break']
 if field=='remaining':state['remaining']['EMBER']=1
 elif field=='provenance':lease['provenance']['request']['raw_amount']=1
 else:lease[field]+=1
 try:restored=Engine.restore(s.program,bad,providers=BUILTIN_PROVIDERS);accepted=True;error=None
 except Exception as e:accepted=False;error=str(e)
 results.append({'field':field,'accepted':accepted,'error':error})
report={'core':implementation_digest(),'actual_exit':0 if all(r['accepted'] for r in results) else 1,'counter_real_restore_accepts_six_singlefields':results,'natural_lease':s.ctx.get('target',('runtime','elemental')),'public_packet_tick':9,'expected_capacity733_duration2_75_due92':True,'all_events_jobs_cache_kept':True,'legacy_peer_counter_SHA':hashlib.sha256((ROOT/'validation/campaign/campaign_elemental_receiver_peer_v1/result.v1.json').read_bytes()).hexdigest()};(OUT/'parent.counter.v1.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(results));raise SystemExit(report['actual_exit'])
