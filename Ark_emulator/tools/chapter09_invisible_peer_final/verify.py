"""Strict structural legacy comparison and retained small peer receipt."""
import copy,hashlib,json,os,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
LOG=Path('E:/ArkSimLogs/runs/chapter09_invisible_independent_final')
OUT=ROOT/'validation/campaign/chapter09_invisible_independent_final'
CAND=ROOT.parent/'unpack_work/campaign_invisible_v1_candidate'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
 try:return json.loads(path.read_text(encoding='utf8'))
 except UnicodeDecodeError:return json.loads(path.read_text())
def identities(a,b):
 allowed={'$.implementation':(a['implementation'],b['implementation'])}
 def trace(x,y,path,ra,rb):
  assert {'calculation_id','rule_id','inputs','context','value','runtime_fingerprint'}<=set(x)
  assert x['runtime_fingerprint']==ra and y['runtime_fingerprint']==rb
  allowed[path+'.runtime_fingerprint']=(ra,rb)
  for i,(sx,sy) in enumerate(zip(x.get('stages',[]),y.get('stages',[]))):
   if isinstance(sx.get('trace'),dict) and 'calculation_id' in sx['trace']:trace(sx['trace'],sy['trace'],path+'.stages['+str(i)+'].trace',ra,rb)
 for name,x in a['cases'].items():
  y=b['cases'][name];path='$.cases.'+name
  for k in ('program_fingerprint','runtime_fingerprint'):allowed[path+'.'+k]=(x[k],y[k])
  ra=x['metadata']['rule_runtime_fingerprint'];rb=y['metadata']['rule_runtime_fingerprint'];allowed[path+'.metadata.rule_runtime_fingerprint']=(ra,rb)
  px=x['metadata']['providers'].get('model.targeting.eligibility');py=y['metadata']['providers'].get('model.targeting.eligibility')
  if px is not None:allowed[path+'.metadata.providers.model.targeting.eligibility.implementation']=(px['implementation'],py['implementation'])
  for i,(cx,cy) in enumerate(zip(x['captures'],y['captures'])):
   cp=path+'.captures['+str(i)+']'
   for k in ('program_fingerprint','runtime_fingerprint'):allowed[cp+'.checkpoint.'+k]=(x[k],y[k])
   for events_path in (('events',),('checkpoint','kernel','events','records')):
    ex,ey=cx,cy
    for part in events_path:ex,ey=ex[part],ey[part]
    for j,(vx,vy) in enumerate(zip(ex,ey)):
     if vx['type']=='calculation':
      trace(vx['payload']['trace'],vy['payload']['trace'],cp+'.'+'.'.join(events_path)+'['+str(j)+'].payload.trace',ra,rb)
 return allowed
def pair(a,b,allowed,path='$'):
 assert type(a) is type(b),path+' type'
 if isinstance(a,dict):
  assert list(a)==list(b),path+' keys/order'
  for k in a:pair(a[k],b[k],allowed,path+'.'+k)
 elif isinstance(a,list):
  assert len(a)==len(b),path+' length'
  for i,(x,y) in enumerate(zip(a,b)):pair(x,y,allowed,path+'['+str(i)+']')
 elif a!=b:
  assert path in allowed and (a,b)==allowed[path],path+' value'
  assert isinstance(a,str) and re.fullmatch('[a-f0-9]{64}',a) and re.fullmatch('[a-f0-9]{64}',b),path+' identity'
