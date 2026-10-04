"""Opt-in decisions must actually stop travel/casts; eligible reads are pure."""
from pathlib import Path
import sys
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m24_enemy_fsm_candidate'
sys.path.insert(0,str(RUNTIME))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
def fixture():
 return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[
  {'id':'unit/enemy','kind':'entity','tags':['enemy','ground'],'components':{'attributes':{'base':{'atk':20,'def':0,'mres':0,'max_hp':100,'move_speed':3,'attack_interval':1,'attack_speed_ratio':1,'block_cost':1}},
   'resources':{'hp':{'initial':100,'capacity':100}},'spatial':{},'abilities':['ability/normal'],'behavior':{'machine':'behavior/decision'}}},
  {'id':'unit/target','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'atk':0,'def':0,'mres':0,'max_hp':100}},
   'resources':{'hp':{'initial':100,'capacity':100}},'spatial':{},'abilities':['ability/escape']}}],
  'abilities':[{'id':'ability/normal','kind':'ability','activation':{'mode':'automatic_attack'},'selector':'selector/enemies','duration_seconds':.3,
   'timeline':[{'at_seconds':.2,'effect':{'op':'damage','damage_type':'physical','scale':1}}]},
   {'id':'ability/escape','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':5}}]},'timeline':[]}],
  'selectors':[{'id':'selector/enemies','kind':'selector','region':{'type':'radius','radius':1},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}],
  'behaviors':[{'id':'behavior/decision','kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
   'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':'selector/enemies'}],
      'cast_groups':[{'key':'normal','abilities':['ability/normal']}],'parameters':{'target_key':'normal','stop_on_target':True,'stop_cast_groups':['normal']}}]}}],
  'scenarioDraft':{'id':'scenario/decision','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':6},'initialEntities':[
    {'definition':'unit/enemy','instanceAlias':'enemy','position':{'row':0,'col':0},'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':5},'checkpoints':[]}},
    {'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':1}}],'waves':[],'objectives':{}}}
