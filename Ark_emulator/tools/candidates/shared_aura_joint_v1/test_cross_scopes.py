"""Fresh joint two-capability checks: Aura never grants cast, timer never grants wrong Aura."""
import json,sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_chapter07_foundation_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.candidates.shared_aura_v1.test_shared_guarded_v9 import waiting_package,children
CORE='43d8dc974b4a914aabc3dc4315b4178d4516913edbb2a5e80ce0e7c629c8d73a';OUT=ROOT/'validation/campaign/shared_aura_joint_cross_v1'
def package(waiting=True):
 assert implementation_digest()==CORE;p=waiting_package();cfg={'_ignoreTargetFree':0,'_onlyIgnoreSomeOfTargetFreeCase':0,'_excludeSomeAbnormalFlags':0,'_needProfessionMask':0,'_ignoreAllyTargetFree':0,'_ignoreHealFree':0,'_ignoreMotionMode':0,'_forceIgnoreCamouflage':0,'_checkUnitType':0,'_targetSide':1,'_targetCategory':1,'_targetMotion':3};p['rules'].append({'id':'rule/joint/typed','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}});p['selectors'][0]['eligibility']={'rule':'rule/joint/typed','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}};attack=deepcopy(p['selectors'][0]);attack['id']='selector/joint/victim';attack['filters']=[{'tag':'victim'}];attack['eligibility']['parameters']['source_configuration']['_targetSide']=2;p['selectors'].append(attack);p['entities'].append({'id':'unit/joint/victim','kind':'entity','tags':['victim'],'components':{'attributes':{'base':{'max_hp':100,'atk':0,'def':0,'mres':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/joint/victim','instanceAlias':'victim','position':{'row':0,'col':3}});aid='ability/joint/waiting';tid='buff/joint/wait_timer';p['abilities']=[{'id':aid,'kind':'ability','selector':attack['id'],'activation':{'mode':'manual','parameters':{'auto_only':True}},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':0,'additions':10}}]}];p['entities'][0]['components']['abilities']=[aid];p['buffs'].append({'id':tid,'kind':'buff','interval_seconds':4/30,'effects':[{'op':'trigger_ability','ability':aid}]});spec=p['entities'][0]['components']['rebirth'];spec['retain_buffs'].append(tid);spec['on_begin']=[{'op':'apply_buff','buff':tid}]
 if waiting:spec['waiting_actions']={'abilities':[aid],'buffs':[tid]}
 p['scenarioDraft']['dependencies'] += [tid,aid];return p
def kill(s):s.ctx.effects.execute('parent2',[s.session.world.resolve('parent1')],{'op':'damage','damage_type':'true','scale':0,'additions':100})
def test_Aura_only_waiting_owner_does_not_grant_periodic_or_manual_cast():
 p=package(False);s=Engine.create(Compiler().compile(p));kill(s);assert children(s);s.session.advance(10);assert s.ctx.resources.current('victim','hp')==100;before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('parent1','ability/joint/waiting',automatic=True)
 assert s.checkpoint()==before
def test_real_waiting_timer_and_Aura_both_work_CP_head_but_auth_not_interchangeable():
 p=package();p['selectors'].append({'id':'selector/joint/p1','kind':'selector','region':{'type':'all'},'filters':[{'tag':'parent1'}]});p['abilities'].append({'id':'ability/joint/kill','kind':'ability','selector':'selector/joint/p1','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':0,'additions':100}}]});p['entities'][1]['components']['abilities']=['ability/joint/kill'];program=Compiler().compile(p);s=Engine.create(program);s.submit({'action':'skill','source':'parent2','ability':'ability/joint/kill'},at=5);s.session.advance(6);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'joint6.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.session.advance(14);r.session.advance(14);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot();assert s.ctx.resources.current('victim','hp')==70;assert children(s);parent=next(i for i in s.ctx.entity('parent1')['components']['buffs']['instances'] if i['definition'].endswith('/marker'))['id']
 with pytest.raises(ValueError):s.ctx.spatial.select('parent1','selector/joint/victim',aura_parent=parent)
 assert s.ctx.spatial.select('parent1','selector/joint/victim')==[]
 assert not s.ctx.waiting_actions._scopes and not s.ctx.waiting_actions._timers and not s.ctx.rebirth._aura_waiting_begins;(OUT/'actual.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')
def test_plain_manual_cast_rejected_even_both_leases_declared():
 s=Engine.create(Compiler().compile(package()));kill(s);s.session.advance(1);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('parent1','ability/joint/waiting',automatic=True)
 assert s.checkpoint()==before
