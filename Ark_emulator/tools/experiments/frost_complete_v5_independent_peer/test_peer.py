import json,hashlib
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];MODULE=ROOT/'packages/campaign/chapter04_boss/frost_complete_v1/module.reference.json'
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=='1e452d2a260af4590fa4a4aa0ef3eb2a8298f8ca332753af36b657b192e6fa6c'
ICE='ability/ch4/frost/ice_shield';BLAST='ability/frost/blast';NORMAL='ability/frost/normal';INPUTS=[];CAPTURES=[]
def hero(ident='unit/peer/hero'):return {'id':ident,'kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'mres':20,'def':31,'attack_interval':1,'attack_speed_ratio':1,'block_count':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
def fixture(ready=False,one_cell=False,empty=False):
 p=json.loads(MODULE.read_bytes());unit=hero();p['entities'].append(unit);d=hero('unit/peer/director');d['components']['abilities']=['ability/peer/sleep','ability/peer/wake'];p['entities'].append(d)
 p['abilities'].extend([{'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('sleep',{'op':'apply_buff','target':2,'buff':'buff/m70/sleep'}),('wake',{'op':'remove_buff','target':2,'buff':'buff/m70/sleep'})]])
 source={'definition':'unit/ch4/frstar/level0','instanceAlias':'boss','position':{'row':2,'col':2}}
 if ready:source['components']={'ability_timing':{'initial_cooldowns':{ICE:0,BLAST:0}}}
 tiles=[{'buildableType':0 if one_cell or empty else 1,'passableMask':1} for _ in range(35)]
 if one_cell:tiles[2*7+3]['buildableType']=1
 initial=[source,{'definition':unit['id'],'instanceAlias':'hero','position':{'row':2,'col':4.4 if one_cell else 3}},{'definition':d['id'],'instanceAlias':'director','position':{'row':4,'col':6}}]
 if empty:
  initial=[source];source['route']={'motionMode':0,'startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':6},'checkpoints':[]}
 p['scenarioDraft']={'id':'scene/peer/frost_complete','ruleset':'ruleset/ark_standard','roster':[unit['id']],'map':{'rows':5,'cols':7,'tiles':tiles},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':25,'capacity':99}},'objectives':{'life_resource':'life'},'initialEntities':initial}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=10410)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def starts(s):return [(e['time'],e['payload']['ability']) for e in ev(s,'ability.started') if e['payload']['source']==2]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def exact(s,tmp,n):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(n);r.advance(n)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();return h
def test_actual_normal_clock_and_blast504_after_ground_primary_native_stats(tmp_path):
 s=make(fixture());assert s.ctx.get('boss',('runtime','cooldowns',ICE))==900 and s.ctx.get('boss',('runtime','cooldowns',BLAST))==255
 s.advance(349);exact(s,tmp_path,23);capture(s,'normal_then_blast')
 assert starts(s)==[(0,NORMAL),(111,NORMAL),(222,NORMAL),(333,BLAST)]
 assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted')]==[(20,336),(131,336),(242,336),(361,504)]
 assert not ev(s,'tile.selection');assert s.ctx.resources.current('boss','hp')==25000
def test_single_cell_min2_ice55_then_blast139_outside_splash_and_token_retain_withdraw_reject(tmp_path):
 s=make(fixture(True,True));s.advance(54);assert starts(s)==[(0,ICE)] and not ev(s,'tile.token_created');assert s.ctx.get('boss',('runtime','behavior_decision','move')) is False
 exact(s,tmp_path,87);tokens=[e for e in s.session.world.entities() if e['definition_id']=='unit/ch4/frost/sealed_floor'];assert len(tokens)==1 and tokens[0]['components']['spatial']['position']=={'row':2,'col':3}
 assert starts(s)==[(0,ICE),(111,BLAST)];assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted')]==[(139,504)]
 token=tokens[0]['id'];s.submit({'action':'withdraw','source':token},at=141);s.submit({'action':'withdraw','source':'boss'},at=142);s.advance(3);capture(s,'one_cell_ice_then_blast')
 assert s.ctx.active(token) and not s.ctx.selectable(token) and not s.ctx.effect_target_available(token);assert not s.ctx.active('boss')
 assert s.ctx.resources.current(token,'hp')==100 and s.ctx.resources.current('system/battle','dp')==25
 assert any(e['payload']['reason']=='entity is not manually withdrawable' for e in ev(s,'command.rejected'))
 assert s.ctx.spatial.grid.passable(2,3) and s.ctx.spatial.grid.tile(2,3)['buildableType']==1
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_zero_candidate_ready_ice_and_no_actor_target_does_not_pin_movement_or_draw_rng(tmp_path):
 s=make(fixture(True,empty=True));s.advance(12);exact(s,tmp_path,12);capture(s,'empty_tiles_move')
 assert not starts(s) and not ev(s,'tile.selection') and not ev(s,'damage.accepted');assert s.session.random.samples==()
 pos=s.ctx.get('boss',('spatial','position'));assert pos['col']>2 and s.ctx.get('boss',('runtime','behavior_decision','move')) is True
def environment(amount):return {'op':'no_source_damage','target':2,'fixed_amount':amount,'damage_type':'true','attack_type':'NONE','origin':{'kind':'independent_complete_frost_environment'},'ignore_for_sp':False,'damage_without_modify':False,'node_is_env_damage':False,'env_blackboard_injected':True,'environmental':True,'rules':{'damage.pipeline':'rule/peer/environment'}}
def test_no_source_down_cancels_ice_sleep_after_rebirth_then630_normal945_blast_and_final_none_claim(tmp_path):
 p=fixture(True);p['rules'].append({'id':'rule/peer/environment','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'answer','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],'output':'nodes.answer'}});p['scenarioDraft']['scheduledEffects']=[{'at':10,'effect':environment(25000)},{'at':528,'effect':environment(25000)}]
 s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/peer/sleep'},at=161);s.submit({'action':'skill','source':'director','ability':'ability/peer/wake'},at=180)
 s.advance(11);assert s.ctx.resources.current('boss','hp')==0 and s.ctx.alive('boss') and not s.ctx.active('boss') and s.ctx.state()['kills']==0
 h=write_ordered(tmp_path/'down.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'down.json',h));s.advance(151);r.advance(151)
 assert s.ctx.get('boss',('runtime','cooldowns',ICE))==1060 and s.ctx.get('boss',('runtime','cooldowns',BLAST))==415
 assert not s.ctx.buffs.controls('boss')['attack'];assert s.ctx.spatial.selection_state('boss',DEFAULT_STATE)['abnormal_immunes']==[0,12,16,25]
 s.advance(368);r.advance(368);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'rebirth_sleep_wake_none')
 packets=[e for e in ev(s,'damage.accepted') if e['payload']['source']==2];assert [(e['time'],e['payload']['amount']) for e in packets]==[(291,504),(402,504),(521,756)]
 assert not ev(s,'tile.token_created');assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1
 kills=ev(s,'combat.kill');assert len(kills)==1 and kills[0]['payload']['source'] is None and kills[0]['payload']['origin']==environment(25000)['origin']
