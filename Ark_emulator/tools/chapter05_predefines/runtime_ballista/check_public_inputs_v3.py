"""Independent read-only checks for frozen C5 native overlays/public input."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.build_campaign_runthrough_input import apply
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 receipt=json.loads((ROOT/'validation/campaign/chapter05_public_v3/prepared_commands.json').read_bytes());results=[]
 for row in receipt['cases']:
  parent=Path(row['parent']);overlay=Path(row['overlay']);cmd=Path(row['commands'])
  assert (sha(parent),sha(overlay),sha(cmd))==(row['parent_sha'],row['overlay_sha'],row['commands_sha'])
  native=json.loads(parent.read_bytes());package=json.loads(overlay.read_bytes());commands=json.loads(cmd.read_bytes());scene=package['scenarioDraft'];defs={d['id']:d for d in package['definitions']}
  assert package==apply(native,sha(parent));assert native['scenarioDraft']['resources']['life']=={'initial':3,'capacity':3}
  assert scene['resources']['dp']['initial']==row['native_DP'] and scene['parameters']['deploy_capacity']==row['native_slots'];assert len(scene['roster'])==12
  spawns=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn']
  assert sum(a.get('count',1) for a in spawns)==row['births'];assert len({a['spawn']['definition'] for a in spawns})==row['variants']
  deployed=[c for c in commands if c['action']=='deploy'];assert len(deployed)==12 and {c['entity'] for c in deployed}==set(scene['roster'])
  aliases={};occupied={};peak=0
  for c in commands:
   if c['action']=='deploy':
    d=defs[c['entity']];cell=(c['row'],c['col']);tile=scene['map']['tiles'][cell[0]*scene['map']['cols']+cell[1]];assert tile['buildableType']&(1 if d['components']['deployable']['terrain']=='ground' else 2)
    assert cell not in occupied.values();occupied[c['alias']]=cell;aliases[c['alias']]=c['entity'];peak=max(peak,len(occupied))
   elif c['action']=='withdraw':occupied.pop(c['source'],None)
   elif c['action']=='skill':
    a=defs[c['ability']];assert a['activation']['mode']=='manual';params={**a.get('parameters',{}),**a['activation'].get('parameters',{})};assert not params.get('auto_only',False)
  assert peak+1<=row['native_slots'] # reserve actual Mon3tr slot
  results.append({'stage':row['native_id'],'standard_overlay_exact':True,'full_native_births':row['births'],'variants':row['variants'],'native_DP':row['native_DP'],'native_slots':row['native_slots'],'public_first_deploys':len(deployed),'last_first_deploy':max(c['at'] for c in deployed),'nominal_operator_peak':peak,'auto_only_manual_commands':0,'command_sha':sha(cmd),'actual_admission_requires_runtime_receipt':True})
 out=ROOT/'validation/campaign/chapter05_public_v3/independent_input_check.json'
 if out.exists():raise FileExistsError(out)
 out.write_text(json.dumps({'results':results,'registry_modified':False,'whole_stage_passed':False},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'results':results}))
if __name__=='__main__':main()
