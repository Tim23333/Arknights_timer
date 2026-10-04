import sys
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m70_buff_applicability_v2_candidate'));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
def fixture():
 unit={'id':'unit/subject','kind':'entity','tags':['enemy'],'components':{'spatial':{},'selection_state':{'side':1},'attributes':{'base':{'max_hp':1000,'atk':100,'def':0,'mres':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/stun','ability/immune','ability/silence','ability/mixed','ability/removeimmune']}}
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[unit],'rules':[{'id':'rule/stun','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_flags'}},{'id':'rule/notsilenced','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}}],
 'buffs':[{'id':'buff/stun','kind':'buff','duration_seconds':1,'control_rule':'rule/stun','control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':True},'selection_flags':{'abnormal_flags':[0]},'modifiers':[{'attribute':'atk','layer':'flat','value':5}]},{'id':'buff/immune','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_immunes':[0]}},{'id':'buff/silence','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[12]}},{'id':'buff/mixed','kind':'buff','active_rule':'rule/notsilenced','modifiers':[{'attribute':'atk','layer':'flat','value':20}],'selection_flags':{'abnormal_flags':[9],'abnormal_immunes':[0]}}],
 'abilities':[{'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('stun',{'op':'apply_buff','target':'source','buff':'buff/stun'}),('immune',{'op':'apply_buff','target':'source','buff':'buff/immune'}),('silence',{'op':'apply_buff','target':'source','buff':'buff/silence'}),('mixed',{'op':'apply_buff','target':'source','buff':'buff/mixed'}),('removeimmune',{'op':'remove_buff','target':'source','buff':'buff/immune'})]],
 'scenarioDraft':{'id':'scene/applicability','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':4},'initialEntities':[{'definition':'unit/subject','instanceAlias':'subject','position':{'row':0,'col':0}}]}}
def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=7001)
def state(s):
 from ark_sim.domains.selection import DEFAULT_STATE
 return s.ctx.spatial.selection_state('subject',DEFAULT_STATE)
def test_intrinsic_stun_immunity_disables_only_control_and_keeps_modifier_and_buff():
 p=fixture();p['entities'][0]['components']['selection_state']['abnormal_immunes']=[0];s=make(p);s.ctx.buffs.apply('subject','subject','buff/stun')
 assert s.ctx.buffs.controls('subject')=={'move':True,'attack':True,'abilities':True,'block':True} and s.ctx.attributes.value('subject','atk')==105 and len(s.ctx.get('subject',('buffs','instances')))==1
def test_immunity_expiry_reactivates_existing_stun_control_half_open():
 s=make();s.ctx.buffs.apply('subject','subject','buff/immune');s.ctx.buffs.apply('subject','subject','buff/stun');assert s.ctx.buffs.controls('subject')['attack']
 s.advance(4);assert not s.ctx.buffs.controls('subject')['attack'] and s.ctx.attributes.value('subject','atk')==105
def test_silence_mixed_buff_stops_own_immunity_flags_and_modifiers_then_restores():
 s=make();s.ctx.buffs.apply('subject','subject','buff/mixed');assert s.ctx.attributes.value('subject','atk')==120 and state(s)['abnormal_flags']==[9] and state(s)['abnormal_immunes']==[0]
 s.ctx.buffs.apply('subject','subject','buff/silence');assert s.ctx.attributes.value('subject','atk')==100 and state(s)['abnormal_flags']==[12] and state(s).get('abnormal_immunes',[])==[]
 s.advance(4);assert s.ctx.attributes.value('subject','atk')==120 and state(s)['abnormal_flags']==[9]
def test_mutual_contribution_cycle_fails_atomically_instead_of_leaving_immunity_permanent():
 p=fixture();p['rules'][1]['implementation']['expression']='9 not in inputs.status.abnormal_flags';s=make(p);s.session.reaction_budget=8;before=s.checkpoint()
 with pytest.raises(ValueError,match='budget'):s.ctx.buffs.apply('subject','subject','buff/mixed')
 assert s.checkpoint()==before and not s.ctx.buffs.applicability._busy
def test_combo_sleep_immunity_is_distinct_from_flag0_and_controls_public_capture():
 p=fixture();p['rules'].append({'id':'rule/sleep','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_combos'}});p['buffs'].append({'id':'buff/sleep','kind':'buff','control_rule':'rule/sleep','selection_flags':{'abnormal_combos':[0]},'control':{'move':False,'attack':False,'abilities':False,'block':False}});p['entities'][0]['components']['selection_state']['abnormal_combo_immunes']=[0];p['entities'][0]['dependencies']=['buff/sleep'];s=make(p);s.ctx.buffs.apply('subject','subject','buff/sleep')
 assert s.ctx.buffs.controls('subject')['attack'] and state(s)['abnormal_combos']==[]

@pytest.mark.parametrize('flag',[0,12,16,25])
def test_frost_intrinsic_four_native_flag_immunities_keep_mixed_attributes(flag):
 p=fixture();p['entities'][0]['components']['selection_state']['abnormal_immunes']=[0,12,16,25];p['rules'][0]['implementation']['expression']=str(flag)+' in inputs.status.abnormal_flags';p['buffs'][0]['selection_flags']['abnormal_flags']=[flag];s=make(p);s.ctx.buffs.apply('subject','subject','buff/stun')
 assert state(s)['abnormal_flags']==[] and s.ctx.buffs.controls('subject')['move'] and s.ctx.attributes.value('subject','atk')==105

@pytest.mark.parametrize('key',['active_rule','control_rule'])
def test_wrong_contract_and_non_boolean_are_rejected_without_state_changes(key):
 p=fixture();p['buffs'][0][key]='rule/notsilenced';p['rules'][1]['contract']='resource.recovery';p['rules'][1]['implementation']['expression']='inputs.current'
 with pytest.raises(Exception,match='contract|applicability'):make(p)
 p=fixture();p['buffs'][0][key]='rule/notsilenced';p['rules'][1]['implementation']['expression']='1';s=make(p);before=s.checkpoint()
 with pytest.raises(Exception,match='bool|boolean'):s.ctx.buffs.apply('subject','subject','buff/stun')
 assert s.checkpoint()==before and not s.ctx.buffs.applicability._busy

def test_public_immune_then_stun_and_expiry_ordered_checkpoint_and_commands_replay(tmp_path):
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=7001)
 s.submit({'action':'skill','source':'subject','ability':'ability/immune'},at=0);s.submit({'action':'skill','source':'subject','ability':'ability/stun'},at=1);s.advance(2)
 assert s.ctx.buffs.controls('subject')['attack'];path=tmp_path/'immune.ordered.json';digest=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,digest));s.advance(10);r.advance(10)
 assert not s.ctx.buffs.controls('subject')['attack'] and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

