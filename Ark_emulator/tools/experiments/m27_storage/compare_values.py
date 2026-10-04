import json,hashlib,struct,argparse,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];ap=argparse.ArgumentParser();ap.add_argument('--suffix',default='capture');a=ap.parse_args();BASE=ROOT/'validation/campaign/m27_storage';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();left=BASE/('m26.'+a.suffix+'.json');right=BASE/('m27.'+a.suffix+'.json');l=json.loads(left.read_bytes());r=json.loads(right.read_bytes());started=time.time();assert l['package_sha256']==r['package_sha256'] and l['commands_sha256']==r['commands_sha256'] and l['program']==r['program'];assert l['runtime']!=r['runtime'];assert l['core_start']==l['core_end'] and r['core_start']==r['core_end']
le=Path(l['events_path']);re=Path(r['events_path']);assert sha(le)==l['events_sha256'] and sha(re)==r['events_sha256'];ls=Path(l['state_path']);rs=Path(r['state_path']);assert sha(ls)==l['state_sha256'] and sha(rs)==r['state_sha256'];counts={'scalar_values':0,'containers':0}
def exact(x,y,path='root'):
 assert type(x) is type(y),(path,type(x),type(y))
 if isinstance(x,dict):
  counts['containers']+=1;assert list(x)==list(y),path
  for key in x:exact(x[key],y[key],path+'/'+key)
 elif isinstance(x,list):
  counts['containers']+=1;assert len(x)==len(y),path
  for i,(aa,bb) in enumerate(zip(x,y)):exact(aa,bb,path+'/'+str(i))
 else:
  counts['scalar_values']+=1;assert struct.pack('>d',x)==struct.pack('>d',y) if type(x) is float else x==y,path
count=0
with le.open(encoding='utf8') as lf,re.open(encoding='utf8') as rf:
 for line in lf:
  other=rf.readline();assert other;exact(json.loads(line),json.loads(other),'event/'+str(count));count+=1
 assert rf.readline()==''
assert count==l['events']==r['events'];exact(json.loads(ls.read_bytes()),json.loads(rs.read_bytes()),'continuation');report={'schema':'ark-sim/m27-all-values-comparison/v1','passed':True,'inputs':{'package_sha256':l['package_sha256'],'commands_sha256':l['commands_sha256']},'source_report':{'path':str(left),'sha256':sha(left)},'target_report':{'path':str(right),'sha256':sha(right)},'runtime_source':l['runtime'],'runtime_target':r['runtime'],'program_equal':True,'runtime_equal':False,'event_count':count,'all_events_full_fields_typed_equal':True,'raw_event_bytes_equal':l['events_sha256']==r['events_sha256'],'all_world_random_scheduler_state_typed_equal':True,'raw_continuation_bytes_equal':l['state_sha256']==r['state_sha256'],'comparison_counts':counts,'excluded_payload_fields':[],'identity_scope':'runtime fingerprints retained separately in report; NONE removed from events or continuation data','actual_decoded_byte_identity_bound':a.suffix=='capture_v2','elapsed_seconds':time.time()-started,'formal_approval':False};out=BASE/('all_values_'+a.suffix+'.json');out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'events':count,'compared_values':counts,'actual_bytes_bound':a.suffix=='capture_v2','report_sha256':sha(out)}))
