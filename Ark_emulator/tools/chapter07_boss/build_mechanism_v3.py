"""Correct ADDITION0 mapping to standard flat layer, preserving v2 failure."""
from pathlib import Path
import json
from tools.chapter07_boss.build_mechanism_v1 import OUT,sha
def main():
 p=json.loads((OUT/'mechanism.v2.json').read_bytes())
 for b in p['buffs']:
  for m in b.get('modifiers',[]):
   if m['layer']=='direct_add':m['layer']='flat'
 p['manifest']['id']='package/ch7/patrt/single_emitter_mechanism_probe_v3';p['manifest']['metadata']['builder_sha256']=sha(Path(__file__));p['manifest']['metadata']['additive_layer_policy']='NativeformulaADDITION0 binds standardflat; v2 unsupported direct_add receipt remainsfailed'
 path=OUT/'mechanism.v3.json';path.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(path),'stage_export_allowed':False}))
if __name__=='__main__':main()
