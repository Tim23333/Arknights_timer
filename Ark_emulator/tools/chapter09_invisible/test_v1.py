"""Generic invisible qualification, permissions and captured flight lifecycle."""
import sys,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_invisible_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE,MANDATORY_FIELDS,project_state,validate_state,eligibility_profile
from ark_sim.tools.replay import replay
from tools.chapter08_bsnake_combat.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
REG=providers();LOG=Path('E:/ArkSimLogs/runs/chapter09_invisible_own')
def make(flag=9,permission=False,force=False,ignore=False,initial=True):
 p=json.loads((ROOT/'packages/campaign/chapter09_consumers/more_ordinary/enemy_1168_dumage.module.v1.json').read_bytes())
 mage=p['entities'][0];mage['components']['selection_state']['can_select_invisible']=permission
 cfg=p['selectors'][0]['eligibility']['parameters']['source_configuration'];cfg['_forceIgnoreCamouflage']=int(force);cfg['_ignoreTargetFree']=int(ignore)
 p['buffs'].append({'id':'buff/invisible/probe','kind':'buff','selection_flags':{'abnormal_flags':[flag]}})
 p['entities'].append({'id':'unit/invisible/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':9000,'def':137,'mres':23}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'buffs':{'initial':['buff/invisible/probe'] if initial else []},'abilities':['ability/invisible/apply','ability/invisible/remove'],'lifecycle':{'policy':'policy/ark_lifecycle'}}})
 for name,op in [('apply','apply_buff'),('remove','remove_buff')]:p['abilities'].append({'id':'ability/invisible/'+name,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':op,'target':'self','buff':'buff/invisible/probe'}}]})
 p['scenarioDraft']={'id':'scene/invisible/probe','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':mage['id'],'instanceAlias':'mage','position':{'row':0,'col':0}},{'definition':'unit/invisible/target','instanceAlias':'target','position':{'row':0,'col':2}}]}
 return p
def run(p,name,split=20,end=30):
 pr=Compiler(providers=REG).compile(p);s=Engine.create(pr,providers=REG,seed=9951);s.advance(split);LOG.mkdir(parents=True,exist_ok=True);cp=LOG/(name+'.checkpoint.json');pin=write_ordered(cp,s.checkpoint());r=Engine.restore(pr,load_bound(cp,pin),providers=REG);s.advance(end-split);r.advance(end-split);head=replay(pr,s.export_replay(),providers=REG);assert s.checkpoint()==r.checkpoint()==head.checkpoint();assert list(s.session.events)==list(r.session.events)==list(head.session.events)
 cleanup=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),'--apply','--run-dir',str(LOG),'--minimum-age-minutes','0'],capture_output=True,text=True);assert cleanup.returncode==0
 out=ROOT/'validation/campaign/chapter09_invisible/own';out.mkdir(parents=True,exist_ok=True);(out/(name+'.json')).write_text(json.dumps({'CP_sha':pin,'CP_and_head_equal':True,'CP_deleted':True,'events':len(s.session.events),'cleanup':json.loads(cleanup.stdout)},indent=2)+'\n');return s
def hits(s):return [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']
@pytest.mark.parametrize('force,ignore',[(False,False),(True,False),(False,True),(True,True)])
def test_native9_neither_forcecamouflage_nor_ignoretargetfree_grants_permission(force,ignore):
 s=run(make(force=force,ignore=ignore),'reject_'+str(force)+str(ignore));assert hits(s)==[];state=project_state(s.ctx,'target',DEFAULT_STATE);assert state['invisible'] and not state['camouflage'] and not state['target_free']
def test_declared_source_detection_permission_hits_native9():assert hits(run(make(permission=True),'detect'))==[(25,231)]
@pytest.mark.parametrize('flag,force,ignore,expected',[(17,False,True,[]),(17,True,False,[(25,231)]),(2,True,False,[]),(2,False,True,[(25,231)])])
def test_independent_old_camouflage_and_targetfree_policies(flag,force,ignore,expected):assert hits(run(make(flag,force=force,ignore=ignore),'old_'+str(flag)+str(force)+str(ignore)))==expected
def test_live_remove_makes_target_selectable_and_cp_during_attack():
 p=make();p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'target','ability':'ability/invisible/remove'}];s=run(p,'remove',20,35);assert len(hits(s))==1;assert 'invisible' not in project_state(s.ctx,'target',DEFAULT_STATE)
