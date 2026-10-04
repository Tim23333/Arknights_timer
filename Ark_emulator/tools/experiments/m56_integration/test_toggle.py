import json,hashlib
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]
def fixture():
 enemy={'id':'unit/arbitrary_hidden','kind':'entity','tags':['enemy'],'rules':{'targeting.availability':'rule/availability'},'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':100,'def':0,'block_cost':1,'move_speed':1,'attack_interval':2}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'selection_state':{'side':1,'abnormal_flags':[]},'lifecycle':{'policy':'policy/ark_lifecycle'},'buffs':{'initial':['buff/controller']},'abilities':['ability/pulse','ability/move']}}
 hero={'id':'unit/hero','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':100,'def':0,'block_count':1}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'selection_state':{'side':0},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'abilities':['ability/probe']}}
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[enemy,hero],'buffs':[{'id':'buff/controller','kind':'buff','toggle':{'rule':'rule/hold','buff':'buff/hidden','initial_enabled':True,'restore_delay_seconds':3,'events':[{'event':'attack.accepted','owner_role':'source'}]}},{'id':'buff/hidden','kind':'buff','stacking':{'mode':'independent'},'selection_flags':{'abnormal_flags':[9]}},{'id':'buff/immunity','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_immunes':[9]}}], 'rules':[{'id':'rule/hold','kind':'rule','contract':'passive.toggle','implementation':{'type':'expression','expression':'inputs.blocked_by != None and inputs.blocker_active'}},{'id':'rule/availability','kind':'rule','contract':'targeting.availability','parameters':{'flag':9},'implementation':{'type':'expression','expression':"params.flag not in inputs.selection_states.candidate.abnormal_flags or inputs.selection_states.source.side == inputs.selection_states.candidate.side or ('parameters' in inputs.selector and 'visibility_bypass_flags' in inputs.selector.parameters and params.flag in inputs.selector.parameters.visibility_bypass_flags)"}}], 'selectors':[{'id':'selector/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}], 'abilities':[{'id':'ability/pulse','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'emit','event':'attack.accepted'}]},'timeline':[]},{'id':'ability/move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':4}}]},'timeline':[]},{'id':'ability/probe','kind':'ability','selector':'selector/enemy','activation':{'mode':'manual','parameters':{'requires_targets':True}},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}], 'scenarioDraft':{'id':'scene/toggle','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':6},'initialEntities':[{'definition':enemy['id'],'instanceAlias':'enemy','position':{'row':0,'col':0}},{'definition':hero['id'],'instanceAlias':'hero','position':{'row':2,'col':0}}]}}
def make(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':4901,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=4901)
def flags(s):return s.ctx.spatial.selection_state('enemy',{'side':1,'motion':1,'category':1,'profession':0,'unit_type':1,'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[]})
def test_initial9_not_camouflage_and_pulse_restores_exact91_public_disk_replay(tmp_path):
 s=make(fixture());assert flags(s)['abnormal_flags']==[9] and flags(s)['camouflage'] is False
 before=len(s.session.events);rng=s.session.random.snapshot();assert s.ctx.spatial.eligible('hero','selector/enemy')==[];assert len(s.session.events)==before and s.session.random.snapshot()==rng
 s.submit({'action':'skill','source':'enemy','ability':'ability/pulse'},at=1);s.submit({'action':'skill','source':'hero','ability':'ability/probe'},at=90);s.submit({'action':'skill','source':'hero','ability':'ability/probe'},at=91);s.advance(45)
 assert 9 not in flags(s)['abnormal_flags'];pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(49);r.advance(49)
 assert flags(s)['abnormal_flags']==[9] and s.ctx.resources.current('enemy','hp')==900
 rejected=[e for e in s.session.events if e['type']=='command.rejected'];assert len(rejected)==1 and rejected[0]['time']==91
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_continuous_block_disables_without_attack_release_restores92(tmp_path):
 p=fixture();p['buffs'].append({'id':'buff/still','kind':'buff','control':{'move':False}});p['entities'][0]['components']['buffs']['initial'].append('buff/still');p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':5},'checkpoints':[]}
 p['scenarioDraft']['initialEntities'][1]['position']={'row':0,'col':0}
 s=make(p);s.submit({'action':'skill','source':'enemy','ability':'ability/move'},at=2);s.advance(2);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('hero') and 9 not in flags(s)['abnormal_flags']
 s.advance(1);assert s.ctx.spatial.blocked_by('enemy') is None and 9 not in flags(s)['abnormal_flags']
 s.advance(89);assert 9 not in flags(s)['abnormal_flags'];h=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',h));s.advance(1);r.advance(1);assert flags(s)['abnormal_flags']==[9] and s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def reveal_setup(p):
 p['selectors'].append({'id':'selector/reveal','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'parameters':{'visibility_bypass_flags':[9]},'limit':1})
 p['abilities'].append({'id':'ability/reveal','kind':'ability','selector':'selector/reveal','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/immunity'}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/reveal');return p

def test_live_immunity9_keeps_underlying_flag_and_two_sources_half_open(tmp_path):
 p=reveal_setup(fixture());p['scenarioDraft']['initialEntities'].append({'definition':'unit/hero','instanceAlias':'hero2','position':{'row':2,'col':1}});s=make(p)
 s.submit({'action':'skill','source':'hero','ability':'ability/reveal'},at=2);s.submit({'action':'skill','source':'hero2','ability':'ability/reveal'},at=3);s.advance(4)
 assert 9 not in flags(s)['abnormal_flags'] and any(i['definition']=='buff/hidden' for i in s.ctx.get('enemy',('buffs','instances')))
 s.advance(28);assert 9 not in flags(s)['abnormal_flags'];h=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',h));s.advance(1);r.advance(1)
 assert flags(s)['abnormal_flags']==[9] and s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_targeting_area_and_selector_agree_with_9_immunity(tmp_path):
 p=reveal_setup(fixture());p['abilities'].append({'id':'ability/area','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'area','target':'source','center_position':{'row':0,'col':0},'radius':1,'filters':[{'tag':'enemy'}],'effects':[{'op':'damage','damage_type':'true','scale':1}]}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/area');s=make(p)
 s.submit({'action':'skill','source':'hero','ability':'ability/area'},at=0);s.submit({'action':'skill','source':'hero','ability':'ability/reveal'},at=2);s.submit({'action':'skill','source':'hero','ability':'ability/area'},at=3);s.advance(5)
 assert s.ctx.resources.current('enemy','hp')==900 and [e['time'] for e in s.session.events if e['type']=='damage.accepted']==[3]
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_pulse_rule_failure_is_atomic_and_guards_restore():
 p=fixture();p['rules'][0]['implementation']['expression']='False if inputs.state.last_pulse == None else 1 / 0';s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('enemy',['enemy'],{'op':'emit','event':'attack.accepted'})
 assert s.checkpoint()==before and not s.ctx.buffs.toggles._busy and not s.ctx.buffs.toggles._requested and s.ctx.buffs.toggles._removing==set()
 with pytest.raises(Exception):s.ctx.effects.execute('enemy',['enemy'],{'op':'emit','event':'attack.accepted'})
 assert s.checkpoint()==before

@pytest.mark.parametrize('change',[lambda s:s.update(foo=1),lambda s:s.update(initial_enabled=1),lambda s:s.update(restore_delay_seconds=True),lambda s:s.update(restore_delay_seconds=-1),lambda s:s.update(rule='rule/availability'),lambda s:s['events'][0].update(owner_role='owner')])
def test_toggle_spec_strict_preflight(change):
 p=fixture();change(p['buffs'][0]['toggle'])
 with pytest.raises(ValueError):Compiler().compile(p)

def test_pulse_reset_preserves90_delay_from_last_attack_not_first(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'enemy','ability':'ability/pulse'},at=1);s.submit({'action':'skill','source':'enemy','ability':'ability/pulse'},at=10);s.submit({'action':'skill','source':'hero','ability':'ability/probe'},at=99);s.submit({'action':'skill','source':'hero','ability':'ability/probe'},at=100);s.advance(102)
 assert s.ctx.resources.current('enemy','hp')==900 and [e['time'] for e in s.session.events if e['type']=='command.rejected']==[100]
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()

@pytest.mark.parametrize('mode',['remove','expired','dead','withdrawn'])
def test_parent_lifecycle_owns_child_without_reapplication(mode,tmp_path):
 p=fixture();p['selectors'].append({'id':'selector/management','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'parameters':{'visibility_bypass_flags':[9]},'limit':1})
 effect={'op':'remove_buff','buff':'buff/controller'} if mode=='remove' else {'op':'retire','parameters':{'reason':mode}}
 if mode=='expired':p['buffs'][0]['duration_seconds']=2/30
 else:
  p['abilities'].append({'id':'ability/cleanup','kind':'ability','selector':'selector/management','activation':{'mode':'manual','on_start':[effect]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/cleanup')
 s=make(p)
 if mode!='expired':s.submit({'action':'skill','source':'hero','ability':'ability/cleanup'},at=2)
 s.advance(5);assert not any(i['definition']=='buff/hidden' for i in s.ctx.get('enemy',('buffs','instances')))
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_legal_child_on_remove_retire_owner_stabilizes_and_no_orphan(tmp_path):
 p=fixture();p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}];s=make(p);s.submit({'action':'skill','source':'enemy','ability':'ability/pulse'},at=1);s.advance(3)
 assert not s.ctx.alive('enemy') and not any(i['definition']=='buff/hidden' for i in s.ctx.get('enemy',('buffs','instances')))
 assert not s.ctx.buffs.toggles._busy and s.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_nonconvergent_child_modifiers_hit_budget_and_full_apply_rollback():
 p=fixture();p['entities'][0]['components']['buffs']['initial']=[];p['entities'][0]['dependencies']=['buff/controller'];p['buffs'][1]['modifiers']=[{'attribute':'def','layer':'flat','value':1}];p['buffs'][0]['toggle']['restore_delay_seconds']=0;p['rules'][0]['implementation']['expression']='inputs.owner.components.attributes.modifiers != []'
 s=make(p);s.session.reaction_budget=6;before=s.checkpoint()
 with pytest.raises(ValueError,match='budget'):s.ctx.buffs.apply('enemy','enemy','buff/controller')
 assert s.checkpoint()==before and not s.ctx.buffs.toggles._busy and s.ctx.buffs.toggles._removing==set()

def test_immunity9_never_masks17_and_force_camo_never_bypasses9():
 p=fixture();p['entities'][0]['dependencies']=['buff/immunity'];p['buffs'].append({'id':'buff/camouflage','kind':'buff','selection_flags':{'abnormal_flags':[17]}});p['entities'][0]['components']['buffs']['initial'].append('buff/camouflage')
 from ark_sim.domains.selection import DEFAULT_STATE
 cfg={'_targetSide':2,'_targetMotion':3,'_targetCategory':1,'_ignoreTargetFree':0,'_onlyIgnoreSomeOfTargetFreeCase':0,'_excludeSomeAbnormalFlags':0,'_needProfessionMask':0,'_ignoreAllyTargetFree':0,'_ignoreHealFree':0,'_ignoreMotionMode':0,'_forceIgnoreCamouflage':1,'_checkUnitType':0}
 p['rules'].append({'id':'rule/base_eligibility','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}})
 p['selectors'][0]['eligibility']={'rule':'rule/base_eligibility','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':{**deepcopy(DEFAULT_STATE),'motion':1,'category':1}}}
 s=make(p);assert s.ctx.spatial.eligible('hero','selector/enemy')==[]
 s.ctx.buffs.apply('hero','enemy','buff/immunity');state=flags(s);assert state['abnormal_flags']==[17] and state['camouflage'] is True
 assert s.ctx.spatial.eligible('hero','selector/enemy')==[s.session.world.resolve('enemy')]

def test_multiple_toggle_sources_retire_one_preserves_other_child():
 p=fixture();p['entities'][0]['components']['buffs']['initial']=[];p['entities'][0]['dependencies']=['buff/controller'];p['scenarioDraft']['initialEntities'].append({'definition':'unit/hero','instanceAlias':'hero2','position':{'row':2,'col':1}});s=make(p)
 s.ctx.buffs.apply('hero','enemy','buff/controller');s.ctx.buffs.apply('hero2','enemy','buff/controller')
 children=lambda:[x for x in s.ctx.get('enemy',('buffs','instances')) if x['definition']=='buff/hidden']
 assert len(children())==2;s.ctx.lifecycle.retire('hero','withdrawn');assert len(children())==1 and children()[0]['source']==s.session.world.resolve('hero2') and flags(s)['abnormal_flags']==[9]
