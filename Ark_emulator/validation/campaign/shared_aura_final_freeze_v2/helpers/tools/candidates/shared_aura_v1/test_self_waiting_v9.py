"""Actual retained waiting owner may be its own Aura target only; other waiting actors rejected."""
import json,sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_shared_aura_v9_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.candidates.shared_aura_v1.test_shared_guarded_v9 import waiting_package
OUT=ROOT/'validation/campaign/shared_aura_self_v9'
def package():
 p=waiting_package();p['selectors'][0]['filters']=[{'state':'alive'}];cfg={'_ignoreTargetFree':0,'_onlyIgnoreSomeOfTargetFreeCase':0,'_excludeSomeAbnormalFlags':0,'_needProfessionMask':0,'_ignoreAllyTargetFree':0,'_ignoreHealFree':0,'_ignoreMotionMode':0,'_forceIgnoreCamouflage':0,'_checkUnitType':0,'_targetSide':1,'_targetCategory':1,'_targetMotion':3};p['rules'].append({'id':'rule/self/typed','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}});p['selectors'][0]['eligibility']={'rule':'rule/self/typed','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}};return p
def children(s,ref='parent1'):return [i for i in s.ctx.entity(ref)['components']['buffs']['instances'] if i.get('aura_leases')]
def kill(s,ref='parent1'):s.ctx.effects.execute('parent2',[s.session.world.resolve(ref)],{'op':'damage','damage_type':'true','scale':0,'additions':100})
def test_actual_self_HP0_has_original_child_max1_and_general_select_still_rejects():
 s=Engine.create(Compiler().compile(package()));before=[i['id'] for i in children(s)];assert s.ctx.attributes.value('parent1','atk')==120;kill(s);assert s.ctx.resources.current('parent1','hp')==0 and not s.ctx.active('parent1');s.session.advance(12);assert [i['id'] for i in children(s)]==before and s.ctx.attributes.value('parent1','atk')==120 and s.ctx.attributes.value('parent1','def')==250;assert s.ctx.spatial.select('parent1','selector/peer/receiver')==[]
def test_other_actual_waiting_ally_not_given_self_target_permission():
 p=package();p['entities'][2]['components']['rebirth']=deepcopy(p['entities'][0]['components']['rebirth']);p['entities'][2]['components']['rebirth']['retain_buffs']=[];s=Engine.create(Compiler().compile(p));kill(s,'receiver');assert s.ctx.alive('receiver') and not s.ctx.active('receiver') and not children(s,'receiver');kill(s);assert children(s) and not children(s,'receiver')
def test_self_selector_explicit_exclude_source_still_excludes_waiting_owner():
 p=package();p['selectors'][0]['parameters']={'exclude_source':True};s=Engine.create(Compiler().compile(p));assert not children(s);kill(s);s.session.advance(7);assert not children(s) and s.ctx.attributes.value('parent1','atk')==100
def test_waiting_self_CP6_head_and_actual_same_actor_restore():
 p=package();p['selectors'].append({'id':'selector/self/p1','kind':'selector','region':{'type':'all'},'filters':[{'tag':'parent1'}]});p['abilities']=[{'id':'ability/self/kill','kind':'ability','selector':'selector/self/p1','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':0,'additions':100}}]}];p['entities'][1]['components']['abilities']=['ability/self/kill'];program=Compiler().compile(p);s=Engine.create(program);s.submit({'action':'skill','source':'parent2','ability':'ability/self/kill'},at=5);s.session.advance(6);assert children(s);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'self6.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.session.advance(34);r.session.advance(34);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot();assert s.ctx.active('parent1') and s.ctx.resources.current('parent1','hp')==100;(OUT/'actual.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')
