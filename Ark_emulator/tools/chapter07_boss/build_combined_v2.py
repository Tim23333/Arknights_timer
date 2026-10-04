"""Source explicit considerUnhurtable handling, retaining v1 identity."""
from pathlib import Path
import json
from tools.chapter07_boss.build_mechanism_v1 import ROOT,OUT,UID,sha
def main():
 old=OUT/'combined.mechanism.v1.json';p=json.loads(old.read_bytes());rid='rule/'+UID+'/invul'
 for rule in p['rules']:
  if rule['id']==rid:rule['implementation']={'type':'provider','provider':'reference.ch7.patrt_invulnerability'}
 p['manifest']['id']='package/ch7/patrt/combined_source_mechanisms_v2';meta=p['manifest']['metadata'];meta['builder_sha256']=sha(Path(__file__));meta['policy_provider_sha256']=sha(ROOT/'tools/chapter07_boss/policies_v2.py');meta['source_locks'][str(old.relative_to(ROOT))]=sha(old);meta['reference_policies']['invulnerability']='Defaultdamage considersunhurtable and isrejected while15s Buff; explicitsourceparameter consider_unhurtable:false passes thishook unchanged, allothermodifiers/pipeline stillapply. Numeric0 notaccepted. NativeHP0 selection gates remain; notminesgeneral immunity inference.';path=OUT/'combined.mechanism.v2.json';path.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(path),'stage_export_allowed':False}))
if __name__=='__main__':main()
