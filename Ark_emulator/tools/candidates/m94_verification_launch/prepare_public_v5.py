"""Public summon and real SP wait for the host's required owned target."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=OUT/'compact.commands.public_v4.prepared.json';assert sha(source)=='333fe2acb335b379fe7fca87ff0d0ae20a9bd2a466f008dfb2156d31ed3b995d';rows=json.loads(source.read_bytes());changes=[]
 for c in rows:
  if c.get('source')=='c409_kalts' and c['action']=='skill':changes.append({'before':dict(c),'reason':'Host requires real owned Mon3tr and15 recovered SP after deployment'});c['at']=3600;changes[-1]['after']=dict(c)
  elif c.get('source')=='c409_kalts' and c['action']=='withdraw':changes.append({'before':dict(c)});c['at']=3630;changes[-1]['after']=dict(c)
  elif c.get('alias')=='c409_lisa' and c['action']=='deploy':changes.append({'before':dict(c),'reason':'Keep occupied host tile4,4 free of an overlapping public deployment'});c['row']=4;c['col']=5;changes[-1]['after']=dict(c)
 assert len(changes)==3;added={'at':3150,'action':'skill','source':'c409_kalts','ability':'ability/kalts_summon','payload':{'position':{'row':6,'col':6},'facing':'right'}};rows.append(added);rows.sort(key=lambda c:c['at'])
 commands=OUT/'compact.commands.public_v5.prepared.json';receipt=OUT/'runthrough_launch.public_v5.prepared.json'
 if commands.exists() or receipt.exists():raise ValueError('Preserve revised input')
 commands.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8',newline='');launch=json.loads((OUT/'runthrough_launch.public_v4.prepared.json').read_bytes());launch.update(commands=str(commands),commands_sha=sha(commands),status='Prepared summon/realSPwait/cell-only revision; V3 source run remains unchanged',owned_target_revision={'observed_live_v3_failure':{'time':3420,'ability':'ability/kalts_host_s3','reason':'No legal ability target','receipt_status':'Read-only live complete-line observation; final sealed V3 receipt pending'},'previous_commands_sha':sha(source),'changes':changes,'added_public_summon':added,'owned_spawn_cost_DP':10,'slot_policy':'Original8 slots retained; own host+token+Lisa at most3 during this overlap, with complete real terrain checks','attributes_or_SP_grants':False});receipt.write_text(json.dumps(launch,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'commands_sha':sha(commands),'launch_sha':sha(receipt)}))
if __name__=='__main__':main()
