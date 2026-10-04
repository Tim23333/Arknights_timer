import pytest
from ark_sim import Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.chapter07_consumers_peer.common import *
def ore(p,sp=7):p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch7/predefined/ore/level1','instanceAlias':'ore','position':{'row':3,'col':3},'components':{'resources':{'sp':{'initial':sp}}}})
def test_fourteen_actual_typed_states_receive_exact_none500_or_reject():
 p=package('ore14');ore(p);cases=[('side0',{'side':0},True),('side1',{'side':1},True),('side2',{'side':2},False),('ground',{'motion':1},True),('air',{'motion':2},True),('motion0',{'motion':0},False),('category2',{'category':2},False),('free',{'target_free':True},True),('camo',{'camouflage':True},False),('allyfree',{'ally_target_free':True},True),('healfree',{'heal_free':True},True),('flag14',{'abnormal_flags':[14]},True),('combo1',{'abnormal_combos':[1]},True),('tokenbit',{'unit_type':4},True)]
 for name,flags,_ in cases:recipient(p,name,(3,4),flags)
 s=create(p,[ORE]);s.advance(20);capture(s,'ore14')
 for name,_,accepted in cases:
  assert s.ctx.resources.current(name,'hp')==(8500 if accepted else 9000) and s.ctx.resources.current(name,'sp')==int(accepted)
 hits=events(s,'damage.accepted');assert len(hits)==sum(x[2] for x in cases) and all(e['time']==19 and e['payload']['damage_flags']=={'source_attack_type':'NONE','ignore_for_sp':False} for e in hits) and not events(s,'attack.accepted')
 assert not any(b['definition'].endswith('/damage_payload') for x in cases for b in s.ctx.get(x[0],('buffs','instances'),[]))
def test_diamond_cell_edge_and_half_tie_are_explicit_current_projection():
 p=package('ore_geometry');ore(p)
 for name,pos in [('edge',(3,5)),('diag',(4,4)),('outside',(4,5)),('beforehalf',(3,5.499999)),('athalf',(3,5.5))]:recipient(p,name,pos)
 s=create(p,[ORE]);s.advance(20);capture(s,'ore_cells');assert [s.ctx.resources.current(x,'hp') for x in ['edge','diag','outside','beforehalf','athalf']]==[8500,8500,9000,8500,9000]
def test_midcast_immune_expiry_and_listener_checked_at_actual_payload_disk_head(tmp_path):
 p=package('ore_late_markers');ore(p);recipient(p,'a',(3,4));recipient(p,'b',(4,3));recipient(p,'c',(3,2));p['buffs'][0]['duration_seconds']=1/30
 # Source marker exact ID, with a controlled finite override at t18 -> t19.
 controller(p,[ability('mark',[{'op':'apply_buff','target':4,'buff':'buff/ch7/source/ore_listener'},{'op':'apply_buff','target':5,'buff':'buff/ch7/source/ore_immune'}]),ability('held',[{'op':'apply_buff','target':3,'buff':'buff/ch7/source/ore_immune'}])])
 s=create(p,[ORE]);command(s,'mark',18);command(s,'held',19);s.advance(18);pin=write_ordered(tmp_path/'ore18.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'ore18.json',pin),providers=registry());s.advance(3);r.advance(3);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'ore_late_markers');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 assert [s.ctx.resources.current(x,'hp') for x in ['a','b','c']]==[9000,8500,8500] and s.ctx.get('b',('behavior','state'))=='mode1' and s.ctx.get('a',('behavior','state'))=='mode0'
def test_source_retirement_during_declared_windup_cancels_payload_and_overlay():
 p=package('ore_retire');ore(p);recipient(p,'a',(3,4));controller(p,[ability('retire',[{'op':'retire','target':2,'parameters':{'reason':'withdraw'}}])]);s=create(p,[ORE]);command(s,'retire',18);s.advance(22);capture(s,'ore_cancel');assert s.ctx.resources.current('a','hp')==9000 and not events(s,'damage.accepted') and not s.ctx.active('ore') and not s.ctx.get('ore',('runtime','casts'))
