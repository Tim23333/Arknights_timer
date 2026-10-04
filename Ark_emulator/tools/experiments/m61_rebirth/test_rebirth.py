import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m61_rebirth_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def fixture(delay=.1):
 boss={'id':'unit/boss','kind':'entity','tags':['enemy'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'atk':40,'def':0,'mres':0,'move_speed':1,'block_cost':1}},'resources':{'hp':{'initial':100,'capacity_attribute':'max_hp','role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':2},'buffs':{'initial':['buff/old']},'rebirth':{'resource':'hp','max_count':1,'delay_seconds':delay,'restore_ratio':1,'restore_rule':'rule/restore','retain_buffs':[],'on_finish':[{'op':'apply_buff','target':'source','buff':'buff/up'}]}}}
 director={'id':'unit/director','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'atk':100,'max_hp':1000,'def':0,'mres':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/hit','ability/kill','ability/skip','ability/withdraw']}}
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[boss,director],'rules':[{'id':'rule/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}}],
 'buffs':[{'id':'buff/old','kind':'buff','modifiers':[{'attribute':'def','layer':'flat','value':20}]},{'id':'buff/up','kind':'buff','modifiers':[{'attribute':'atk','layer':'direct_ratio','value':.5}]}],
 'selectors':[{'id':'selector/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1}],
 'abilities':[{'id':'ability/'+name,'kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('hit',{'op':'damage','damage_type':'true'}),('kill',{'op':'instant_kill','parameters':{'cause':'script','skip_rebirth':False}}),('skip',{'op':'instant_kill','parameters':{'cause':'script','skip_rebirth':True}}),('withdraw',{'op':'retire','parameters':{'reason':'withdrawn'}})]],
 'scenarioDraft':{'id':'scene/rebirth','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':5},'initialEntities':[{'definition':'unit/boss','instanceAlias':'boss','position':{'row':1,'col':1}},{'definition':'unit/director','instanceAlias':'director','position':{'row':2,'col':4}}]}}
def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=6101)
def command(s,name,at):s.submit({'action':'skill','source':'director','ability':'ability/'+name},at=at)
def test_first_zero_retains_uid_population_down_zero_then_restores_effective_hp_at_end():
 s=make();ref=s.session.world.resolve('boss');command(s,'hit',0);s.advance(1);assert s.ctx.alive('boss') and not s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==0 and s.ctx.state()['kills']==0
 assert not s.ctx.get('boss',('buffs','instances')) and not [e for e in s.session.events if e['type']=='combat.kill']
 s.advance(3);assert s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==100 and s.ctx.attributes.value('boss','atk')==60 and s.session.world.resolve('boss')==ref
def test_second_damage_is_true_death_once_and_one_combat_kill():
 s=make();command(s,'hit',0);command(s,'hit',3);s.advance(5);assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1
 assert len([e for e in s.session.events if e['type']=='combat.kill'])==1 and len([e for e in s.session.events if e['type']=='entity.rebirth.started'])==1
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_public_instant_kill_not_damage_and_respects_false_and_true_skip():
 s=make();command(s,'kill',0);s.advance(1);assert s.ctx.alive('boss') and not s.ctx.active('boss') and not [e for e in s.session.events if e['type']=='damage.accepted']
 s=make();command(s,'skip',0);s.advance(1);assert not s.ctx.alive('boss') and s.ctx.resources.current('boss','hp')==0 and s.ctx.state()['kills']==1 and len([e for e in s.session.events if e['type']=='combat.kill'])==1
def test_effective_max_capacity_rebound_is_not_literal_initial_hp():
 p=fixture();p['scenarioDraft']['initialEntities'][0]['components']={'attributes':{'base':{'max_hp':200}}};p['entities'][0]['components']['rebirth']['restore_ratio']=.5;s=make(p);command(s,'kill',0);s.advance(4);assert s.ctx.resources.current('boss','hp')==100
def test_retire_cancels_owned_finish_and_cannot_ghost_restore():
 s=make();command(s,'hit',0);s.advance(1);s.ctx.lifecycle.retire('boss','withdrawn');s.advance(5);assert not s.ctx.alive('boss') and s.ctx.resources.current('boss','hp')==0
 assert s.ctx.get('boss',('runtime','rebirth'))['phase']=='cancelled' and not [t for t in s.session.scheduler.pending if t['kind']=='domain.rebirth.finish']
def test_finish_callback_kills_source_without_reinserting_alive():
 p=fixture();p['entities'][0]['components']['rebirth']['on_finish']=[{'op':'instant_kill','target':'source','parameters':{'cause':'callback','skip_rebirth':True}}];s=make(p);command(s,'hit',0);s.advance(5)
 assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1 and not [e for e in s.session.events if e['type']=='entity.rebirth.completed']
def test_real_onbegin_rng_rule_failure_restores_hp_buffs_jobs_events_rng_and_guard():
 p=fixture();p['scenarioDraft']['resources']={'credit':{'initial':10,'capacity':100}};p['rules'].append({'id':'rule/fail','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}})
 p['entities'][0]['components']['rebirth']['on_begin']=[{'op':'random','target':'battle','stream':'peer','probability':1,'on_success':[{'op':'modify_resource','target':'battle','resource':'credit','amount_rule':'rule/fail'}]}];s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('director',['boss'],{'op':'damage','damage_type':'true'})
 assert s.checkpoint()==before and not s.ctx.rebirth._callbacks and not s.ctx.rebirth._requests
def test_pending_public_clock_boundary_and_ordered_disk_replay(tmp_path):
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=6102);command(s,'hit',0);command(s,'hit',3);s.advance(2);path=tmp_path/'cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(3);r.advance(3)
 assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
@pytest.mark.parametrize('change',[lambda p:p['entities'][0]['components']['rebirth'].update(max_count=True),lambda p:p['entities'][0]['components']['rebirth'].update(restore_ratio=0),lambda p:p['entities'][0]['components']['rebirth'].update(delay_seconds=-1),lambda p:p['entities'][0]['components']['rebirth'].update(restore_rule='buff/up'),lambda p:p['entities'][0]['components']['rebirth'].update(resource='sp'),lambda p:p['abilities'][1]['activation']['on_start'][0]['parameters'].update(skip_rebirth=1)])
def test_config_and_refs_strict_preflight(change):
 p=fixture();change(p)
 with pytest.raises(ValueError):Compiler().compile(p)

def test_pending_actor_releases_block_and_pauses_route_and_sp_recovery():
 p=fixture(delay=.2);p['entities'][0]['components']['resources']['sp']={'initial':0,'capacity':10,'recovery_rate':1};p['entities'][1]['components']['attributes']['base']['block_count']=1;p['entities'][1]['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'};p['scenarioDraft']['initialEntities'][1]['position']={'row':1,'col':1};p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':4},'checkpoints':[]}
 s=make(p);s.advance(1);assert s.ctx.spatial.blocked_by('boss')==s.session.world.resolve('director');command(s,'hit',1);s.advance(1);point=s.ctx.get('boss',('spatial','position'));sp=s.ctx.resources.current('boss','sp');assert s.ctx.spatial.blocked_by('boss') is None
 s.advance(4);assert s.ctx.get('boss',('spatial','position'))==point and s.ctx.resources.current('boss','sp')==sp and not s.ctx.active('boss')

def test_managed_wave_not_released_or_victory_before_second_true_death(tmp_path):
 p=fixture();p['scenarioDraft']['resources']={'life':{'initial':99999,'capacity':99999}};p['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'};p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][1:]
 p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','managed':True,'blocks_wave':True,'blocks_fragment':True,'spawn':{'definition':'unit/boss','instanceAlias':'boss','position':{'row':1,'col':1}}}]}]},{'fragments':[{'actions':[{'kind':'effects','effects':[{'op':'emit','target':'battle','event':'peer.nextwave'}]}]}]}]}
 s=make(p);command(s,'hit',1);command(s,'hit',6);s.advance(3);assert not s.ctx.state()['finished'] and not [e for e in s.session.events if e['type']=='peer.nextwave']
 path=tmp_path/'managed.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,h));s.advance(6);r.advance(6);assert s.ctx.state()['kills']==1 and len([e for e in s.session.events if e['type']=='entity.created' and e['payload']['definition']=='unit/boss'])==1 and s.ctx.state()['pending_waves']==0
 assert len([e for e in s.session.events if e['type']=='peer.nextwave'])==1 and s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_nested_terminal_effect_stops_following_children_and_all_owned_jobs_immediately():
 p=fixture();p['scenarioDraft']['resources']={'life':{'initial':1,'capacity':1},'credit':{'initial':10,'capacity':100}};p['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'}
 p['entities'][0]['components']['rebirth']['on_begin']=[{'op':'random','target':'battle','stream':'peer','probability':1,'on_success':[{'op':'modify_resource','target':'battle','resource':'life','value':0},{'op':'modify_resource','target':'battle','resource':'credit','value':20}]},{'op':'emit','event':'peer.must_not_emit'}]
 s=make(p);command(s,'hit',0);s.advance(1);assert s.ctx.state()['result']=='defeat' and s.ctx.resources.current('system/battle','credit')==10 and not [e for e in s.session.events if e['type']=='peer.must_not_emit']
 assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.rebirth.finish'] and s.ctx.get('boss',('runtime','rebirth'))['phase']=='cancelled'
def test_external_terminal_result_cancels_pending_recovery_on_the_same_tick():
 p=fixture(delay=1);p['scenarioDraft']['resources']={'life':{'initial':1,'capacity':1}};p['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'};p['entities'][1]['components']['abilities'].append('ability/defeat');p['abilities'].append({'id':'ability/defeat','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':'battle','resource':'life','value':0}]},'timeline':[]})
 s=make(p);command(s,'hit',0);command(s,'defeat',2);s.advance(3);assert s.ctx.state()['result']=='defeat' and not [t for t in s.session.scheduler.pending if t['kind']=='domain.rebirth.finish']