def main():
 helper_start={p.name:sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
 LOG.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 if '--reuse' not in sys.argv:
  for runtime,file,mode in ((ROOT,'parent.capture.json','legacy'),(CAND,'candidate.capture.json','legacy'),(CAND,'independent.json','independent')):
   subprocess.run([sys.executable,str(Path(__file__).with_name('worker.py')),str(runtime),str(LOG/file),mode],cwd=ROOT,env={**os.environ,'PYTHONHASHSEED':'0'},check=True)
 a,b=load(LOG/'parent.capture.json'),load(LOG/'candidate.capture.json');assert a['implementation']=='5c729384f50e078bd3d3ac9d211360b17bc486588770914efe92ef5b4e983826';assert b['implementation']=='4321a27f07d44574a5ce5f6ea740dced097e02868bd28a4580f529853c546563'
 allowed=identities(a,b);pair(a,b,allowed);negative=[]
 def reject(name,mutate):
  x=copy.deepcopy(b);mutate(x)
  try:pair(a,x,allowed)
  except AssertionError:negative.append(name)
  else:raise AssertionError('negative accepted '+name)
 key='enemy_1167_dubow';event=next(i for i,e in enumerate(b['cases'][key]['captures'][0]['events']) if e['type']=='calculation')
 def tr(x):return x['cases'][key]['captures'][0]['events'][event]['payload']['trace']
 reject('context scalar mutation',lambda x:tr(x)['context'].__setitem__('time',-782))
 reject('calculated value mutation',lambda x:tr(x).__setitem__('value',{'mutated':True}))
 reject('context deceptive runtime_fingerprint',lambda x:tr(x)['context'].__setitem__('runtime_fingerprint','a'*64))
 reject('unknown identity value at genuine path',lambda x:x['cases'][key].__setitem__('runtime_fingerprint','a'*64))
 reject('key insertion order',lambda x:tr(x).__setitem__('context',dict(reversed(list(tr(x)['context'].items())))))
 reject('checkpoint cached state mutation',lambda x:x['cases'][key]['captures'][0]['checkpoint']['kernel'].__setitem__('cached_calc',{'runtime_fingerprint':'a'*64}))
 def cached_sample_mutation(x):
  def visit(v):
   if isinstance(v,dict):
    if 'context' in v and isinstance(v['context'],dict) and 'attribute_sample_time' in v['context']:
     v['context']['attribute_sample_time']+=1;return True
    return any(visit(child) for child in v.values())
   if isinstance(v,list):return any(visit(child) for child in v)
   return False
  assert visit(x),'fixture must contain actual attribute sample calculation context'
 reject('actual cached attribute sample context',cached_sample_mutation)
 subprocess.run([sys.executable,str(Path(__file__).with_name('test_identity_boundaries.py'))],cwd=ROOT,check=True,capture_output=True,text=True)
 helper_end={p.name:sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))};assert helper_start==helper_end,'peer helpers changed during gate execution'
 receipt={'parent':a['implementation'],'candidate':b['implementation'],'fresh_numeric_fixture':{'max_hp':7731,'def':181,'mres':63,'seed':72613,'times':[0,17,83]},'legacy_cases':list(a['cases']),'contexts_values_and_keyorder_equal':True,'cached_calc_excluded':False,'identity_exemptions':'Only exact structural source identity paths; values must match known source identity pairs','identity_paths_count':len(allowed),'negative_checks':negative,'independent':load(LOG/'independent.json'),'raw_sha':{p.name:sha(p) for p in LOG.iterdir() if p.is_file()},'worker_sha':sha(Path(__file__).with_name('worker.py')),'passed':True}
 receipt['preexisting_cache_scope']={name:load(OUT/('cache.'+name+'.v1.json')) for name in ('parent','candidate')}
 receipt['scope']='Selection change accepted independently; separate preexisting legal attribute-query CP cache cause mismatch remains failing and is not waived'
 receipt['helpers_sha_before']=helper_start;receipt['helpers_sha_after']=helper_end;receipt['helper_execution_guard_stable']=True
 receipt['setup_cleanup_history']='Exploratory runs were superseded by this fresh fixed-helper gate. Fixed PYTHONHASHSEED=0 for parent/candidate insertion-order pairing; renamed large parent/candidate snapshots to *.capture.json so policy cleanup recognizes them; added independent cache-scope mode, actual cached sample context mutation and same-shape adversarial identity-key negatives before final freeze. Expectations and candidate/main sources were unchanged.'
 receipt['adversarial_same_shape_FP']=load(OUT/'identity.adversarial.v1.json')
 cleanup=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),'--apply','--run-dir',str(LOG),'--minimum-age-minutes','0'],capture_output=True,text=True,check=True);receipt['cleanup']=json.loads(cleanup.stdout);(OUT/'receipt.v1.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf8');print(json.dumps({'passed':True,'independent_checks':len(receipt['independent']['checks']),'negative_checks':len(negative),'legacy_cases':3,'cleanup':receipt['cleanup']}))
if __name__=='__main__':main()
