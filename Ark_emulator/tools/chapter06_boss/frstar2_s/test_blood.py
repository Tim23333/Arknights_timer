"""Exact story passive on isolated generic BUFF/no-source candidate."""
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.frstar2_s.test_module import package,deploy,events
from tools.chapter06_boss.frstar2_s.test_controls import controller
from tools.chapter06_boss.frstar2_s.build_module import COLD,UID,BLOOD
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def make(p=None):return Engine.create(Compiler(providers=providers()).compile(p or package(),packages=[COLD]),seed=6217,providers=providers())
def packets(s):return [e for e in events(s,'damage.accepted') if e['payload'].get('source_policy')=='none']
def test_native_first30_boundary_amount_and_buff_provenance():
 s=make();s.session.advance(30);assert not packets(s) and s.ctx.resources.current('boss','hp')==95000
 s.session.advance(1);assert [(e['time'],e['payload']['amount']) for e in packets(s)]==[(30,2000)]
 e=packets(s)[0]['payload'];assert e['source'] is None and e['attack_type']=='BUFF' and e['ignore_for_sp'] is True and e['damage_without_modify'] is True
 assert e['origin']['buff_timer']['owner']==s.session.world.resolve('boss') and e['origin']['buff_timer']['definition']==BLOOD
def test_native48_ticks_true_death_once_cleanup_and_no_rebirth():
 s=make();s.session.advance(1441)
 ps=packets(s);assert [e['time'] for e in ps]==list(range(30,1441,30))
 assert all(e['payload']['settlement_amount']==2000 for e in ps) and ps[-1]['payload']['actual_health_loss']==1000
 assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.alive('boss') and len(events(s,'entity.died'))==1
 assert not events(s,'entity.rebirth.started') and not s.ctx.get('boss',('buffs','instances'),[])
 s.session.advance(100);assert len(packets(s))==48
def test_source_native_blood_bypasses_actual_target_hook_and_sp_damage_driver():
 p=package();c=p['entities'][0]['components'];c['attributes']['base']['atk']=1200000
 deny='rule/test/story/deny';buff='buff/test/story/deny'
 p['rules'].append({'id':deny,'kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.result'}})
 p['buffs'].append({'id':buff,'kind':'buff','damage_hooks':[{'phase':'after','rule':deny}]});c['buffs']['initial'].append(buff)
 p['rules'].append({'id':'rule/test/story/sp','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
 c['resources']['sp']={'initial':0,'capacity':99,'recovery_rule':'rule/test/story/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}
 s=make(p);s.session.advance(91);assert s.ctx.resources.current('boss','hp')==89000 and s.ctx.resources.current('boss','sp')==0
 assert len(events(s,'damage.modification_bypassed'))==3 and len(packets(s))==3
def test_actual_public_retire_stops_owned_blood_timer():
 p=package();aid='ability/test/story/retire';controller(p,aid)
 p['selectors'].append({'id':'selector/test/story/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'story_boss'},{'state':'alive'}],'limit':1})
 p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/story/boss','timeline':[{'at':0,'effect':{'op':'retire','parameters':{'reason':'controlled_story_retire'}}}]})
 s=make(p);s.submit({'action':'skill','source':'controller','ability':aid},at=31);s.session.advance(200)
 assert [e['time'] for e in packets(s)]==[30] and not s.ctx.active('boss')
def test_full_native_blood_and_skills_coexist_without_normal_or_attack_clock():
 s=make();deploy(s);s.session.advance(780)
 from tools.chapter06_boss.frstar2_s.build_module import I,B
 starts=[(e['time'],e['payload']['ability']) for e in events(s,'ability.started') if e['payload']['source']==s.session.world.resolve('boss')]
 assert starts==[(480,B),(690,I)] and len(packets(s))==25
 assert s.ctx.resources.current('boss','hp')==45000 and not events(s,'projectile.launched')
 assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')]==[(567,900)]
def test_native_timemode1_cold_source_does_not_scale_skill87_frame():
 p=package();p['entities'][0]['tags'].append('cold_receiver');p['entities'][1]['tags'].remove('cold_receiver');controller(p,'ability/ch6/cold/apply5')
 s=make(p);deploy(s);s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=470);s.session.advance(568)
 assert s.ctx.attributes.value('boss','attack_speed_ratio')==pytest.approx(.7)
 assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')]==[(567,900)]
@pytest.mark.parametrize('tick',[29,31,500,1439])
def test_actual_native_blood_disk_checkpoint_and_public_head(tick,tmp_path):
 s=make();deploy(s);s.session.advance(tick);p=tmp_path/'blood.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h),providers=providers());s.session.advance(1450-tick);r.session.advance(1450-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
