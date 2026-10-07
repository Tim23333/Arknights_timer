"""Public finite plan intent audit. No command-acceptance claim."""
import hashlib,json,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter10_stage_source_peer_v1.source_preflight import exact
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 results=[];guards={}
 for stage,pin in zip(['level_main_00-10','level_main_00-11'],['8c0ef4ab1ce26cf68bc750a798daf3518c64ac2267bbb46594c40dfa1034fc54','f4fb5a05f0b2db23d9c1f7a7119b956920817c5b02b1e232c8f848a84b0bf8ff']):
  facts={}
  try:
   folder=ROOT/'packages/campaign/chapter0_stage_models';p=folder/f'{stage}.public.plan.v4.json';src=folder/f'{stage}.source.v2.json';assert sha(p)==pin;plan=json.loads(p.read_bytes());d=json.loads(src.read_bytes());assert sha(src)==plan['source_package_sha256'];defs={x['id']:x for x in d['definitions']};s=d['scenarioDraft'];exact(plan['roster'],s['roster']);commands=plan['commands'];assert commands==sorted(commands,key=lambda x:x['at']);assert not plan['source_parameters_changed'] and not plan['native_resource_changed'] and not plan['SP_injected'];assert s['resources']['dp']['initial']==10 and s['parameters']['deploy_capacity']==8
   aliases={};live={};cells={};slotrows=[];costrows=[];slot=0;maximum=0;dp=10;lastregen=0;sumcost=0
   def legal(pos,entity):
    row,col=pos['row'],pos['col'];assert type(row)is int and type(col)is int and 0<=row<s['map']['rows'] and 0<=col<s['map']['cols'];tile=s['map']['tiles'][row*s['map']['cols']+col];terrain=entity['components']['deployable']['terrain'];mask={'ground':1,'highland':2,'both':3}[terrain];assert tile['buildableType']&mask,(entity['id'],pos,tile)
   def spend(at,cost):
    nonlocal dp,lastregen,sumcost
    regen=(at-1)//30;dp=min(99,dp+regen-lastregen);lastregen=regen;assert dp>=cost,('DP lower bound',at,dp,cost);dp-=cost;sumcost+=cost;costrows.append({'tick':at,'cost':cost,'lower_DP_after':dp})
   for c in commands:
    assert type(c['at'])is int and c['at']>=0 and c['action'] in ['deploy','withdraw','skill']
    if c['action']=='deploy':
     entity=defs[c['entity']];assert c['entity'] in s['roster'] and c['alias'] not in aliases;legal(c,entity);cell=(c['row'],c['col']);assert cell not in cells;aliases[c['alias']]=entity;live[c['alias']]=entity;cells[cell]=c['alias'];capacity=entity['components']['deployable'].get('capacity',1);slot+=capacity;spend(c['at'],entity['components']['deployable']['base_cost']);slotrows.append({'tick':c['at'],'action':'deploy','alias':c['alias'],'slots':slot});maximum=max(maximum,slot);assert slot<=8
    elif c['action']=='withdraw':
     assert c['source'] in aliases
     if c['source'] in live:
      entity=live.pop(c['source']);slot-=entity['components']['deployable'].get('capacity',1);cells={key:v for key,v in cells.items() if v!=c['source']};slotrows.append({'tick':c['at'],'action':'withdraw','alias':c['source'],'slots':slot})
    else:
     assert c['source'] in live,('skill after intended withdrawal',c);ability=defs[c['ability']];assert c['ability'] in live[c['source']]['components']['abilities'];assert ability['kind']=='ability'
     attempt=next((x for x in plan['summon_attempts'] if x['command']==c),None)
     if attempt:
      token=defs[attempt['token_definition']];legal(c['payload']['position'],token);capacity=token['components']['deployable'].get('capacity',1);assert capacity==attempt['native_capacity'];assert attempt['declared_cost']==token['components']['deployable']['base_cost'];slot+=capacity;maximum=max(maximum,slot);assert slot<=8;spend(c['at'],attempt['declared_cost']);slotrows.append({'tick':c['at'],'action':'summon_intent','definition':token['id'],'slots':slot})
   assert {x['entity'] for x in commands if x['action']=='deploy'}==set(s['roster']) and len([x for x in commands if x['action']=='deploy'])==12
   ready=[]
   for row in plan['source_native_SP_ready_windows']:
    entity=defs[row['unit']];ability=defs[row['skill']];exact(row['source_resource'],entity['components']['resources']['sp']);assert row['source_activation_cost']==next(x['amount'] for x in ability['activation']['costs'] if x['resource']=='sp');assert row['declared_mode']==ability['activation']['mode'];ready.append({'unit':row['unit'],'SP':row['source_resource'],'cost':row['source_activation_cost'],'retries':row['retry_ticks'],'actual_ready_guaranteed':False})
   m=defs['unit/char_151_myrtle']['components']['resources']['sp'];assert m['initial']==10 and m['capacity']==24 and plan['Myrtle_source_cost']==24;deploy=next(c['at'] for c in commands if c['action']=='deploy' and c['entity']=='unit/char_151_myrtle');earliest=deploy+14*30;assert earliest==451 and plan['Myrtle_first_conservative_ready_retry_at']>=earliest;assert any(c['at']==plan['Myrtle_first_conservative_ready_retry_at'] and c.get('ability')=='ability/campaign_myrtle_s2' for c in commands)
   ack=plan['ACK_driver'];assert sha(ack['path'])==ack['sha256'] and not ack['static_control_ids_or_ACK_schedule'];assert ack['policy']=='external_dialogue_observation_plus_one_tick/v2';guards[ack['path']]=ack['sha256'];facts={'commands':len(commands),'deployments':12,'maximum_intended_slots':maximum,'slot_intent':slotrows,'funding_native_DP_only_no_refunds_or_skill_income':costrows,'total_cost':sumcost,'source_SP_windows':ready,'Myrtle_earliest_periodic_no_previous_cast_tick':earliest,'actual_acceptance_not_guaranteed':True};results.append({'stage':stage,'passed':True,'facts':facts});guards[str(p)]=sha(p);guards[str(src)]=sha(src)
  except Exception as e:results.append({'stage':stage,'passed':False,'facts':facts,'error':str(e),'traceback':traceback.format_exc()})
 guards[str(Path(__file__))]=sha(__file__);report={'schema':'ark-sim/chapter0-plan-static-peer/v1','static_plan_intent_approved':all(x['passed'] for x in results),'results':results,'source_guards':guards,'actual_commands_accepted':False,'whole_approved':False,'simulation_executed':False,'boundaries':['DP calculation is before-tick native periodic lower bound, ignores all skill gains and refunds; actual death/story inputlock/terminal/resource freeze still can reject.','Event SP and selector-qualified host SP depend on actual attacks/received damage/summon; clock retries do not certify readiness.','Myrtle early91 attempt diagnostic may reject; 24-cost initial10 periodic retry452 is planned conservative first window after deploy31, not injected SP.','SourceDead/terminal/manual-mode/automatic-only/target/cast rejection must be fully logged; repeated attempts are not guaranteed success.','PublicAckDriver is dynamic actual-observation+one tick reference, not native UI dwell or combat-pause proof.']};out=ROOT/'validation/campaign/chapter0_stage_input_peer_v1/plan.review.v1.json';assert not out.exists();out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'approved':report['static_plan_intent_approved'],'results':[{'stage':x['stage'],'passed':x['passed'],'error':x.get('error')} for x in results],'sha':sha(out)}));return 0 if report['static_plan_intent_approved'] else 1
if __name__=='__main__':raise SystemExit(main())