def test_readonly_selection_and_control_queries_do_not_resample_or_emit():
 s=make();s.ctx.buffs.apply('subject','subject','buff/stun');before=s.checkpoint()
 for _ in range(10):state(s);s.ctx.buffs.controls('subject')
 assert s.checkpoint()==before

def test_intrinsic_immunity_removed_and_added_sync_existing_control():
 p=fixture();p['entities'][0]['components']['selection_state']['abnormal_immunes']=[0];s=make(p);s.ctx.buffs.apply('subject','subject','buff/stun');assert s.ctx.buffs.controls('subject')['attack']
 s.ctx.set('subject',('selection_state','abnormal_immunes'),[]);assert not s.ctx.buffs.controls('subject')['attack']
 s.ctx.set('subject',('selection_state','abnormal_immunes'),[0]);assert s.ctx.buffs.controls('subject')['attack']

def test_inactive_mixed_periodic_and_event_reactions_are_suppressed_but_remove_callback_runs():
 p=fixture();p['entities'][0]['components']['resources']['credit']={'initial':0,'capacity':100};b=p['buffs'][3];b.update(interval_seconds=.1,duration_seconds=.4,effects=[{'op':'modify_resource','target':'source','resource':'credit','amount':1}],events=[{'event':'probe.credit','effects':[{'op':'modify_resource','resource':'credit','amount':10}]}],on_remove=[{'op':'emit','event':'probe.removed','payload':{'kept':True}}]);s=make(p)
 s.ctx.buffs.apply('subject','subject','buff/mixed');s.ctx.buffs.apply('subject','subject','buff/silence');s.ctx.emit('probe.credit',{'source':s.session.world.resolve('subject'),'target':s.session.world.resolve('subject')});assert s.ctx.resources.current('subject','credit')==0
 s.ctx.buffs.remove('subject','buff/mixed');assert len([e for e in s.session.events if e['type']=='probe.removed'])==1
 s.advance(14);assert s.ctx.resources.current('subject','credit')==0

def test_mixed_periodic_resumes_after_halfopen_silence_expiry():
 p=fixture();p['entities'][0]['components']['resources']['credit']={'initial':0,'capacity':100};p['buffs'][3].update(interval_seconds=.1,duration_seconds=.4,effects=[{'op':'modify_resource','target':'source','resource':'credit','amount':1}]);p['buffs'][2]['duration_seconds']=.2;s=make(p);s.ctx.buffs.apply('subject','subject','buff/silence');s.ctx.buffs.apply('subject','subject','buff/mixed');s.advance(5);assert s.ctx.resources.current('subject','credit')==0;s.advance(6);assert s.ctx.resources.current('subject','credit')==2

