from pathlib import Path
from copy import deepcopy
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
    profile={'type':'contact_lifecycle','rule':'rule/contact','parameters':{},'normal_path_passable':False,
             'forced_contact_passable':True,'appearance_contact_passable':True,'health_policy':'zero','death_reason':'dead','reevaluate_each_tick':False}
    unit={'id':'unit/enemy','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':100,'move_speed':3,'mass_level':0}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/move','ability/fly','ability/ground','ability/push']}}
    abilities=[{'id':'ability/move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':2}}]},'timeline':[]},
               *[{'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[{'op':'set_motion_mode','target':'source','value':mode}]},'timeline':[]} for name,mode in [('fly',1),('ground',0)]]]
    abilities.append({'id':'ability/push','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'push','target':'source','force':3,'distance':3,'direction':'source_facing','rules':{'movement.displacement':'rule/push'}}]},'timeline':[]})
    return {'manifest':{'requires':['preset/ark_standard']},'entities':[unit], 'abilities':abilities,
        'rules':[{'id':'rule/contact','kind':'rule','contract':'tile.contact','implementation':{'type':'expression','expression':"inputs.motion_mode == 0 and inputs.ready and 'enemy' in inputs.entity.tags"}},
                 {'id':'rule/push','kind':'rule','contract':'movement.displacement','implementation':{'type':'expression','expression':"{'distance': inputs.distance, 'duration': 0.1}"}}],
        'scenarioDraft':{'id':'scene/contact','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':4,'tiles':[
            {'tileKey':'arbitrary_pit' if i==1 else 'tile_floor','passableMask':3,'buildableType':0} for i in range(8)],
            'tile_mechanics':{'arbitrary_pit':profile}},'initialEntities':[{'definition':'unit/enemy','instanceAlias':'a','position':{'row':0,'col':0}}]}}

def sim(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=4101)
def push(s,distance=3):s.ctx.effects.execute('a',['a'],{'op':'push','force':3,'distance':distance,'direction':'source_facing','rules':{'movement.displacement':'rule/push'}})
def deaths(s):return [e for e in s.session.events if e['type']=='tile.contact_death']

def test_ground_path_detours_without_rewriting_native_mask():
    s=sim();g=s.ctx.spatial.grid
    assert g.tile(0,1)['passableMask']==3 and not g.passable(0,1)
    path=g.path({'row':0,'col':0},{'row':0,'col':3})
    assert {'row':0,'col':1} not in path and {'row':1,'col':1} in path

def test_push_enters_pit_stops_at_first_contact_no_tunnel_no_leak_damage():
    s=sim();push(s);s.advance(5)
    assert s.ctx.resources.current('a','hp')==0 and not s.ctx.alive('a')
    assert s.ctx.state()['kills']==1 and s.ctx.state()['leaks']==0 and s.ctx.state()['damage_dealt']==0
    assert s.ctx.get('a',('spatial','position'))['col']==pytest.approx(.5,abs=1e-8)
    assert not s.ctx.get('a',('spatial','forced_motion')) and len(deaths(s))==1
    assert not any(e['type'] in ('damage.accepted','combat.kill') for e in s.session.events)

def test_fly_ignores_pit_and_public_ground_change_falls_once():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1};p['scenarioDraft']['initialEntities'][0]['components']={'spatial':{'motion_mode':1}}
    s=sim(p);assert s.ctx.alive('a')
    s.submit({'action':'skill','source':'a','ability':'ability/ground'},at=3);s.advance(5)
    assert not s.ctx.alive('a') and len(deaths(s))==1 and s.ctx.get('a',('runtime','death_cause'))['kind']=='motion_changed'

def test_born_immediate_enemy_falls_player_and_field_are_excluded():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1}
    s=sim(p);assert not s.ctx.alive('a') and s.ctx.state()['kills']==1
    p['entities'][0]['tags']=['player'];s=sim(p);assert s.ctx.alive('a')

def test_birth_buff_half_open_finish_45_triggers_fall():
    p=fixture();p['buffs']=[{'id':'buff/born','kind':'buff','duration_seconds':1.5,'contact_flags':{'defer_fall':True}}]
    p['entities'][0]['components']['buffs']={'initial':['buff/born']};p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1}
    s=sim(p);s.advance(45);assert s.ctx.alive('a')
    s.advance(1);assert not s.ctx.alive('a') and deaths(s)[0]['time']==45

