import sys,json,hashlib,inspect
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from tools.chapter07_stage_join.runner_718_providers_v1 import providers

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parent=ROOT/'packages/campaign/chapter07_stage_models/level_main_07-16.native_draft.v2.json';overlay=parent.with_name('level_main_07-16.native_draft.v2.life99999.strict_v1.json');commands=ROOT/'scenarios/campaign/chapter07/level_main_07-16/public_plan_v1/commands.json';p=json.loads(overlay.read_bytes());s=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']};cmds=json.loads(commands.read_bytes());aliases={};slots=0;peak=0;costs=[]
 for c in cmds:
  if c['action']=='deploy':
   u=c['entity'];assert u in s['roster'] or u in s['cards'];aliases[c['alias']]=u;d=defs[u]['components']['deployable'];mask=2 if d.get('terrain')=='high' else 1;assert s['map']['tiles'][c['row']*s['map']['cols']+c['col']]['buildableType']&mask;slots+=d.get('capacity',1);costs.append({'at':c['at'],'unit':u,'cost':d.get('base_cost',defs[u]['components']['attributes']['base'].get('deploy_cost')),'capacity':d.get('capacity',1)})
  elif c['action']=='withdraw':slots-=defs[aliases[c['source']]]['components']['deployable'].get('capacity',1)
  elif c['action']=='skill':
   u=aliases[c['source']];assert c['ability'] in defs[u]['components']['abilities'] and not defs[c['ability']].get('activation',{}).get('parameters',{}).get('auto_only',False)
   if 'payload' in c:
    q=c['payload']['position'];spawn=next(x for x in defs[c['ability']]['activation']['on_start'] if x['op']=='spawn');token=defs[spawn['definition']];terrain=token['components']['deployable']['terrain'];mask=1 if terrain=='ground' else 2 if terrain=='high' else 3;assert s['map']['tiles'][q['row']*s['map']['cols']+q['col']]['buildableType']&mask;assert spawn['parameters']['position_from_payload'] is True
   if c['ability']=='ability/kalts_summon':slots+=1
  peak=max(peak,slots)
 assert peak<=9;Compiler(providers=providers()).compile(p);files={}
 for val in providers().values():
  fn=val['callable'] if isinstance(val,dict) else val
  if callable(fn):q=Path(inspect.getsourcefile(fn));files[str(q)]=sha(q)
 for n in ['tools/chapter07_stage_join/runner_718_providers_v1.py','tools/run_campaign_disk_runthrough_v17.py','tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py','tools/control_driver/public_ack_v2.py','tools/chapter07_stage_join/build_718_life_v1.py','tools/chapter07_stage_join/build_718_commands_v1.py','tools/chapter07_stage_join/verify_718_input_v2.py']:
  q=ROOT/n;files[str(q)]=sha(q)
 r={'actual_compile':True,'core':'3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000','parent':str(parent),'parent_sha':sha(parent),'overlay':str(overlay),'overlay_sha':sha(overlay),'commands':str(commands),'commands_sha':sha(commands),'planned_count':30,'planned_fixed12':12,'planned_mine_requests':2,'planned_peak_with_Mon3tr_no_death_assumption':peak,'static_actual_costs':costs,'provider_helper_actualpins':files,'accepted_counts':None,'scope':'Allunit/ownedabilityIDs and staticterrain including tokenpositions checked. NativeDP/HP/9slots unchanged; DP/death/control/SP/cost/stock15/max1mine/cooldown7 acceptances onlyactualruntime. Mine1nativeBossroute1,7/mine2 at3,7 are explicit requests, no fabricated hits or terminal outcome.'};out=ROOT/'validation/campaign/chapter07_718_public_input_v1/input_pins_v2.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(out),'slots':peak,'providers_pins':len(files)}))
if __name__=='__main__':main()
