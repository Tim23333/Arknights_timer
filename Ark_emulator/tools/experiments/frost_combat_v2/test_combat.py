from pathlib import Path
from copy import deepcopy
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
NORMAL='ability/frost/normal';BLAST='ability/frost/blast';SLOW='buff/frost/arctic_slow'
def hero():return {'id':'unit/probe','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':17,'mres':40,'attack_interval':1,'attack_speed_ratio':1,'block_count':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
def fixture(policy='first17.bb8.reference_ground',area=False):
 p=json.loads((ROOT/'packages/campaign/chapter04_boss/frost_combat_v2'/(policy+'.json')).read_bytes());p['entities'].append(hero());d=hero();d['id']='unit/director';d['components']['abilities']=['ability/probe/boost','ability/probe/withdraw'];p['entities'].append(d)
 p['buffs'].append({'id':'buff/probe/boost','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]})
 p['abilities'].extend([{'id':'ability/probe/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('boost',{'op':'apply_buff','target':2,'buff':'buff/probe/boost'}),('withdraw',{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}})]])
 source={'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':2,'col':2}};primary={'definition':'unit/probe','instanceAlias':'primary','position':{'row':2,'col':4.4 if area else 3},'components':{'attributes':{'base':{'taunt_level':2}}}}
 if area:source['components']={'ability_timing':{'initial_cooldowns':{BLAST:0}}}
 p['scenarioDraft']={'id':'scene/frost_probe','ruleset':'ruleset/ark_standard','map':{'rows':6,'cols':10},'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'},'initialEntities':[source,primary,{'definition':'unit/director','instanceAlias':'director','position':{'row':5,'col':9}}]}
 if area:p['scenarioDraft']['initialEntities'].extend([{'definition':'unit/probe','instanceAlias':'near','position':{'row':3,'col':2}},{'definition':'unit/probe','instanceAlias':'air','position':{'row':2,'col':3},'components':{'selection_state':{'motion':2},'spatial':{'motion_mode':1}}},{'definition':'unit/probe','instanceAlias':'free','position':{'row':1,'col':2},'components':{'selection_state':{'target_free':True}}}])
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=410493)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'snapshot':s.snapshot(),'commands':s.export_replay(),'events':thaw(tuple(s.session.events))})
def exact(s,tmp,n):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(n);r.advance(n);assert s.checkpoint()==r.checkpoint();assert s.snapshot()==replay(s.program,s.export_replay()).snapshot();return h
@pytest.mark.parametrize('policy,frames',[('first17',[20]),('last28',[31]),('both17_28',[20,31])])
def test_actual_normal_two_animation_events_three_declared_policies_and_flight_cp(policy,frames,tmp_path):
 s=make(fixture(policy+'.bb8.reference_ground'));s.advance(18);exact(s,tmp_path,18);capture(s,'normal_'+policy)
 assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted')]==[(t,252) for t in frames]
 assert len(ev(s,'attack.accepted'))==1;assert s.ctx.resources.current('boss','hp')==25000
 assert s.ctx.get('boss',('runtime','cooldowns',BLAST))==255
@pytest.mark.parametrize('policy,duration,air_hit',[('first17.bb8.reference_ground',240,False),('first17.raw4.source_motion3',120,True)])
def test_blast_precise28_source_radius_plus_qualified_primary_damage_debuff_sp_flags_and_expiry(policy,duration,air_hit,tmp_path):
 p=fixture(policy,True);p['entities'][1]['components']['resources']['sp']={'initial':0,'capacity':100,'recovery_rule':'rule/probe/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}
 p['rules'].append({'id':'rule/probe/sp','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
 s=make(p);s.advance(28);assert not ev(s,'damage.accepted');exact(s,tmp_path,1)
 packets=[e for e in ev(s,'damage.accepted') if e['payload']['ability']==BLAST];expect={s.session.world.resolve(x) for x in (['primary','near','air'] if air_hit else ['primary','near'])}
 assert {e['payload']['target'] for e in packets}==expect and all(e['time']==28 and e['payload']['amount']==378 for e in packets)
 assert all(e['payload']['damage_flags']=={'source_attack_type':'SPLASH','ignore_for_sp':False} for e in packets);assert not ev(s,'attack.accepted')
 assert s.ctx.resources.current('primary','sp')==1;row=next(b for b in s.ctx.get('primary',('buffs','instances')) if b['definition']==SLOW);assert row['expires_at']==28+duration
 assert s.ctx.get('primary',('attributes','modifiers'))[0]['value']==-.5
 s.advance(duration-1);assert s.session.time==28+duration and not any(b['definition']==SLOW for b in s.ctx.get('primary',('buffs','instances')))
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'blast_'+policy)
def test_shared111clock_initial255_first_ready_blast333_and_period_after_animation_pause():
 s=make(fixture());s.advance(715);capture(s,'shared_clock')
 starts=ev(s,'ability.started');assert [(e['time'],e['payload']['ability']) for e in starts if e['payload']['source']==2]==[(0,NORMAL),(111,NORMAL),(222,NORMAL),(333,BLAST),(444,NORMAL),(555,NORMAL),(666,BLAST)]
 assert [e['time'] for e in ev(s,'damage.accepted') if e['payload']['ability']==BLAST]==[361,694]
def test_live_hit_atk_after_public_boost_and_source_retire_still_delivers_launched_packet(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'director','ability':'ability/probe/boost'},at=18);s.submit({'action':'skill','source':'director','ability':'ability/probe/withdraw'},at=19);s.advance(18);exact(s,tmp_path,7);capture(s,'live_after_retire')
 assert not s.ctx.alive('boss');assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted')]==[(20,312)]
@pytest.mark.parametrize('area',[False,True])
def test_public_withdraw_during_windup_cancels_normal_or_blast_without_packet(area,tmp_path):
 s=make(fixture(area=area));s.submit({'action':'skill','source':'director','ability':'ability/probe/withdraw'},at=10);s.advance(5);exact(s,tmp_path,32);capture(s,'windup_cancel_'+str(area));assert not ev(s,'damage.accepted')
def env(amount):return {'op':'no_source_damage','target':2,'fixed_amount':amount,'damage_type':'true','attack_type':'NONE','origin':{'kind':'frost_after_environment_probe'},'ignore_for_sp':False,'damage_without_modify':False,'node_is_env_damage':False,'env_blackboard_injected':True,'environmental':True,'rules':{'damage.pipeline':'rule/probe/env'}}
def test_real_after_no_source_rebirth_resets_clock_and_next_normal_uses630(tmp_path):
 p=fixture();p['rules'].append({'id':'rule/probe/env','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'answer','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],'output':'nodes.answer'}});p['scenarioDraft']['scheduledEffects']=[{'at':18,'effect':env(25000)}]
 s=make(p);s.advance(30);assert s.ctx.resources.current('boss','hp')==0 and s.ctx.alive('boss') and not s.ctx.active('boss') and s.ctx.state()['kills']==0
 exact(s,tmp_path,164);capture(s,'after_no_source_rebirth');assert s.ctx.resources.current('boss','hp')==25000 and s.ctx.get('boss',('runtime','cooldowns',BLAST))==423
 assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted') if e['payload']['source']==2]==[(20,252),(188,378)]
 assert not any(b['definition']=='buff/ch4/frstar/initial_sleep_immune' for b in s.ctx.get('boss',('buffs','instances')))
