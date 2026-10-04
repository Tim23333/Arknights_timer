from ark_sim import Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.chapter07_consumers_peer.common import *
MINE_ID='unit/ch7/predefined/mine/level1'
def mine(p,ready=False):
 row={'definition':MINE_ID,'instanceAlias':'mine','position':{'row':0,'col':0}}
 if ready:row['components']={'resources':{'sp':{'initial':25}},'behavior':{'state':'mode1'}}
 p['scenarioDraft']['initialEntities'].append(row)
def test_closed_radius_ground_free_included_air_camo_and_outer_rejected():
 p=package('mine_radius');mine(p,True);r=.550000011920929
 for name,x,flags in [('edge',r,{}),('outer',r+1e-8,{}),('air',.1,{'motion':2}),('camo',.2,{'camouflage':True}),('free',.3,{'target_free':True})]:recipient(p,name,(0,x),flags)
 s=create(p,[MINE]);s.advance(2);capture(s,'mine_radius');assert [s.ctx.resources.current(x,'hp') for x in ['edge','outer','air','camo','free']]==[6000,9000,9000,9000,6000]
 assert len(events(s,'area.resolved'))==1 and len(events(s,'damage.accepted'))==2 and not s.ctx.active('mine') and s.ctx.resources.current('mine','hp')==100
 assert all(e['payload']['damage_flags']=={'source_attack_type':'NORMAL','ignore_for_sp':False} for e in events(s,'damage.accepted'))
def test_natural_source_mode20s_separate_from_sp25_and_disk_prehit(tmp_path):
 p=package('mine_clock');mine(p);recipient(p,'a',(0,.5));s=create(p,[MINE]);s.advance(601);assert s.ctx.get('mine',('behavior','state'))=='mode1' and s.ctx.resources.current('a','hp')==9000 and s.ctx.resources.current('mine','sp')<25
 pin=write_ordered(tmp_path/'mine601.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'mine601.json',pin),providers=registry());s.advance(151);r.advance(151);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'mine_natural_clock');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 hits=events(s,'damage.accepted');assert len(hits)==1 and hits[0]['time']==749 and hits[0]['payload']['amount']==3000 and s.ctx.resources.current('a','sp')==1
def deploy(t,alias):return {'action':'deploy','definition':MINE_ID,'position':{'row':1,'col':1},'alias':alias},t
def test_all_native_fifteen_cards_cost_stock_capacity_refund_cooldown_and_public_cp(tmp_path):
 p=package('mine_cards15');p['scenarioDraft']['map']['tiles']=[{'tileKey':'tile_floor','buildableType':1,'heightType':0,'passableMask':1,'advancedBuildMask':1} for _ in range(49)];s=create(p,[MINE])
 for i in range(15):
  cmd,t=deploy(i*211,'mine'+str(i));s.submit(cmd,at=t);s.submit({'action':'withdraw','source':'mine'+str(i)},at=t+1)
 cmd,_=deploy(0,'duplicate');s.submit(cmd,at=0);cmd,_=deploy(210,'early');s.submit(cmd,at=210);cmd,_=deploy(3165,'exhausted');s.submit(cmd,at=3165)
 s.advance(2);assert s.ctx.resources.current('system/battle','dp')==95 and s.ctx.resources.current('system/battle','stock_ch7_mine')==14 and s.ctx.resources.current('system/battle','deployment_capacity')==0
 pin=write_ordered(tmp_path/'mine_cards2.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'mine_cards2.json',pin),providers=registry());s.advance(3165);r.advance(3165);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'mine_fifteen_cards');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 assert s.ctx.resources.current('system/battle','dp')==25 and s.ctx.resources.current('system/battle','stock_ch7_mine')==0 and s.ctx.resources.current('system/battle','deployment_capacity')==0
 assert len(events(s,'command.accepted'))==30 and len(events(s,'command.rejected'))==3 and not events(s,'damage.accepted')
def test_mine_withdraw_before_ready_cancels_mode_timer_and_never_refunds():
 p=package('mine_cancel');s=create(p,[MINE]);cmd,_=deploy(0,'mine');s.submit(cmd,at=0);s.submit({'action':'withdraw','source':'mine'},at=599);s.advance(605);capture(s,'mine_end_cancel');assert s.ctx.resources.current('system/battle','dp')==95 and s.ctx.resources.current('system/battle','stock_ch7_mine')==14 and not s.ctx.active('mine') and s.ctx.get('mine',('behavior','state'))=='mode0'