def test_real_rule_failure_on_intrinsic_state_change_rolls_back_all_state_and_guard():
 p=fixture();p['rules'][0]['implementation']['expression']='1 / 0 if 0 not in inputs.status.abnormal_immunes else True';p['entities'][0]['components']['selection_state']['abnormal_immunes']=[0];s=make(p);s.ctx.buffs.apply('subject','subject','buff/stun');before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.set('subject',('selection_state','abnormal_immunes'),[])
 assert s.checkpoint()==before and not s.ctx.buffs.applicability._busy

def test_periodic_first_effect_silences_before_second_effect_and_must_recheck_active():
 p=fixture();p['entities'][0]['components']['resources']['credit']={'initial':0,'capacity':100};p['buffs'][3].update(interval_seconds=.1,effects=[{'op':'apply_buff','buff':'buff/silence'},{'op':'modify_resource','target':'source','resource':'credit','amount':1}]);s=make(p);s.ctx.buffs.apply('subject','subject','buff/mixed');s.advance(4)
 assert s.ctx.resources.current('subject','credit')==0

def test_movement_damage_old_active_tail_settles_and_inactive_distance_is_not_replayed():
 import json
 from copy import deepcopy
 p=fixture();weedy=json.loads((ROOT/'packages/campaign/skills.weedy.json').read_bytes());rule=deepcopy(next(r for r in weedy['rules'] if r['id']=='rule/campaign_weedy_distance_damage'));p['rules'].append(rule);p['buffs'][3]['movement_damage']={'effect':{'op':'damage','damage_type':'true','parameters':{'value':10,'per_distance':1},'rules':{'damage.pipeline':rule['id']}}};p['buffs'][3]['interval_seconds']=1;s=make(p);s.ctx.buffs.apply('subject','subject','buff/mixed');ref=s.session.world.resolve('subject')
 s.ctx.movement.displace(ref,ref,{'position':{'row':0,'col':1}},None);s.ctx.buffs.apply(ref,ref,'buff/silence');assert s.ctx.resources.current(ref,'hp')==990
 s.ctx.movement.displace(ref,ref,{'position':{'row':0,'col':2}},None);s.ctx.buffs.remove(ref,'buff/silence');assert s.ctx.resources.current(ref,'hp')==990
 s.ctx.movement.displace(ref,ref,{'position':{'row':0,'col':3}},None);s.ctx.buffs.remove(ref,'buff/mixed');assert s.ctx.resources.current(ref,'hp')==980

def test_immunity_expiry_interrupts_an_existing_cast_once_control_reactivates():
 p=fixture();p['entities'][0]['components']['abilities'].append('ability/waiter');p['abilities'].append({'id':'ability/waiter','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at_seconds':.5,'effects':[{'op':'emit','event':'probe.waiter_finished'}]}]});s=make(p)
 for t,a in [(0,'immune'),(1,'stun'),(2,'waiter')]:s.submit({'action':'skill','source':'subject','ability':'ability/'+a},at=t)
 s.advance(20);assert not any(e['type']=='probe.waiter_finished' for e in s.session.events);assert any(e['type']=='ability.interrupted' and e['payload'].get('reason')=='buff_control_reactivated' for e in s.session.events)

def test_immediate_first_effect_silences_and_cancels_later_buff_contribution():
 p=fixture();p['entities'][0]['components']['resources']['credit']={'initial':0,'capacity':100};p['buffs'][3]['effects']=[{'op':'apply_buff','buff':'buff/silence'},{'op':'modify_resource','resource':'credit','amount':1}];s=make(p);s.ctx.buffs.apply('subject','subject','buff/mixed');assert s.ctx.resources.current('subject','credit')==0

def test_inactive_mixed_damage_hook_stops_without_losing_underlying_buff():
 p=fixture();p['rules'].append({'id':'rule/double','kind':'rule','contract':'damage.request','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'effect':{'op':'damage','damage_type':inputs.effect.damage_type,'attack':inputs.effect.attack,'defense':inputs.effect.defense,'resistance':inputs.effect.resistance,'scale':inputs.effect.scale*2,'additions':inputs.effect.additions},'effects':[]}"}],'output':'nodes.result'}});p['buffs'][3]['damage_hooks']=[{'phase':'before','rule':'rule/double'}];s=make(p);ref=s.session.world.resolve('subject');s.ctx.buffs.apply(ref,ref,'buff/mixed');s.ctx.effects.execute(ref,[ref],{'op':'damage','damage_type':'physical'});assert s.ctx.resources.current(ref,'hp')==760
 s.ctx.buffs.apply(ref,ref,'buff/silence');s.ctx.effects.execute(ref,[ref],{'op':'damage','damage_type':'physical'});assert s.ctx.resources.current(ref,'hp')==660 and len(s.ctx.get(ref,('buffs','instances')))==2
