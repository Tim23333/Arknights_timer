import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PAIR=ROOT/'validation/campaign/chapter08_foundation_pair_v1'
def compare(a,b):
 assert a['core']=='4bf1cc96ae41f2850b645c25d772ada1d472f7b0202127fff340a4fc2b0b04c3' and b['core']=='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae';allowed={'/core'}
 for i,(old,new) in enumerate(zip(a['cases'],b['cases'])):
  for case in (old,new):
   assert type(case['actual_runtime_fingerprint']) is str and len(case['actual_runtime_fingerprint'])==64
   assert all(case[k]['runtime_fingerprint']==case['actual_runtime_fingerprint'] for k in ('snapshot','checkpoint','replay'))
   assert all(case[k]['program_fingerprint']==case['actual_program_fingerprint'] for k in ('snapshot','checkpoint','replay'))
  allowed|={f'/cases/{i}/{k}/runtime_fingerprint' for k in ('snapshot','checkpoint','replay')}|{f'/cases/{i}/actual_runtime_fingerprint'}
 differences=[]
 def walk(x,y,path=''):
  assert type(x) is type(y),(path,'typedshape')
  if isinstance(x,dict):
   assert list(x)==list(y),(path,'dictionary_order')
   for k in x:walk(x[k],y[k],path+'/'+k)
  elif isinstance(x,list):
   assert len(x)==len(y),(path,'arraylength')
   for i,(v,w) in enumerate(zip(x,y)):walk(v,w,path+'/'+str(i))
  elif x!=y:
   assert path in allowed,(path,'valuechanged');differences.append(path)
 walk(a,b);assert set(differences)==allowed;return differences
def main():
 a=json.loads((PAIR/'parent/capture.json').read_bytes());b=json.loads((PAIR/'candidate/capture.json').read_bytes());diff=compare(a,b);out=PAIR/'verification.json';assert not out.exists();out.write_text(json.dumps({'passed':True,'actual_exit':0,'paired_cases':3,'all_values_types_contexts_cache_entries_dictionary_order_checked':True,'only_differences':diff,'not_ignored':['value','context','calculation.trace','cache_entries','cached_calculation','dictionary_order','random','scheduler','world'],'pins':{str(PAIR/x/'capture.json'):hashlib.sha256((PAIR/x/'capture.json').read_bytes()).hexdigest() for x in ('parent','candidate')}},indent=2),encoding='utf8');print(hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