def test_normal_wall_still_clips_forced_motion():
    p=fixture();p['scenarioDraft']['map']['tiles'][1]={'tileKey':'tile_wall','passableMask':0,'buildableType':0}
    s=sim(p);push(s);s.advance(5);assert s.ctx.alive('a') and s.ctx.get('a',('spatial','position'))['col']<.5

def test_boundary_negative_half_up_and_no_false_adjacent_fall():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':.499999}
    s=sim(p);assert s.ctx.alive('a')
    s.ctx.movement.displace('a','a',{'position':{'row':0,'col':.5}},None);assert not s.ctx.alive('a')
    p['scenarioDraft']['initialEntities'][0]['position']={'row':-.5,'col':0};assert sim(p).ctx.alive('a')

def test_custom_rule_can_deny_special_death_without_guessing_revive_body():
    p=fixture();p['rules'][0]['implementation']['expression']='False';p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1}
    s=sim(p);s.advance(3);assert s.ctx.alive('a') and s.ctx.state()['kills']==0

@pytest.mark.parametrize('change',[lambda p:p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit'].update(rule='ability/move'),
    lambda p:p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit'].pop('health_policy'),
    lambda p:p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit'].update(forced_contact_passable=1),
    lambda p:p['abilities'][1]['activation']['on_start'][0].update(value=True)])
def test_declared_profiles_and_contracts_strict(change):
    p=fixture();change(p)
    with pytest.raises(ValueError):Compiler().compile(p)

def test_real_public_move_cp_disk_and_command_replay(tmp_path):
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=4114)
    s.submit({'action':'skill','source':'a','ability':'ability/move'},at=3);s.advance(2)
    path=tmp_path/'ordered.json';receipt=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,receipt));s.advance(5);r.advance(5)
    assert not s.ctx.alive('a') and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

def test_throwing_contact_rule_rolls_back_actual_move_and_guard():
    p=fixture();p['rules'][0]['implementation']['expression']='1 / 0 > 0';s=sim(p);before=s.checkpoint()
    with pytest.raises(Exception):s.ctx.movement.displace('a','a',{'position':{'row':0,'col':2}},None)
    assert s.checkpoint()==before and s.ctx.tile_contacts._settling==set()

def test_actual_route_motion_crosses_declared_contact_only_when_profile_allows():
    p=fixture();p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit']['normal_path_passable']=True
    p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}
    s=sim(p);s.advance(20);assert not s.ctx.alive('a') and s.ctx.state()['kills']==1 and s.ctx.state()['leaks']==0

def test_ground_appear_contact_dies_without_posthumous_exit():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},
        'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},
        'checkpoints':[{'type':5},{'type':1,'time':.1},{'type':6,'position':{'row':0,'col':1}}]}
    s=sim(p);s.advance(10);assert not s.ctx.alive('a') and s.ctx.state()['leaks']==0 and deaths(s)[0]['payload']['cause']=='appear'

def test_live_flying_push_crosses_hole_not_just_flying_birth():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['components']={'spatial':{'motion_mode':1}}
    s=sim(p);push(s);s.advance(5);assert s.ctx.alive('a') and s.ctx.get('a',('spatial','position'))['col']==pytest.approx(3)

def test_forced_entry_policy_false_clips_without_death():
    p=fixture();p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit']['forced_contact_passable']=False
    s=sim(p);push(s);s.advance(5);assert s.ctx.alive('a') and s.ctx.get('a',('spatial','position'))['col']<.5

def test_high_speed_negative_direction_first_pit_entry_does_not_skip():
    p=fixture();p['scenarioDraft']['initialEntities'][0].update(position={'row':0,'col':3},facing='left')
    s=sim(p);push(s);s.advance(5);assert not s.ctx.alive('a') and s.ctx.get('a',('spatial','position'))['col']==pytest.approx(1.5,abs=1e-8)