def test_zero_delay_restore_is_synchronous_and_has_no_owned_job():
 s=make(fixture(0));command(s,'hit',0);s.advance(1);assert s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==100 and not [t for t in s.session.scheduler.pending if t['kind']=='domain.rebirth.finish']
def test_runtime_bad_kill_options_reject_before_any_state_or_random_mutation():
 s=make();before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('director',['boss'],{'op':'instant_kill','parameters':{'cause':'script','skip_rebirth':1}})
 assert s.checkpoint()==before
def test_effective_instance_override_wrong_restore_contract_fails_compile():
 p=fixture();p['scenarioDraft']['initialEntities'][0]['components']={'rebirth':{'restore_rule':'buff/up'}}
 with pytest.raises(ValueError):Compiler().compile(p)

def test_explicit_owned_initial_cooldown_reset_has_real_public_boundary_and_replay():
 p=fixture();p['entities'][0]['components']['abilities']=['ability/wait'];p['entities'][0]['components']['rebirth'].update(reset_attack_clock=True,reset_cooldowns=[{'ability':'ability/wait','initial_delay_seconds':.2}]);p['abilities'].append({'id':'ability/wait','kind':'ability','activation':{'mode':'manual','cooldown_seconds':20,'on_start':[{'op':'emit','event':'peer.wait'}]},'timeline':[]})
 s=make(p)
 for at,source,aid in [(0,'boss','ability/wait'),(1,'director','ability/hit'),(9,'boss','ability/wait'),(10,'boss','ability/wait')]:s.submit({'action':'skill','source':source,'ability':aid},at=at)
 s.advance(12);assert [e['time'] for e in s.session.events if e['type']=='peer.wait']==[0,10] and [e['time'] for e in s.session.events if e['type']=='command.rejected']==[9]
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
@pytest.mark.parametrize('row',[{'ability':'ability/hit','initial_delay_seconds':1},{'ability':'buff/up','initial_delay_seconds':1},{'ability':'ability/hit','initial_delay_seconds':True}])
def test_cooldown_reset_unowned_wrongkind_bad_duration_rejected(row):
 p=fixture();p['entities'][0]['components']['rebirth']['reset_cooldowns']=[row]
 with pytest.raises(ValueError):Compiler().compile(p)

