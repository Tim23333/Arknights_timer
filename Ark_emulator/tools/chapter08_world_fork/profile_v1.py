import sys,json,time,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_world_fork_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim.kernel import World
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/chapter08_world_fork_profile_v1';OUT.mkdir(exist_ok=False)
w=World();w.create('system/peer',{'projectiles':{'next_id':4001,'instances':{str(i):{'id':str(i),'source':2,'target':3,'position':{'row':i%7,'col':i%15},'metadata':{'values':[0,True,None,3.125]*8},'events':[{'value':j} for j in range(3)]} for i in range(4000)}}},alias='peer')
timings={};last={}
for kind in ('public_snapshot_restore','private_fork'):
 samples=[]
 for _ in range(7):
  started=time.perf_counter()
  if kind=='public_snapshot_restore':f=World();f.restore(w.snapshot())
  else:f=w._fork_validated()
  samples.append(time.perf_counter()-started)
 last[kind]=f.snapshot();timings[kind]={'samples_seconds':samples,'median_seconds':statistics.median(samples)}
assert last['public_snapshot_restore']==last['private_fork'];r={'passed':True,'core':implementation_digest(),'records':4000,'timings':timings,'single_paired_median_ratio':timings['public_snapshot_restore']['median_seconds']/timings['private_fork']['median_seconds'],'all_snapshot_values_equal':True,'scope':'ActualinternalWorld setup alreadyvalidated by publiccreate. Seven paired repeatedcostsamples only; sourcehistory workloadproxy, not wholecampaign throughput guarantee.'};path=OUT/'verification.json';path.write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({'sha':hashlib.sha256(path.read_bytes()).hexdigest(),'ratio':r['single_paired_median_ratio']}))