def test_health_preserve_choice_is_not_fake_damage_and_owner_retains():
    p=fixture();p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit']['health_policy']='preserve'
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/enemy','instanceAlias':'owner','position':{'row':1,'col':0}})
    s=sim(p);child=s.ctx.lifecycle.create('unit/enemy',{'row':0,'col':1},owner='owner',alias='child')
    assert not s.ctx.alive(child) and s.ctx.alive('owner') and s.ctx.resources.current(child,'hp')==100
    assert s.ctx.get(child,('runtime','death_cause'))['owner']==s.session.world.resolve('owner')

def test_environment_cause_canonical_push_source_separate_from_kill_credit():
    s=sim();push(s);s.advance(3);cause=s.ctx.get('a',('runtime','death_cause'))
    assert cause['source']==s.session.world.resolve('a') and cause['type']=='environment_contact'
    assert deaths(s)[0]['payload']['caster_kill_credit'] is False

def test_born_dead_managed_membership_does_not_leak_or_count_controls_as_enemy():
    p=fixture();p['scenarioDraft']['initialEntities']=[]
    spawn=lambda alias,col:{'kind':'spawn','count':1,'delay_seconds':0,'interval_seconds':0,'managed':True,'blocks_wave':True,'blocks_fragment':True,
        'spawn':{'definition':'unit/enemy','instanceAlias':alias,'position':{'row':0,'col':col}}}
    p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[
        {'pre_delay_seconds':0,'post_delay_seconds':0,'max_wait_seconds':-1,'fragments':[{'pre_delay_seconds':0,'actions':[spawn('pit',1)]}]},
        {'pre_delay_seconds':.1,'post_delay_seconds':0,'max_wait_seconds':-1,'fragments':[{'pre_delay_seconds':0,'actions':[spawn('safe',2)]}]}]}
    s=sim(p);s.advance(5);assert not s.ctx.alive('pit') and s.ctx.alive('safe')
    assert s.ctx.state()['pending_waves']==0 and s.ctx.state()['kills']==1 and s.ctx.state()['leaks']==0
    members=s.ctx.state()['timeline']['members'];assert set(members)=={str(s.session.world.resolve('safe'))}

def test_death_settlement_failure_restores_hp_rng_jobs_and_contact_guard():
    s=sim();before=s.checkpoint();original=s.ctx.lifecycle.retire
    def fail(ref,reason):
        original(ref,reason);s.session.random.sample('imp');s.session.schedule('domain.entity.expire',{'target':ref},55);raise RuntimeError('actual death settlement failure')
    s.ctx.lifecycle.retire=fail
    with pytest.raises(RuntimeError):s.ctx.movement.displace('a','a',{'position':{'row':0,'col':2}},None)
    assert s.checkpoint()==before and s.ctx.tile_contacts._settling==set()
    s.ctx.lifecycle.retire=original;s.ctx.movement.displace('a','a',{'position':{'row':0,'col':2}},None);assert not s.ctx.alive('a')

def test_public_push_durable_midflight_replay(tmp_path):
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=4123)
    s.submit({'action':'skill','source':'a','ability':'ability/push'},at=3);s.advance(4)
    path=tmp_path/'push.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(5);r.advance(5)
    assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot() and not s.ctx.alive('a')

@pytest.mark.parametrize('mode',[True,2,'FLY',None])
def test_invalid_initial_override_mode_rejected_before_create(mode):
    p=fixture();p['scenarioDraft']['initialEntities'][0]['components']={'spatial':{'motion_mode':mode}}
    with pytest.raises(ValueError):Compiler().compile(p)

def test_flying_born_protection_and_wave_pending_cannot_skip_all_births():
    p=fixture();p['entities'][0]['components']['spatial']['motion_mode']=1
    p['scenarioDraft']['waves']=[{'at':3,'definition':'unit/enemy','instanceAlias':'flyborn','position':{'row':0,'col':1}}]
    s=sim(p);s.advance(4);assert s.ctx.alive('flyborn') and s.ctx.state()['pending_waves']==0 and s.ctx.state()['kills']==0

