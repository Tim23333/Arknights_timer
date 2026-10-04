"""Fresh source-controlled Flame four-ray gate under original7e76 identity."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_lifetime_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter08_flame_device.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
MODULE=ROOT/'packages/campaign/chapter08_consumers/flame/module.v2.reference.json';OUT=ROOT/'packages/campaign/chapter08_consumers/special/flame_independent_v2';CORE='7e76e49e8b196f1c7ec6d3a08c7760cbb4ebc7eaa02ef778f6e71c820549fef8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def package(kind):
 p=json.loads(MODULE.read_bytes());p['manifest']['metadata']['peer_fixture']='Independent target/controller definitions, not native roster/NPC/wholeJT8-3; originaldeviceHP6000/ATK0/SP25 unchanged.';uid=p['entities'][0]['id'];p['scenarioDraft']={'id':'scene/peer/flame/'+kind,'ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':7},'objectives':{},'initialEntities':[{'definition':uid,'instanceAlias':'flame','position':{'row':3,'col':3}}]}
 for name,row,col,res in [('up',2,3,11),('right',3,4,29),('down',4,3,47),('left',3,2,61)]:
  id='unit/peer/flame/'+name;components={'attributes':{'base':{'max_hp':20000,'atk':0,'def':777,'mres':res,'one_minus_status_resistance':1}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}};p['entities'].append({'id':id,'kind':'entity','tags':['player',name],'components':components});p['scenarioDraft']['initialEntities'].append({'definition':id,'instanceAlias':name,'position':{'row':row,'col':col}})
 if kind=='qualifiers':
  p['entities'][1]['components']['selection_state']['motion']=2
  for name,row,col,state in [('camo',3,3.5,{'side':0,'camouflage':True}),('enemy',3.5,3,{'side':1}),('neutral',3,2.5,{'side':2}),('free',2.5,3,{'side':0,'target_free':True})]:
   id='unit/peer/flame/'+name;p['entities'].append({'id':id,'kind':'entity','tags':['qualifier'], 'components':{'attributes':{'base':{'max_hp':20000,'atk':0,'def':13,'mres':0}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'selection_state':{'motion':1,'category':1,'unit_type':1,**state},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']['initialEntities'].append({'definition':id,'instanceAlias':name,'position':{'row':row,'col':col}})
 if kind=='hook':
  rule='rule/peer/flame/half';buff='buff/peer/flame/half';p['rules'].append({'id':rule,'kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':inputs.effect.settlement.accepted,'amount':inputs.effect.settlement.amount*.5,'allocations':[],'events':[]}"}],'output':'nodes.result'}});p['buffs'].append({'id':buff,'kind':'buff','damage_hooks':[{'phase':'after','rule':rule,'condition':"inputs.effect.damage_type=='arts'"}]});p['entities'][2]['components']['buffs']={'initial':[buff]}
 if kind=='consider_false':
  rule='rule/peer/flame/unhurtable';buff='buff/peer/flame/unhurtable';p['rules'].append({'id':rule,'kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"inputs.effect.settlement if ('consider_unhurtable' in inputs.effect.parameters and inputs.effect.parameters.consider_unhurtable == False) else {'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.result'}});p['buffs'].append({'id':buff,'kind':'buff','damage_hooks':[{'phase':'after','rule':rule,'condition':"inputs.effect.damage_type=='arts'"}]});p['entities'][2]['components']['buffs']={'initial':[buff]}
 return p
def run(kind,expected_arts=None):
 p=package(kind);s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=821);folder=OUT/kind;folder.mkdir(parents=True,exist_ok=True);s.session.advance(750);cp=folder/'checkpoint750.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h),providers=providers());s.session.advance(55);r.session.advance(55);head=replay(s.program,s.export_replay(),providers=providers());assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
 launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==4 and all(e['time']==749 for e in launches);hits=[e for e in s.session.events if e['type']=='damage.accepted'];arts=[e for e in hits if e['payload'].get('damage_type')=='arts']
 # Damage event records carry no required damage_type field; distinguish actual fixed first hit amounts from child56/62.
 arts=[e for e in hits if e['payload']['amount'] not in (56,62)]
 amounts=sorted(e['payload']['amount'] for e in arts)
 if expected_arts is not None:assert amounts==sorted(expected_arts),(kind,amounts)
 assert s.ctx.resources.current('flame','hp')==6000 and not s.ctx.active('flame') and s.ctx.resources.current('flame','sp')==0
 (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
 with (folder/'events.jsonl').open('wb') as f:
  for event in s.session.events:f.write((json.dumps(thaw(event),ensure_ascii=False,separators=(',',':'))+'\n').encode())
 return {'kind':kind,'launches':[(e['time'],e['payload']['definition']) for e in launches],'packets':[(e['time'],e['payload']['target'],e['payload']['amount']) for e in hits],'CP750_to805':True,'head':True,'all_events':True,'fixed_amounts':amounts,'HP6000_not_fake_dead':True,'sourceSPspent0':True,'files':{str(q):sha(q) for q in folder.iterdir() if q.is_file()}}
def main():
 assert implementation_digest()==CORE;before=sha(MODULE);OUT.mkdir(exist_ok=True);rows=[]
 rows.append(run('four_original_directions',[890,710,530,390]));rows.append(run('qualifiers',[890,710,530,390]));rows.append(run('hook',[890,355,530,390]));counter=run('consider_false');assert counter['fixed_amounts']==sorted([890,530,390])
 result={'status':'required_content_flag_gap_with_positive_cases','core':CORE,'module_sha256':before,'source_after':sha(MODULE),'positive_cases':rows,'required_counter':counter,'native_contract':'flame_s FixedValueDamage original _considerUnhurtablefalse not copied to source effect parameters. Controlled actual receiver hook rejects right arts; expected native1000*(1-.29)=710 must bypass onlyunhurtable, retaining otherhooks. This is content requirement, no generic ID branch.','neutral_policy':'OriginaltargetSide2 translatedneutral-source toabsolute playerbit1; nativebody mapping unverified and declared source-reference, enemy/neutral witnesses skipped.','clock':'NativeSP25/initial0/increment1; existingdt0 reference ready749, not clientnative tickproof.','no_source_complete_device_or_stage_gate':True,'client_verified':False};assert before==sha(MODULE);out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out)}))
if __name__=='__main__':main()
