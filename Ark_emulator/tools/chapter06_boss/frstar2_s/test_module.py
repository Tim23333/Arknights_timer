"""Actual public story Boss probes; blood omission only explicit pre-gap fixture."""
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.frstar2_s.build_module import OUT,COLD,UID,I,B,BLOOD
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def package(blood=True):
 p=json.loads((OUT/'model.json').read_bytes())
 if not blood:
  p['buffs']=[b for b in p['buffs'] if b['id']!=BLOOD];p['entities'][0]['components']['buffs']['initial'].remove(BLOOD)
  p['manifest']['metadata']['probe_omission']='Blood only omitted to isolate skill consumers while generic protocol rejects exact native BUFF without_modify; not whole consumer pass'
 p['entities'].append({'id':'unit/test/story/player','kind':'entity','tags':['player','ground','cold_receiver'],'components':{'attributes':{'base':{'max_hp':1000000,'atk':0,'def':100,'mres':25,'attack_speed_ratio':1,'block_count':0}},'resources':{'hp':{'role':'health','initial':1000000,'capacity':1000000}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}}})
 p['scenarioDraft']={'id':'scene/ch6/story/author','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':9,'default_tile':{'terrain':'ground','buildableType':1,'passableMask':1}},'resources':{'dp':{'initial':30,'capacity':99},'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':UID,'instanceAlias':'boss','position':{'row':2,'col':2}}],'roster':['unit/test/story/player']}
 return p
def create(blood=True):return Engine.create(Compiler(providers=providers()).compile(package(blood),packages=[COLD]),seed=6217,providers=providers())
def deploy(s,at=0):s.submit({'action':'deploy','definition':'unit/test/story/player','alias':'player','position':{'row':2,'col':3}},at=at)
def events(s,name):return [e for e in s.session.events if e['type']==name]
def flags(s,who):return s.ctx.spatial.selection_state(who,DEFAULT_STATE)['abnormal_flags']
def test_exact_distinct_profile_nevertrigger_no_rebirth():
 p=json.loads((OUT/'model.json').read_bytes());c=p['entities'][0]['components'];a=c['attributes']['base']
 assert (a['max_hp'],a['atk'],a['def'],a['mres'],a['move_speed'],a['attack_interval'])==(95000,1200,300,50,.25,3.7)
 assert c['abilities']==[I,B] and 'rebirth' not in c and c['selection_state']['abnormal_immunes']==[0,12]
 blood=next(b for b in p['buffs'] if b['id']==BLOOD);e=blood['effects'][0]
 assert blood['interval_seconds']==1 and e['fixed_amount']==2000 and e['damage_without_modify'] is True and e['attack_type']=='BUFF' and e['ignore_for_sp'] is True
def test_pre_gap_skills_nevertrigger_burst87_cold10_and_shield55_three():
 s=create(False);deploy(s);s.session.advance(779)
 starts=[(e['time'],e['payload']['ability']) for e in events(s,'ability.started') if e['payload']['source']==s.session.world.resolve('boss')]
 assert starts==[(480,B),(690,I)]
 damage=[(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted') if e['payload']['source']==s.session.world.resolve('boss')]
 assert damage==[(567,900)]
 b=next(b for b in s.ctx.get('player',('buffs','instances'),[]) if b['definition']=='buff/ch6/cold/e2c_cold');assert b['started_at']==567 and b['expires_at']==867
 tokens=[e for e in s.session.world.entities() if 'sealed_floor' in e.get('tags',[])];assert len(tokens)==3
 assert not events(s,'entity.rebirth.started') and s.ctx.resources.current('boss','hp')==95000
@pytest.mark.parametrize('tick',[1,500,700])
def test_pre_gap_skills_actual_disk_cp_and_head(tick,tmp_path):
 s=create(False);deploy(s);s.session.advance(tick);p=tmp_path/'story.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h),providers=providers());s.session.advance(779-tick);r.session.advance(779-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