def test_real_profile_uses_actual_native_tile_without_patching_passable_source():
    import json
    v=json.loads((ROOT/'packages/campaign/chapter02_tiles/m41.hole.profile.json').read_bytes())
    p=fixture();raw=v['native_stage_cells']['02-09'][0]['raw'];assert raw['passableMask']=='ALL' or raw['passableMask']==3
    # Raw parser enum strings are normalized into masks, while preserving raw in source sidecar.
    p['scenarioDraft']['map']['tiles'][1]={'tileKey':'tile_hole','passableMask':3,'buildableType':0}
    p['scenarioDraft']['map']['tile_mechanics']=deepcopy(v['tile_mechanics']);p['rules'][0]=deepcopy(v['rules'][0])
    s=sim(p);push(s);s.advance(4);assert not s.ctx.alive('a') and s.ctx.spatial.grid.tile(0,1)['passableMask']==3

def test_false_rule_is_cached_but_explicit_periodic_policy_can_recheck_live_state():
    p=fixture();p['rules'][0]['implementation']['expression']='inputs.entity.components.resources.hp.current < 50'
    p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit']['reevaluate_each_tick']=True
    p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1};s=sim(p)
    assert s.ctx.alive('a');s.ctx.resources.adjust('a','hp',value=40);s.advance(1);assert not s.ctx.alive('a')

def test_undeclared_hole_still_rejects_instead_of_becoming_floor():
    p=fixture();p['scenarioDraft']['map']['tiles'][1]['tileKey']='tile_hole';p['scenarioDraft']['map'].pop('tile_mechanics')
    with pytest.raises(ValueError,match='unsupported tile mechanic'):Compiler().compile(p)

def test_static_field_owner_on_contact_tile_never_counts_as_falling_enemy():
    p=fixture();p['entities'].append({'id':'unit/static','kind':'entity','tags':['tile_field_owner'],'components':{
        'spatial':{},'attributes':{'base':{'max_hp':1}},'resources':{'hp':{'initial':1,'capacity':1}},'buffs':{'initial':['buff/static']}}})
    p['buffs']=[{'id':'buff/static','kind':'buff','aura':{'selector':'selector/static','buff':'buff/child'}},{'id':'buff/child','kind':'buff','stacking':{'mode':'independent'}}]
    p['selectors']=[{'id':'selector/static','kind':'selector','region':{'type':'grid_offsets','offsets':[[0,0]],'rotate_with_facing':False},'filters':[{'tag':'player'},{'state':'alive'}]}]
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/static','instanceAlias':'field','position':{'row':0,'col':1}})
    s=sim(p);s.advance(4);assert s.ctx.alive('field') and s.ctx.state()['kills']==0

def test_walking_safe_route_leaks_once_without_false_fall_or_spawn_loss():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}
    s=sim(p);s.advance(70);assert not s.ctx.alive('a') and s.ctx.state()['kills']==0 and s.ctx.state()['leaks']==1 and deaths(s)==[]

def test_ground_appearance_can_be_explicitly_forbidden_at_compile():
    p=fixture();p['scenarioDraft']['map']['tile_mechanics']['arbitrary_pit']['appearance_contact_passable']=False
    p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},
        'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},
        'checkpoints':[{'type':5},{'type':6,'position':{'row':0,'col':1}}]}
    with pytest.raises(ValueError,match='impassable'):Compiler().compile(p)

def test_custom_wrong_output_rejects_without_displacement_or_partial_death():
    p=fixture();p['rules'][0]['implementation']['expression']='1';s=sim(p);before=s.checkpoint()
    with pytest.raises(Exception):s.ctx.movement.displace('a','a',{'position':{'row':0,'col':2}},None)
    assert s.checkpoint()==before

def test_birth_boundary_restore_and_replay(tmp_path):
    p=fixture();p['buffs']=[{'id':'buff/born','kind':'buff','duration_seconds':1.5,'contact_flags':{'defer_fall':True}}]
    p['entities'][0]['components']['buffs']={'initial':['buff/born']};p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1}
    program=Compiler().compile(p);s=Engine.create(program,seed=4141);s.advance(44)
    path=tmp_path/'birth.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(3);r.advance(3)
    assert not s.ctx.alive('a') and deaths(s)[0]['time']==45 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
