from tools.chapter09_rock_modes_peer.fixture import *
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=13739731)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
def proof(p,name,splits,end):
 a=create(p);a.advance(end);b=create(p);LOG.mkdir(parents=True,exist_ok=True);pins=[]
 for i,t in enumerate(splits):
  b.advance(t-b.session.time);path=LOG/(name+str(i)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append(pin);b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(end-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_CPP_head_full_equal':True,'CP_SHAs':pins,'input_digest':digest(p),'events':len(a.session.events)},indent=2),encoding='utf8');return a

def test_explicit_ground_route_aerial_targets_wall_detour_no_block_and_land_real_block():
 p=hover();s=create(p);s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('hover') is None;assert s.ctx.get('hover',('spatial','route','motionMode'))==0;assert s.ctx.get('hover',('selection_state','motion'))==2;path=list(s.ctx.spatial.grid.path({'row':2,'col':1},{'row':2,'col':7},0));assert {'row':2,'col':3} not in path and {'row':2,'col':4} not in path
 s=proof(p,'hover_groundroute',[12,40],60);assert s.ctx.spatial.blocked_by('hover') is None;assert s.ctx.get('hover',('spatial','position'))!={'row':2,'col':1}
 p=hover(land=8);s=proof(p,'land_blocks',[7,9],30);assert s.ctx.get('hover',('selection_state','motion'))==1;assert s.ctx.spatial.blocked_by('hover') is None;assert s.ctx.get('hover',('spatial','route','motionMode'))==0
 p=hover(land=0);s=proof(p,'land0_blocks',[1,10],30);assert s.ctx.spatial.blocked_by('hover')==s.session.world.resolve('blocker');assert s.ctx.get('hover',('selection_state','motion'))==1;assert s.ctx.get('hover',('spatial','route','motionMode'))==0

def test_default_no_route_optin_legacy_sync_and_bad_enum_effect_atomic():
 s=proof(hover(False),'default_sync',[12],30);assert s.ctx.get('hover',('spatial','route','motionMode'))==1;path=list(s.ctx.spatial.grid.path({'row':2,'col':1},{'row':2,'col':7},1));assert path==[{'row':2,'col':7}];assert all(point['row']==2 for point in path)
 for value in [True,-1,2,'WALK']:
  p=hover();p['entities'][0]['components']['spatial']['route_motion_mode']=value
  with pytest.raises(ValueError):Compiler(providers=REG).compile(p)
 s=create(hover());s.ctx.attributes.value('hover','move_speed');before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('hover',['hover'],{'op':'set_motion_mode','value':0,'parameters':{'route_motion_mode':True}})
 assert s.checkpoint()==before


def test_durokt_real_land_stun_recover28_once_busy_and_source_frames():
 p=rock();p['scenarioDraft']['commands']=[{'at':9,'action':'skill','source':'controller','ability':'ability/peer/rock/stun'}];s=proof(p,'recover28',[10,30,54],85);assert [t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/durokt/recover']==[25];assert [t for t,x in events(s,'ability.finished') if x['ability']=='ability/ch9/durokt/recover']==[53];assert s.ctx.resources.current('enemy','recover_used')==1;assert s.ctx.resources.current('enemy','mode')==1;assert s.ctx.get('enemy',('selection_state','motion'))==1;assert s.ctx.get('enemy',('spatial','route','motionMode'))==0
 s=create(p);s.advance(30);pos=s.ctx.get('enemy',('spatial','position'));s.advance(20);assert s.ctx.get('enemy',('spatial','position'))==pos


def test_durokt_recover_busy_actual_interrupt_never_restarts():
 p=rock();p['scenarioDraft']['commands']=[{'at':t,'action':'skill','source':'controller','ability':'ability/peer/rock/stun'} for t in [9,34]];s=proof(p,'recover_cancel',[30,35],90);assert [t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/durokt/recover']==[25];assert not [t for t,x in events(s,'ability.finished') if x['ability']=='ability/ch9/durokt/recover'];assert s.ctx.resources.current('enemy','recover_used')==1


def test_durokt_land_real_block_gate_then_leave_allows_one_recover():
 p=rock(block=True);p['scenarioDraft']['commands']=[{'at':9,'action':'skill','source':'controller','ability':'ability/peer/rock/stun'},{'at':91,'action':'skill','source':'blocker','ability':'ability/peer/rock/leave'}];s=create(p);s.advance(80);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('blocker');assert not [t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/durokt/recover']
 s=proof(p,'blocked_leave_recover',[80,95],180);starts=[t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/durokt/recover'];assert len(starts)==1 and starts[0]>=91;assert s.ctx.resources.current('enemy','recover_used')==1

@pytest.mark.parametrize('profile,ratio,motion',[('native_literal',.20000000298023224,1),('prts_reference',1,2)])
def test_gargoyle_native_float20_vs_reference100_stone300_then_Start20_no_heal(profile,ratio,motion):
 p=rock('dugago',profile);p['scenarioDraft']['commands']=[{'at':11,'action':'skill','source':'controller','ability':'ability/peer/rock/hit'}];s=create(p);s.advance(12);assert abs(s.ctx.resources.current('enemy','hp')-HP*ratio)<1e-7;s.advance(290);assert abs(s.ctx.resources.current('enemy','hp')-HP*ratio)<1e-7
 s=proof(p,'gargoyle_'+profile,[12,312,332],360);assert [t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/dugago/start_flight']==[311];assert [t for t,x in events(s,'buff.applied') if x['buff']=='buff/ch9/dugago/reborn_complete']==[331];assert s.ctx.get('enemy',('selection_state','motion'))==motion;assert s.ctx.get('enemy',('spatial','route','motionMode'))==0;assert abs(s.ctx.resources.current('enemy','hp')-HP*ratio)<1e-7;assert s.ctx.attributes.value('enemy','def')==613;assert s.ctx.attributes.value('enemy','mres')==87


def test_early_stone_real_remove_Start20_and_second_death_not_extra_rebirth():
 p=rock('dugago');p['scenarioDraft']['commands']=[{'at':11,'action':'skill','source':'controller','ability':'ability/peer/rock/hit'},{'at':60,'action':'skill','source':'controller','ability':'ability/peer/rock/clear_stone'},{'at':95,'action':'skill','source':'controller','ability':'ability/peer/rock/hit'}];s=proof(p,'stone_early_second',[12,61,81],100);assert [t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/dugago/start_flight']==[60];assert [t for t,x in events(s,'buff.applied') if x['buff']=='buff/ch9/dugago/reborn_complete']==[80];assert not s.ctx.alive('enemy');assert s.ctx.get('enemy',('runtime','casts'))=={}


def test_actual_source_current_module_and_route_protocol_guard():assert guard()==START
