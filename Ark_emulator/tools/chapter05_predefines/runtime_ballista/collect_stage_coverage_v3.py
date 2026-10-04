"""Read sealed original full journals; distinguish actual source triggers."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter05_public_v3'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['05-09','05-10'],required=True);a=ap.parse_args();row=next(r for r in json.loads((OUT/'prepared_commands.json').read_bytes())['cases'] if r['native_id']=='level_main_'+a.stage)
 base=Path('E:/ArkSimEvidence/campaign')/(a.stage.replace('-','_')+'_8fa4e36752e92f7d')/'public_v1.json';original=base.with_suffix('.original.json');r=json.loads(original.read_bytes());journal=Path(r['journal']['path']);assert sha(journal)==r['journal']['sha256']
 p=json.loads(Path(row['overlay']).read_bytes());assert sha(Path(row['overlay']))==r['package_sha256']==row['overlay_sha'];expected=set(r['expected_births']);births=Counter();actors={};ballistas=set();casts=Counter();ballista_launch=[];ballista_damage=[];branch=[];deploy=[];accepted=[];refused=[];ability=[];registrations=[];sp_cost=[];mon=[]
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);k=e['type'];v=e['payload']
   if k in ('entity.created','entity.registered'):
    d=v.get('definition');sid=v.get('source');actors[sid]=d
    if d in expected and k=='entity.created':births[d]+=1
    if d=='unit/ch5/ballista/source_level6':ballistas.add(sid);registrations.append(e)
    if d=='unit/kalts_mon3tr_model':mon.append(e)
   if k=='command.accepted':
    accepted.append(e)
    if v['action']['action']=='deploy':deploy.append(e)
   elif k=='command.rejected':refused.append(e)
   elif k=='ability.started':ability.append(e);casts[(actors.get(v.get('source'),str(v.get('source'))),v['ability'])]+=1
   if k=='entity.activated':branch.append(e)
   if k=='projectile.launched' and v.get('source') in ballistas:ballista_launch.append(e)
   if k=='damage.accepted' and v.get('source') in ballistas:ballista_damage.append(e)
   if k=='resource.changed' and (v.get('source') in ballistas or v.get('target') in ballistas) and v.get('resource')=='sp' and v.get('delta',0)<0:sp_cost.append(e)
 assert dict(births)==r['actual_births'] and sum(births.values())==row['births']
 covered={e['payload']['action']['entity'] for e in deploy if e['time']<r['terminal_tick']};roster=set(p['scenarioDraft']['roster'])
 result={'stage':row['native_id'],'core':r['implementation'],'original_sha':sha(original),'journal':r['journal'],'native_births':dict(births),'native_DP':row['native_DP'],'native_slots':row['native_slots'],'all12_first_deploys_before_terminal':covered==roster,'missing_actual_first_deploys':sorted(roster-covered),'actual_deploys':deploy,'accepted_commands':accepted,'refused_commands':refused,'actual_ability_started':ability,'cast_counts':[{'definition':d,'ability':a,'count':n} for (d,a),n in casts.items()],'ballista':{'actual_instances':sorted(ballistas),'initial_registration_or_creation':registrations,'actual_projectile_launches':ballista_launch,'actual_accepted_damage':ballista_damage,'actual_negative_SP_resource_events':sp_cost},'actual_branch_activation_events':branch,'actual_mon3tr_creation':mon,'terminal':{'tick':r['terminal_tick'],'end':r['end_tick'],'kills':r['state']['kills'],'leaks':r['state']['leaks'],'base_life':r['base_life_final']},'source_trigger_claim_policy':'Only actual journal events above; absent source branches remain separately tested, not stage-triggered.','complete_CP_replay_acceptance_separate':True,'client_verified':False,'registry_modified':False}
 dest=OUT/(a.stage+'.original_coverage_v1.json');assert not dest.exists();dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'actual12':result['all12_first_deploys_before_terminal'],'missing':result['missing_actual_first_deploys'],'launches':len(ballista_launch),'ballista_damage':len(ballista_damage),'refusals':len(refused)}))
if __name__=='__main__':main()
