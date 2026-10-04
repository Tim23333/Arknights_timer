import sys,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m86_immunity_environment_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def request():return {'op':'no_source_damage','fixed_amount':10,'damage_type':'true','attack_type':'NONE','origin':{'kind':'synthetic_cross_probe','cell':{'row':0,'col':0}},'ignore_for_sp':False,'damage_without_modify':False,'node_is_env_damage':False,'env_blackboard_injected':True,'environmental':True,'target':2,'rules':{'damage.pipeline':'rule/m86/base'}}
def fixture():
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/m86/target','kind':'entity','tags':['enemy'],'components':{'spatial':{},'selection_state':{'side':1},'attributes':{'base':{'max_hp':200,'atk':20,'def':0,'mres':0}},'resources':{'hp':{'initial':200,'capacity':200,'role':'health'},'sp':{'initial':0,'capacity':20,'recovery_rule':'rule/m86/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},'lifecycle':{'policy':'policy/ark_lifecycle'},'buffs':{'initial':['buff/m86/hook']},'abilities':['ability/m86/silence']}}],
 'buffs':[{'id':'buff/m86/hook','kind':'buff','active_rule':'rule/m86/active','modifiers':[{'attribute':'atk','layer':'flat','value':7}],'selection_flags':{'abnormal_flags':[9],'abnormal_immunes':[0]},'damage_hooks':[{'phase':'after','rule':'rule/m86/after'}]},{'id':'buff/m86/silent','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[12]}}],
 'abilities':[{'id':'ability/m86/silence','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/m86/silent'}]},'timeline':[]}],
 'rules':[{'id':'rule/m86/sp','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}},{'id':'rule/m86/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}},{'id':'rule/m86/base','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],'output':'nodes.result'}},{'id':'rule/m86/after','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':inputs.source == {} and context.source == {},'amount':inputs.effect.settlement.amount*2,'allocations':[],'events':[]}"}],'output':'nodes.result'}}],
 'scenarioDraft':{'id':'scene/m86/no_source_hook','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/m86/target','instanceAlias':'target','position':{'row':0,'col':0}}],'scheduledEffects':[{'at':t,'effect':request()} for t in [0,2,4]]}}

def test_no_source_safe_afterhooks_filter_inactive_buff_preserve_origin_sp_and_expiry_disk_replay(tmp_path):
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=860072);s.submit({'action':'skill','source':'target','ability':'ability/m86/silence'},at=1);s.advance(3);assert s.ctx.resources.current('target','hp')==170 and s.ctx.resources.current('target','sp')==2
 path=tmp_path/'none_hook.ordered.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(2);r.advance(2);assert s.ctx.resources.current('target','hp')==150 and s.ctx.resources.current('target','sp')==3
 packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount'],e['payload']['source']) for e in packets]==[(0,20,None),(2,10,None),(4,20,None)]
 assert all(e['payload']['origin']==request()['origin'] and e['payload']['ignore_for_sp'] is False for e in packets)
 assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

def test_source_none_active_hook_real_rule_failure_restores_all_state():
 p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':999,'effect':request()}];next(r for r in p['rules'] if r['id']=='rule/m86/after')['implementation']['nodes'][0]['expression']='1/0';s=Engine.create(Compiler().compile(p),seed=860073);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute(None,['target'],request())
 assert s.checkpoint()==before and not s.ctx.buffs.applicability._busy

def test_future_epoch_guard_preserved_with_actual_final_dead_generation_increment():
 from tools.experiments.m85_death_sequence.test_sequence import fixture as base_fixture
 p=base_fixture();p['entities'][0]['components']['lifecycle']['death_projectiles']*=2;s=Engine.create(Compiler().compile(p),seed=760070);s.ctx.set('slime',('runtime','death_generation'),1);old=s.ctx.buffs.toggles.pulse;seen=[]
 def pulse(event,payload):
  old(event,payload)
  if event=='projectile.launched' and not seen:seen.append(True);s.ctx.set('slime',('runtime','death_generation'),2)
 s.ctx.buffs.toggles.pulse=pulse;s.submit({'action':'skill','source':'hero','ability':'ability/peer/kill'},at=1);s.advance(3)
 assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1 and s.ctx.get('slime',('runtime','death_generation'))==3
