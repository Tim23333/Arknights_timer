"""Generic status removal updates membership atomically, not a character branch."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.domains.providers import BUILTIN_PROVIDERS
INPUTS=[]
def fixture():
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/emitter','kind':'entity','tags':['emitter'],'components':{'attributes':{'base':{'max_hp':100,'atk':0,'def':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'buffs':{'initial':['buff/parent']},'abilities':['ability/parent_off','ability/retire']}},{'id':'unit/target','kind':'entity','tags':['target'],'components':{'attributes':{'base':{'max_hp':10000,'def':100,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{}}},{'id':'unit/director','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':1000,'def':0,'mres':0}},'resources':{'hp':{'initial':100,'capacity':100}},'spatial':{},'abilities':['ability/off','ability/on','ability/shot']}}],
 'selectors':[{'id':'selector/owner','kind':'selector','region':{'type':'all'},'filters':[{'tag':'emitter'}],'limit':1},{'id':'selector/target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'target'}],'limit':1},{'id':'selector/aura','kind':'selector','region':{'type':'all'},'filters':[{'tag':'target'}],'eligibility':{'rule':'rule/source_status','parameters':{'source_configuration':{'_targetSide':7,'_targetMotion':3,'_targetCategory':7,'_ignoreTargetFree':0,'_onlyIgnoreSomeOfTargetFreeCase':0,'_excludeSomeAbnormalFlags':0,'_needProfessionMask':0,'_ignoreAllyTargetFree':0,'_ignoreHealFree':0,'_ignoreMotionMode':0,'_forceIgnoreCamouflage':0,'_checkUnitType':0},'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':{'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}}}}],
 'rules':[{'id':'rule/source_status','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'expression','expression':"{'accepted':12 not in inputs.selection_states.source.abnormal_flags,'reason':'generic_source_status'}"}}],
 'buffs':[{'id':'buff/parent','kind':'buff','aura':{'selector':'selector/aura','buff':'buff/child'}},{'id':'buff/child','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':300}]},{'id':'buff/off','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[12]}}],
 'abilities':[{'id':'ability/off','kind':'ability','selector':'selector/owner','parameters':{'blocks_attacks':False},'activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/off'}]},'timeline':[]},{'id':'ability/on','kind':'ability','selector':'selector/owner','parameters':{'blocks_attacks':False},'activation':{'mode':'manual','on_start':[{'op':'remove_buff','buff':'buff/off'}]},'timeline':[]},{'id':'ability/shot','kind':'ability','selector':'selector/target','parameters':{'blocks_attacks':False},'activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]},{'id':'ability/parent_off','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':'source','buff':'buff/parent'}]},'timeline':[]},{'id':'ability/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]},'timeline':[]}],
 'scenarioDraft':{'id':'scene/synchronous_remove','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3},'initialEntities':[{'definition':'unit/emitter','instanceAlias':'emitter','position':{'row':0,'col':0}},{'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':1}},{'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':2}}]}}
def make(p,providers=None):
 raw=json.dumps(p,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':4201,'document':json.loads(raw)});return Engine.create(Compiler(providers=providers).compile(json.loads(raw)),seed=4201,providers=providers)
def cmd(s,who,ability,t):s.submit({'action':'skill','source':who,'ability':ability},at=t)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_source_status_manual_remove_before_sameframe_settlement():
 s=make(fixture());cmd(s,'director','ability/off',0);cmd(s,'director','ability/on',1);cmd(s,'director','ability/shot',1);s.advance(2)
 assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[600];exact(s)
def test_expiry_half_open_source_status_restore():
 s=make(fixture());cmd(s,'director','ability/off',0);cmd(s,'director','ability/shot',2);cmd(s,'director','ability/shot',3);s.advance(4)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(2,900),(3,600)];exact(s)
def test_parent_remove_never_reapplies_child_during_nested_cleanup():
 s=make(fixture());cmd(s,'emitter','ability/parent_off',0);cmd(s,'director','ability/shot',0);s.advance(1)
 assert s.ctx.get('target',('buffs','instances'))==[] and s.ctx.get('emitter',('buffs','instances'))==[]
 assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[900]
 assert s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling;exact(s)
def test_source_retire_cleans_owned_children_synchronously():
 p=fixture();p['entities'][0]['components']['lifecycle']={'policy':'policy/ark_lifecycle'};s=make(p);cmd(s,'emitter','ability/retire',0);cmd(s,'director','ability/shot',0);s.advance(1)
 assert s.ctx.get('target',('buffs','instances'))==[] and not s.ctx.alive('emitter');assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[900];exact(s)
def test_remove_unknown_buff_is_readonly_no_reconcile_trace():
 s=make(fixture());before=s.checkpoint();assert s.ctx.buffs.remove('emitter','buff/not_applied')==0;assert s.checkpoint()==before
def fail_reconcile(inputs,parameters,context):
 if any(i['definition']=='buff/trip' for i in inputs['source']['components']['buffs']['instances']):raise RuntimeError('deliberate reconcile failure')
 return [x['id'] for x in inputs['candidates']]
fail_reconcile.version='m42-peer-selector-fail-v1'
def test_failed_remove_reconciliation_rolls_back_and_guards_recover():
 p=fixture();p['selectors'][2]['provider']='peer.fail';p['buffs'].append({'id':'buff/trip','kind':'buff'});p['buffs'][2]['on_remove']=[{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','resource':'hp','delta':-1}]},{'op':'apply_buff','buff':'buff/trip'}]
 providers={**BUILTIN_PROVIDERS,'peer.fail':fail_reconcile};s=make(p,providers);cmd(s,'director','ability/off',0);s.advance(1);before=s.checkpoint()
 with pytest.raises(RuntimeError,match='deliberate reconcile'):s.ctx.buffs.remove('emitter','buff/off')
 assert s.checkpoint()==before and s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling
 # Same real input stays valid after rollback; no lingering guard skips evaluation.
 with pytest.raises(RuntimeError,match='deliberate reconcile'):s.ctx.buffs.remove('emitter','buff/off')
 assert s.checkpoint()==before and s.ctx.buffs._removal_depth==0
