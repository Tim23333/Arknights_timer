"""Author public commands only; no HP, DP, cost, terrain or slot shortcuts."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
SOURCE=ROOT.parent/'unpack_work/campaign_m91_complete_c4_candidate/stage/level_main_04-09.m92.first_hit.source_circle.prepared.json'
PIN='7e0e3c842b7f3af8d561a4d45f5f834ffc560ec2eb489bdd5d20147a36da19f9'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert sha(SOURCE)==PIN;p=json.loads(SOURCE.read_bytes());s=p['scenarioDraft'];defs={d['id']:d for section in ['entities','abilities','rules','definitions'] for d in p.get(section,[])}
 assert len(s['roster'])==12 and len(set(s['roster']))==12 and sum(t['tileKey']=='tile_volcano' for t in s['map']['tiles'])==8
 # One operator at a time deliberately keeps all original eight available slots.
 # Returns and natural DP recovery finance each later public deployment.
 commands=[];rows=[]
 for index,uid in enumerate(s['roster']):
  d=defs[uid];deploy=d['components']['deployable'];ground=deploy['terrain']=='ground';at=index*900;alias='c409_'+uid.rsplit('_',1)[-1]
  row,col=(6,3) if ground else (4,4)
  skill=next((a for a in d['components'].get('abilities',[]) if defs[a].get('activation',{}).get('mode')=='manual' and 'summon' not in a and 'cannon' not in a),None)
  commands.append({'at':at,'action':'deploy','entity':uid,'row':row,'col':col,'facing':'right','alias':alias})
  if skill:commands.append({'at':at+450,'action':'skill','source':alias,'ability':skill})
  commands.append({'at':at+660,'action':'withdraw','source':alias})
  rows.append({'unit':uid,'alias':alias,'cell':{'row':row,'col':col},'terrain':deploy['terrain'],'cost_base':d['components']['attributes']['base']['deploy_cost'],'skill_attempt':skill,'note':'Skills/withdrawals may correctly reject if real combat retires or controls the actor; retain actual command receipts.'})
 commands.sort(key=lambda c:c['at']);OUT.mkdir(parents=True,exist_ok=True)
 path=OUT/'public_fixed12_plan.prepared.json'
 if path.exists():raise ValueError('Preserve existing authored plan')
 report={'source_stage_sha256':PIN,'source_stage':str(SOURCE),'commands':commands,'operators':rows,'short_prefix_ticks':1600,'full_plan_last_command':commands[-1]['at'],'base_life_authoring':{'required_initial':99999,'required_capacity':99999,'native_stage_initial':s['resources']['life']['initial'],'native_stage_capacity':s['resources']['life']['capacity']},'source_timeline_and_map':'Must retain complete source timeline, 49 births and all eight real heatfields in the new life99999 stage.','slot_policy':'Keep default8 and original deployment rules; commands never request more than one own operator simultaneously.','acceptance':'Prepared only; M93/94 ability receipts and actual cost/command acceptance verification pending.','whole_stage_executed':False,'client_verified':False}
 path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');assert sha(SOURCE)==PIN;print(json.dumps({'plan_sha256':sha(path),'operators':len(rows),'commands':len(commands),'last_command':commands[-1]['at']}))
if __name__=='__main__':main()
