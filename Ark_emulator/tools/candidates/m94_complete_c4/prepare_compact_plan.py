"""Compact first deployments before the last native fragment, unchanged costs."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4';SOURCE=ROOT.parent/'unpack_work/campaign_m91_complete_c4_candidate/stage/level_main_04-09.m92.first_hit.source_circle.prepared.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert sha(SOURCE)=='7e0e3c842b7f3af8d561a4d45f5f834ffc560ec2eb489bdd5d20147a36da19f9';p=json.loads(SOURCE.read_bytes());s=p['scenarioDraft'];defs={d['id']:d for section in ['entities','abilities','rules','definitions'] for d in p.get(section,[])}
 # Source has one wave and five sequential nonblocking fragments. Birth offsets
 # are parallel within each fragment, and count/interval extend its duration.
 elapsed=0;timeline=[]
 for i,f in enumerate(s['timeline']['waves'][0]['fragments']):
  elapsed+=f.get('pre_delay_seconds',0);start=elapsed;duration=max(a.get('delay_seconds',0)+max(0,a.get('count',1)-1)*a.get('interval_seconds',0) for a in f['actions']);elapsed+=duration
  timeline.append({'fragment':i,'nominal_start_seconds':start,'nominal_last_birth_seconds':elapsed,'births':sum(a.get('count',1) for a in f['actions'])})
 commands=[];operators=[]
 for index,uid in enumerate(s['roster']):
  d=defs[uid];ground=d['components']['deployable']['terrain']=='ground';at=index*390;alias='c409_'+uid.rsplit('_',1)[-1];long='amgoat' in uid;row,col=(6,3) if ground else ((4,5) if long else (4,4))
  skill=next((a for a in d['components'].get('abilities',[]) if defs[a].get('activation',{}).get('mode')=='manual' and 'summon' not in a and 'cannon' not in a),None)
  commands.append({'at':at,'action':'deploy','entity':uid,'row':row,'col':col,'facing':'right','alias':alias})
  if skill:commands.append({'at':at+(750 if long else 300),'action':'skill','source':alias,'ability':skill})
  commands.append({'at':at+(780 if long else 360),'action':'withdraw','source':alias})
  operators.append({'unit':uid,'alias':alias,'deploy_at':at,'skill_attempt':skill,'base_cost':d['components']['attributes']['base']['deploy_cost'],'cell':{'row':row,'col':col}})
 commands.sort(key=lambda c:c['at']);assert operators[-1]['deploy_at']<timeline[-1]['nominal_start_seconds']*30
 path=OUT/'public_fixed12_plan.compact.prepared.json'
 if path.exists():raise ValueError('Preserve plan')
 report={'source_stage_sha':sha(SOURCE),'source_wave_count':1,'native_fragment_timing':timeline,'nominal_timing_note':'No blockFragment actions; runtime scheduler rounding and managed clearing remain authoritative. These read-only derived times do not replace the native source timeline.','commands':commands,'operators':operators,'first12_deploy_window_ticks':[0,operators[-1]['deploy_at']],'max_scheduled_own_operators':2,'original_deploy_capacity':s['parameters']['deploy_capacity'],'base_life_required':99999,'status':'Prepared; original costs/DP/HP/heat effects and native seed retained. Runtime acceptance, missing-SP/death/control rejections and timing revisions must be recorded.','whole_stage_executed':False}
 path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(path),'last_first_deploy':operators[-1]['deploy_at'],'last_fragment_nominal_start':timeline[-1]['nominal_start_seconds']*30,'last_command':commands[-1]['at']}))
if __name__=='__main__':main()