def make(p):return Engine.create(Compiler().compile(p),seed=24)
def cp(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_has_target_stops_route_actual_cast_no_new_attack_while_casting():
 s=make(fixture());s.advance(8)
 assert s.ctx.get('enemy',('spatial','position'))=={'row':0,'col':0} and s.ctx.resources.current('target','hp')==80
 assert len([e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==2])==1
 s.submit({'action':'skill','source':'target','ability':'ability/escape'},at=8);s.advance(4)
 assert s.ctx.get('enemy',('spatial','position'))['col']>0;cp(s)
def test_no_target_moves_then_eligibility_read_has_no_events_rng_state_mutation():
 p=fixture();p['scenarioDraft']['initialEntities'][1]['position']['col']=5;s=make(p);before=s.checkpoint()
 for _ in range(3):assert s.ctx.spatial.eligible('enemy','selector/enemies')==[]
 assert s.checkpoint()==before;s.advance(3);assert abs(s.ctx.get('enemy',('spatial','position'))['col']-.3)<1e-8;cp(s)
@pytest.mark.parametrize('bad',[lambda p:p['behaviors'][0]['decision'].update(mode_resource='missing'),
 lambda p:p['behaviors'][0]['decision']['profiles'][0]['cast_groups'][0]['abilities'].append('ability/escape'),
 lambda p:p['behaviors'][0]['decision']['profiles'][0]['selectors'][0].update(selector='ability/normal'),
 lambda p:p['behaviors'][0]['decision']['profiles'].append(deepcopy(p['behaviors'][0]['decision']['profiles'][0]))])
def test_reference_mode_and_ownership_failfast(bad):
 p=fixture();bad(p)
 with pytest.raises(ValueError):Compiler().compile(p)
def test_absent_opt_in_keeps_legacy_default_true():
 p=fixture();p['behaviors'][0].pop('decision');s=make(p);s.advance(3)
 assert abs(s.ctx.get('enemy',('spatial','position'))['col']-.3)<1e-8
 assert s.ctx.get('enemy',('runtime','behavior_decision'))=={'move':True,'attack':True}

def test_same_frame_automatic_skill_stops_movement_without_normal_target():
 p=fixture();p['scenarioDraft']['initialEntities'][1]['position']['col']=5
 p['entities'][0]['components']['abilities'].append('ability/skill')
 p['abilities'].append({'id':'ability/skill','kind':'ability','activation':{'mode':'manual','parameters':{'auto_when_ready':True,'allow_no_targets':True}},
   'duration_seconds':.3,'cooldown_seconds':10,'timeline':[]})
 p['behaviors'][0]['decision']['profiles'][0]['cast_groups'].append({'key':'skill','abilities':['ability/skill']})
 p['behaviors'][0]['decision']['profiles'][0]['parameters']['stop_cast_groups'].append('skill')
 s=make(p);s.advance(1)
 assert s.ctx.get('enemy',('spatial','position'))=={'row':0,'col':0}
 assert s.ctx.get('enemy',('runtime','behavior_decision'))=={'move':False,'attack':False};cp(s)

def custom_geometry(inputs,params,context):
 return [e['id'] for e in inputs['candidates'] if e['components']['spatial']['position']['col']==params['column']]
custom_geometry.version='pure-custom-column-selector-v1'
def test_custom_provider_and_field_semantics_shared_without_sort_rng_emit():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 p=fixture();p['selectors'][0].update(provider='peer.column',parameters={'column':1},ordering='random')
 p['selectors'][0]['parameters']['random_stream']='imp'
 p['selectors'][0]['filters'].append({'field':{'scope':'runtime','path':['components','resources','hp','current'],'equals':100}})
 providers={**BUILTIN_PROVIDERS,'peer.column':custom_geometry};s=Engine.create(Compiler(providers=providers).compile(p),seed=24,providers=providers)
 cp0=s.checkpoint();assert s.ctx.spatial.eligible('enemy','selector/enemies')==[3] and cp0==s.checkpoint()
 assert s.ctx.spatial.select('enemy','selector/enemies')==[3]
 assert cp0['kernel']['random']!=s.checkpoint()['kernel']['random'] # RNG is only consumed by actual select

@pytest.mark.parametrize('output',["{'move':1,'attack':False}","{'move':False,'attack':False,'ignored':True}"])
def test_decision_type_or_unknown_output_rejected_atomic(output):
 p=fixture();p['rules']=[{'id':'rule/bad','kind':'calculation_rule','contract':'behavior.decision','implementation':{'type':'expression','expression':output}}]
 p['behaviors'][0]['decision']['rule']='rule/bad';s=make(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.behavior.plan('enemy')
 # Evaluation itself is observable; wrapping a failed plan in actual action atomicity rolls back.
 s=make(p);before=s.checkpoint()
 with pytest.raises(ValueError):
  with s.session.atomic():s.ctx.behavior.plan('enemy')
 assert s.checkpoint()==before

@pytest.mark.parametrize('value',[.5,True,2])
def test_runtime_mode_nonintegral_bool_or_missing_profile_rejected(value):
 p=fixture();p['entities'][0]['components']['resources']['mode']={'initial':value,'capacity':10}
 config=p['behaviors'][0]['decision'];config.pop('default_mode');config['mode_resource']='mode'
 with pytest.raises(ValueError):
  s=make(p);s.ctx.behavior.plan('enemy')

def test_limit_zero_means_no_ready_target_dynamic_limit_requires_contract():
 p=fixture();p['selectors'][0]['limit']=0;s=make(p);s.advance(2)
 assert s.ctx.get('enemy',('spatial','position'))['col']>0 and not [e for e in s.session.events if e['type']=='ability.started']
 p=fixture();p['selectors'][0]['limit_attribute']='max_targets'
 with pytest.raises(ValueError):Compiler().compile(p)

def test_blocked_combat_input_target_ignores_unblocked_neighbor():
 p=fixture();cfg=p['behaviors'][0]['decision']['profiles'][0];cfg['parameters']['blocked_target']=True
 p['selectors'][0]['region']={'type':'all','blocked_only':True}
 target=p['entities'][1]['components'];target['attributes']['base']['block_count']=1
 target['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}
 p['scenarioDraft']['initialEntities'][0]['position']['col']=1;p['scenarioDraft']['initialEntities'][0]['route']['startPosition']['col']=1
 p['entities'].append({'id':'unit/neighbor','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100,'def':0,'mres':0}},
   'resources':{'hp':{'initial':100,'capacity':100}},'spatial':{}}})
 p['scenarioDraft']['initialEntities'].append({'definition':'unit/neighbor','instanceAlias':'neighbor','position':{'row':0,'col':0}})
 s=make(p);s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('target')
 s.advance(8);assert s.ctx.resources.current('target','hp')==80 and s.ctx.resources.current('neighbor','hp')==100
 # Initialization setup is API-only; checkpoint restore remains exact, no command replay claim for setup.
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()

def test_controls_and_ability_start_failure_refresh_rollback():
 p=fixture();p['buffs']=[{'id':'buff/stop','kind':'buff','duration_seconds':.1,'control':{'move':False,'attack':False,'abilities':False}}]
 p['entities'][0]['components']['buffs']={'initial':['buff/stop']};s=make(p);s.advance(3)
 assert s.ctx.get('enemy',('spatial','position'))=={'row':0,'col':0} and not [e for e in s.session.events if e['type']=='ability.started']
 s.advance(1);assert [e for e in s.session.events if e['type']=='ability.started'];cp(s)
 p=fixture();p['rules']=[{'id':'rule/fail_on_cast','kind':'calculation_rule','contract':'behavior.decision',
  'implementation':{'type':'expression','expression':"{'move':False,'attack':True} if not inputs.casts else 1/0"}}]
 p['behaviors'][0]['decision']['rule']='rule/fail_on_cast';s=make(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('enemy','ability/normal',automatic=True)
 assert s.checkpoint()==before