def test_apply_after_launch_preserves_captured_projectile_then_stops_future_acquisition():
 p=make(initial=False);p['scenarioDraft']['commands']=[{'at':20,'action':'skill','source':'target','ability':'ability/invisible/apply'}];s=run(p,'captured',21,120);assert hits(s)==[(25,231)]
def test_optional_strict_boolean_fields_and_legacy_complete_defaults():
 assert not {'invisible','can_select_invisible'}&set(DEFAULT_STATE);assert not {'invisible','can_select_invisible'}&MANDATORY_FIELDS;validate_state(DEFAULT_STATE,complete=True)
 for key in ('invisible','can_select_invisible'):
  validate_state({key:False});validate_state({key:True},contribution=True)
  for invalid in (0,1,None,'false'):
   with pytest.raises(ValueError,match='bool required'):validate_state({key:invalid})
def test_explicit_new_false_fields_project_only_when_declared():
 p=make(initial=False);p['entities'][1]['components']['selection_state']['invisible']=False;s=run(p,'explicit_false');st=project_state(s.ctx,'target',DEFAULT_STATE);assert st['invisible'] is False and 'can_select_invisible' not in st
def test_replaceable_reference_sourcefire_policy_can_author_invisible_authorization():
 p=make(ignore=True);rule=p['selectors'][0]['eligibility']['rule'];definition=next(r for r in p['rules'] if r['id']==rule);definition['implementation']['provider']='reference.sourcefire.invisible_policy'
 def policy(inputs,params,context):
  mutable=dict(inputs);states=dict(inputs['selection_states']);states['source']={**states['source'],'can_select_invisible':bool(inputs['parameters']['source_configuration']['_ignoreTargetFree'])};mutable['selection_states']=states;return eligibility_profile(mutable,params,context)
 reg={**REG,'reference.sourcefire.invisible_policy':{'callable':policy,'version':'1'}};s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.advance(30);assert hits(s)==[(25,231)]
def test_detection_buff_source_retirement_removes_permission_before_launch():
 p=make();p['buffs'].append({'id':'buff/invisible/detection','kind':'buff','removal':{'on_source_death':'remove'},'selection_flags':{'can_select_invisible':True}})
 p['selectors'].append({'id':'selector/invisible/mage','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
 p['abilities'] += [{'id':'ability/invisible/grant','kind':'ability','activation':{'mode':'manual'},'selector':'selector/invisible/mage','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/invisible/detection'}}]}, {'id':'ability/invisible/retire','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'retire','target':'self','parameters':{'reason':'withdrawn'}}}]}]
 p['entities'].append({'id':'unit/invisible/donor','kind':'entity','components':{'spatial':{},'abilities':['ability/invisible/grant','ability/invisible/retire'],'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/invisible/donor','instanceAlias':'donor','position':{'row':0,'col':3}})
 p['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'donor','ability':'ability/invisible/grant'},{'at':2,'action':'skill','source':'donor','ability':'ability/invisible/retire'}]
 s=run(p,'permission_owner_retire',1,120);assert not s.ctx.alive('donor');assert project_state(s.ctx,'mage',DEFAULT_STATE)['can_select_invisible'] is False
 # A shot already captured during the permission window retains its lifecycle.
 assert hits(s)==[(26,231)]
def test_immunity_cancels9_before_projection_without_new_false_key():
 p=make();p['entities'][1]['components']['selection_state']['abnormal_immunes']=[9];s=run(p,'invisible_immunity');assert hits(s)==[(25,231)];st=project_state(s.ctx,'target',DEFAULT_STATE);assert 9 not in st['abnormal_flags'] and 'invisible' not in st
def test_finite_invisible_expiry_half_open_removes_projection_immediately():
 p=make();next(b for b in p['buffs'] if b['id']=='buff/invisible/probe')['duration_seconds']=2/30;s=run(p,'invisible_expiry',1,30);assert hits(s)==[(27,231)];assert 'invisible' not in project_state(s.ctx,'target',DEFAULT_STATE)


