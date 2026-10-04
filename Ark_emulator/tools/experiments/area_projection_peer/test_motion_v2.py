from ark_sim import Engine,Compiler
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.area_projection_peer.test_projection_controller import package,make,cmd,ev,capture,registry,INPUTS,CAPTURES,deepcopy,pytest
def test_actual_ground_fly_ground_roundtrip_projection_cp_and_public_head(tmp_path):
 p=package();p['abilities'].append({'id':'ability/peer/land','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'set_motion_mode','target':3,'value':0}]},'timeline':[]});p['entities'][-1]['components']['abilities'].append('ability/peer/land');s=make(p);cmd(s,'area',0);cmd(s,'fly',1);s.submit({'action':'skill','source':'director','ability':'ability/peer/land'},at=5);cmd(s,'area',6);s.advance(4)
 assert s.ctx.get('corner',('selection_state','motion'))==2 and s.ctx.resources.current('corner','hp')==101
 pin=write_ordered(tmp_path/'fly4.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'fly4.json',pin),providers=registry());s.advance(6);r.advance(6);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'roundtrip_fly_land');assert s.checkpoint()==r.checkpoint()==h.checkpoint() and s.ctx.get('corner',('selection_state','motion'))==1 and s.ctx.resources.current('corner','hp')==90
 assert [(e['time'],e['payload']['mode']) for e in ev(s,'movement.motion_changed')]==[(1,1),(5,0)]
def test_actual_public_setter_without_old_selection_state_creates_only_typed_motion():
 p=package();p['entities'][1]['components'].pop('selection_state');s=make(p);cmd(s,'fly',0);s.advance(1);capture(s,'setter_absent_state');assert s.ctx.get('corner',('selection_state',))=={'motion':2} and s.ctx.get('corner',('spatial','motion_mode'))==1
@pytest.mark.parametrize('value',[True,False,1.0,-1,2,None])
def test_typed_setter_bad_modes_are_rejected_before_world(value):
 p=package();p['abilities'][2]['activation']['on_start'][0]['value']=value;INPUTS.append(p)
 with pytest.raises(ValueError):Compiler(providers=registry()).compile(p)
def test_late_onstart_callback_failure_rolls_back_physical_and_projected_motion():
 p=package();p['rules'].append({'id':'rule/peer/motionfault','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'bad','expression':'1/0'}],'output':'nodes.bad'}});p['entities'][-1]['components']['attributes']={'base':{'max_hp':101,'atk':13,'def':31,'mres':17}};p['entities'][1]['components']['attributes']['base'].update(atk=0,**{'def':31,'mres':17});p['abilities'][2]['activation']['on_start'] += [{'op':'modify_resource','target':3,'resource':'hp','delta':-7},{'op':'damage','target':3,'damage_type':'true','rules':{'damage.pipeline':'rule/peer/motionfault'}}]
 s=make(p);s.advance(1);world=s.session.world.snapshot();rng=s.session.random.snapshot();cmd(s,'fly',1);s.advance(1);capture(s,'onstart_motion_fault');assert len(ev(s,'command.rejected'))==1 and s.session.world.snapshot()==world and s.session.random.snapshot()==rng and not ev(s,'movement.motion_changed')