def test_early_or_bool_generation_callback_cannot_restore_health():
 s=make();command(s,'hit',0);s.advance(1);before=s.checkpoint();ref=s.session.world.resolve('boss');s.ctx.rebirth.finish(s.session,{'target':ref,'generation':1});assert s.checkpoint()==before
 with pytest.raises(ValueError):s.ctx.rebirth.finish(s.session,{'target':ref,'generation':True})
 assert s.checkpoint()==before

def test_new_generation_during_finish_callback_is_not_overwritten_by_old_completion():
 p=fixture();p['entities'][0]['components']['rebirth']['max_count']=2;p['entities'][0]['components']['rebirth']['on_finish']=[{'op':'instant_kill','target':'source','parameters':{'cause':'callback','skip_rebirth':False}}];s=make(p);command(s,'hit',0);s.advance(4)
 assert s.ctx.alive('boss') and not s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==0 and s.ctx.get('boss',('runtime','rebirth'))['generation']==2 and s.ctx.get('boss',('runtime','rebirth'))['phase']=='waiting'
 s.advance(4);assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1

def test_pending_skip_false_rejects_but_skip_true_finishes_once_without_fake_damage():
 s=make();command(s,'hit',0);s.advance(1);s.ctx.effects.execute('director',['boss'],{'op':'instant_kill','parameters':{'cause':'second','skip_rebirth':False}});assert s.ctx.alive('boss') and s.ctx.get('boss',('runtime','rebirth'))['phase']=='waiting'
 s.ctx.effects.execute('director',['boss'],{'op':'instant_kill','parameters':{'cause':'forced','skip_rebirth':True}});s.advance(5);assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1 and len([e for e in s.session.events if e['type']=='combat.kill'])==1

def test_direct_resource_api_callback_failure_is_atomic_before_health_commit():
 p=fixture();p['scenarioDraft']['resources']={'credit':{'initial':10,'capacity':100}};p['rules'].append({'id':'rule/fail','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}});p['entities'][0]['components']['rebirth']['on_begin']=[{'op':'random','target':'battle','stream':'peer','probability':1,'on_success':[{'op':'modify_resource','target':'battle','resource':'credit','amount_rule':'rule/fail'}]}]
 s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.resources.adjust('boss','hp',value=0,source='director')
 assert s.checkpoint()==before and not s.ctx.rebirth._requests and not s.ctx.rebirth._callbacks
