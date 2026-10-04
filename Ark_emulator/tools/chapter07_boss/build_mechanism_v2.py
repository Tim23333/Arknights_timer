"""Bounded single-emitter probe while shared native Aura contract is missing."""
import json
from tools.chapter07_boss.build_mechanism_v1 import build,OUT,UID,MARKER,sha
def main():
 p=build();parent='buff/'+UID+'/marker_parent';child='buff/'+UID+'/strength'
 p['buffs']=[b for b in p['buffs'] if b['id'] not in [parent,MARKER]]
 for b in p['buffs']:
  if b['id']==child:b['stacking']={'mode':'independent','max_stacks':1}
 c=p['entities'][0]['components'];c['buffs']['initial'].remove(parent);c['rebirth']['retain_buffs'].remove(parent)
 for hook in ['on_begin','on_finish']:c['rebirth'][hook]=[e for e in c['rebirth'][hook] if e.get('buff')!=parent]
 meta=p['manifest']['metadata'];meta['status']='single_emitter_mechanism_probe_only_not_complete_enemy';meta['unconsumed_required_mechanisms']+=['Native sharedStrength markerproducer/aura child nonstacking requiresgenericlease identity contract; omitted fromthissingleemitter probe','MultiplePatriot stats nonstacking cannotbeverifiedusingindependent prototype children'];meta['single_emitter_probe_adapter']='Own attributes child independent onlyto exercise exactlyone emitter. Notnative multiemitter stacking or externalmarker production; existingsharedmarker definition untouched.';meta['builder_sha256']=sha(__import__('pathlib').Path(__file__));p['manifest']['id']='package/ch7/patrt/single_emitter_mechanism_probe_v2'
 path=OUT/'mechanism.v2.json';path.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(path),'stage_export_allowed':False}))
if __name__=='__main__':main()
