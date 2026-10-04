import json
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.chapter07_consumers_peer.common import *
NATIVE=BASE/'chapter07_stage_models/level_main_07-15.native_draft.v1.json'
MINE_ID='unit/ch7/predefined/mine/level1'
def fixed_package(k='cards'):
 native=json.loads(NATIVE.read_text(encoding='utf8'));p=package(k);p['buffs']=[];p['definitions']=native['definitions'];p['scenarioDraft']['roster']=native['scenarioDraft']['roster'];p['scenarioDraft']['cards']=[MINE_ID]
 p['scenarioDraft']['map']['tiles']=[{'tileKey':'tile_floor','buildableType':1,'heightType':0,'passableMask':1,'advancedBuildMask':1} for _ in range(49)]
 return p
def deploy(alias='mine',definition=MINE_ID):return {'action':'deploy','definition':definition,'position':{'row':1,'col':1},'alias':alias}
def test_native_card_public_deploy_keeps_actual_twelve_and_cp_restore_head(tmp_path):
 p=fixed_package();s=create(p,[MINE]);assert MINE_ID in s.program.definitions and len(s.program.scenario['roster'])==12;s.submit(deploy(),at=0);s.advance(2);pin=write_ordered(tmp_path/'native_card2.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'native_card2.json',pin),providers=registry());s.advance(3);r.advance(3);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'fixed12_cards_real');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 assert len(events(s,'command.accepted'))==1 and s.ctx.resources.current('system/battle','dp')==95 and s.ctx.resources.current('system/battle','stock_ch7_mine')==14 and s.ctx.resources.current('system/battle','deployment_capacity')==0
def test_undeclared_stock_card_definition_cannot_borrow_other_card_authority():
 p=fixed_package('rogue');src=json.loads(MINE.read_text(encoding='utf8'));fake=deepcopy(src['entities'][0]);fake['id']='unit/peer/rogue';p['entities'].append(fake);p['scenarioDraft']['dependencies']=['unit/peer/rogue'];s=create(p,[MINE]);s.submit(deploy('rogue','unit/peer/rogue'),at=0);s.advance(1);capture(s,'rogue_card');assert len(events(s,'command.rejected'))==1 and s.ctx.resources.current('system/battle','stock_ch7_mine')==15 and s.ctx.resources.current('system/battle','dp')==100
@pytest.mark.parametrize('value',[True,[True],[MINE_ID,MINE_ID],[None],[],['unit/char_151_myrtle']])
def test_card_declaration_wrongtype_duplicate_or_roster_membership(value):
 p=fixed_package('typed');p['scenarioDraft']['cards']=value;INPUTS.append({'package':p,'modules':[str(MINE)]})
 if value==[]:
  s=create(p,[MINE]);s.submit(deploy(),at=0);s.advance(1);capture(s,'empty_cards_reject');assert len(events(s,'command.rejected'))==1
 else:
  with pytest.raises(ValueError):Compiler(providers=registry()).compile(p,packages=[str(MINE)])
@pytest.mark.parametrize('value',[True,15.0,-1,float('nan')])
def test_card_stock_resource_requires_exact_finite_integer(value):
 p=fixed_package('badstock');p['scenarioDraft']['resources']['stock_ch7_mine']['initial']=value;INPUTS.append({'package':p,'modules':[str(MINE)]})
 with pytest.raises(ValueError):Compiler(providers=registry()).compile(p,packages=[str(MINE)])
def test_stock_zero_card_rejects_without_dp_or_actor_allocation():
 p=fixed_package('stockzero');p['scenarioDraft']['resources']['stock_ch7_mine']['initial']=0;s=create(p,[MINE]);before=s.session.world.snapshot();s.submit(deploy(),at=0);s.advance(1);capture(s,'empty_stock');CAPTURES.append({'case':'empty_stock_before','world':before});assert len(events(s,'command.rejected'))==1 and s.ctx.resources.current('system/battle','dp')==100 and s.session.world.snapshot()==before
def test_late_card_creation_buff_failure_rolls_back_payment_stock_allocation_tasks_rng():
 p=fixed_package('latecardfault');src=json.loads(MINE.read_text(encoding='utf8'));fake=deepcopy(src['entities'][0]);fake['id']='unit/peer/badcard';fake['components']['buffs']['initial'].append('buff/peer/cardfault');p['entities'].append(fake);p['scenarioDraft']['cards']=['unit/peer/badcard'];p['buffs'].append({'id':'buff/peer/cardfault','kind':'buff','effects':[{'op':'modify_resource','target':'source','resource':'hp','delta':-3},{'op':'damage','target':'source','damage_type':'true','rules':{'damage.pipeline':'rule/peer/cardfault'}}]});p['rules'].append({'id':'rule/peer/cardfault','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'bad','expression':'1/0'}],'output':'nodes.bad'}})
 s=create(p,[MINE]);s.submit(deploy('badcard','unit/peer/badcard'),at=0);world=s.session.world.snapshot();rng=s.session.random.snapshot();scheduled=s.session.scheduler._next_id;s.advance(1);capture(s,'card_late_fault');CAPTURES.append({'case':'card_late_before','world':world,'rng':rng,'scheduled':scheduled});assert len(events(s,'command.rejected'))==1 and s.session.world.snapshot()==world and s.session.random.snapshot()==rng and s.session.scheduler._next_id==scheduled and not s.session.scheduler.pending