def test_replaceable_damage_rule_and_initial_quantizer_are_consumed():
 p=fixture();p['rules'].extend([{'id':'rule/probe/quantize','kind':'rule','contract':'time.quantize','implementation':{'type':'expression','expression':'int(round(inputs.seconds / inputs.quantum)) + 1'}},{'id':'rule/probe/packet','kind':'rule','contract':'damage.pipeline','implementation':{'type':'expression','expression':"{'accepted':True,'amount':7,'allocations':[],'events':[]}"}}]);p['scenarioDraft']['rules']={'time.quantize':'rule/probe/quantize','damage.pipeline':'rule/probe/packet'}
 s=make(p);assert s.ctx.get('boss',('runtime','cooldowns',BLAST))==256;s.advance(25);capture(s,'replaceable_rule');assert [e['payload']['amount'] for e in ev(s,'damage.accepted')]==[7]
@pytest.mark.parametrize('value',[True,-1,float('nan'),float('inf'),'8.5'])
def test_initial_cooldown_definition_wrong_type_fails_compile(value):
 p=fixture();next(a for a in p['abilities'] if a['id']==BLAST)['initial_cooldown_seconds']=value
 with pytest.raises(ValueError):Compiler().compile(p)
@pytest.mark.parametrize('value',[True,-1,float('nan'),{'unknown':3},None])
def test_bad_effective_instance_clock_override_fails_atomic_creation(value):
 s=make(fixture());before=s.checkpoint();profile={'initial_cooldowns':{BLAST:value}} if value is not None else None
 with pytest.raises(ValueError):s.ctx.lifecycle.create('unit/ch4/frstar/level0',alias='bad',component_overrides={'ability_timing':profile})
 assert s.checkpoint()==before
@pytest.mark.parametrize('value',[1,None,'yes',[]])
def test_qualified_radius_include_primary_bool_validation(value):
 p=fixture(area=True);next(r for r in p['rules'] if r['id']=='rule/frost/radius')['parameters']['include_primary']=value
 with pytest.raises(ValueError):Compiler().compile(p)
