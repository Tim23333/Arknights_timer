"""Independent public-command checks of roster/qualification/decision wiring."""
import sys,json,os,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=Path(os.environ.get('ARKSIM_PEER_ROOT',str(ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate')))
sys.path.insert(0,str(RUNTIME))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
DEFAULTS=dict(side=0,motion=1,category=1,profession=0,unit_type=1,abnormal_flags=[],abnormal_combos=[],target_free_flags=[],target_free_combos=[],target_free=False,ally_target_free=False,heal_free=False,camouflage=False,can_select_camouflage=False)

def fixture():
 raw=json.loads((ROOT/'validation/campaign/advanced_selector_source_audit.json').read_bytes())['actual_selectors'][0]['raw']
 def unit(name,side):
  return {'id':'unit/'+name,'kind':'entity','tags':['target'] if side==0 else [],'components':{'selection_state':{'side':side},'attributes':{'base':{'max_hp':100,'atk':12,'def':0,'mres':0,'move_speed':3,'attack_interval':1,'attack_speed_ratio':1}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'deployable':{'base_cost':2,'capacity':1,'terrain':'ground','cooldown_seconds':0}}}
 source,target=unit('source',1),unit('target',0)
 source['components'].update(abilities=['ability/fire'],behavior={'machine':'behavior/decision'})
 target['components']['abilities']=['ability/hide','ability/escape']
 return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[source,target],
 'selectors':[{'id':'selector/target','kind':'selector','region':{'type':'radius','radius':1},'filters':[{'tag':'target'},{'state':'alive'}],'ordering':'random','limit':1,'parameters':{'random_stream':'imp'},'eligibility':{'rule':'rule/qualify','parameters':{'source_configuration':raw,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULTS)}}}],
 'rules':[{'id':'rule/qualify','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}}],
 'buffs':[{'id':'buff/hide','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[2]}}],
 'abilities':[{'id':'ability/fire','kind':'ability','selector':'selector/target','activation':{'mode':'automatic_attack'},'duration_seconds':.1,'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true'}}]},
 {'id':'ability/hide','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/hide'}]},'timeline':[]},
 {'id':'ability/escape','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':5}}]},'timeline':[]}],
 'behaviors':[{'id':'behavior/decision','kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':'selector/target'}],'cast_groups':[{'key':'normal','abilities':['ability/fire']}],'parameters':{'target_key':'normal','stop_on_target':True,'stop_cast_groups':['normal']}}]}}],
 'scenarioDraft':{'id':'scenario/peer','ruleset':'ruleset/ark_standard','objectives':{},'resources':{'dp':{'initial':10,'capacity':10}},'map':{'rows':2,'cols':6},'roster':['unit/source'],'initialEntities':[{'definition':'unit/source','instanceAlias':'source','position':{'row':0,'col':0},'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':5},'checkpoints':[]}},{'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':1}}]}}

INPUTS=[]
def make(p=None):
 p=deepcopy(p or fixture())
 if RUNTIME.name=='campaign_m23_roster_candidate':
  # Standalone membership review does not require later M25 components.
  for e in p['entities']:e['components'].pop('selection_state',None)
  for b in p['buffs']:b.pop('selection_flags',None)
 raw=json.dumps(p,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest()
 INPUTS.append({'sha256':digest,'bytes':len(raw),'seed':2603,'document':json.loads(raw)})
 return Engine.create(Compiler().compile(json.loads(raw)),seed=2603)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_qualification_reject_moves_then_half_open_attacks():
 s=make();s.submit({'action':'skill','source':'target','ability':'ability/hide'},at=0);s.advance(3)
 assert not [e for e in s.session.events if e['type']=='damage.accepted']
 assert abs(s.ctx.get('source',('spatial','position'))['col']-.3)<1e-8
 s.advance(1);hits=[e for e in s.session.events if e['type']=='damage.accepted']
 assert len(hits)==1 and hits[0]['time']==3 and hits[0]['payload']['amount']==12
 assert abs(s.ctx.get('source',('spatial','position'))['col']-.3)<1e-8;exact(s)

def test_pure_eligible_filtered_without_rng_or_events():
 p=fixture();p['entities'][1]['components']['selection_state']['target_free']=True;s=make(p);cp=s.checkpoint()
 assert s.ctx.spatial.eligible('source','selector/target')==[];assert s.checkpoint()==cp
 assert s.ctx.spatial.select('source','selector/target')==[]
 assert s.session.random.snapshot()==cp['kernel']['random']

def test_geometry_outside_qualifying_actor_never_stops():
 p=fixture();p['scenarioDraft']['initialEntities'][1]['position']['col']=5;s=make(p);s.advance(3)
 assert abs(s.ctx.get('source',('spatial','position'))['col']-.3)<1e-8
 assert not [e for e in s.session.events if e['type']=='ability.started'];exact(s)

def test_custom_qualification_shared_by_decision_and_packet():
 p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':"{'accepted':False,'reason':'peer_reject'}"};s=make(p);s.advance(3)
 assert not [e for e in s.session.events if e['type']=='ability.started'];assert s.ctx.resources.current('target','hp')==100;exact(s)

@pytest.mark.parametrize('roster',[[],['unit/source']])
def test_public_deploy_rejected_keeps_existing_actor_and_dp(roster):
 p=fixture();p['scenarioDraft']['roster']=roster
 # Remove combat dependency from this deployment-only fixture.
 p['entities'][0]['components'].pop('behavior');p['entities'][0]['components']['abilities']=[]
 p['scenarioDraft']['initialEntities'][1].update(active=False,registration_key='peer-npc')
 s=make(p);s.submit({'action':'deploy','definition':'unit/target','alias':'duplicate','position':{'row':1,'col':0}},at=0);s.advance(1)
 assert len([e for e in s.session.events if e['type']=='command.rejected'])==1
 assert len([e for e in s.session.world.entities() if e['definition_id']=='unit/target'])==1
 assert s.ctx.resources.current('system/battle','dp')==10;exact(s)

def test_absent_roster_stays_open_and_cost_actual():
 p=fixture();p['scenarioDraft'].pop('roster');p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][1:]
 p['scenarioDraft']['initialEntities'][0].update(active=False,registration_key='peer-npc');s=make(p)
 s.submit({'action':'deploy','definition':'unit/target','alias':'new','position':{'row':1,'col':0}},at=0);s.advance(1)
 assert len([e for e in s.session.events if e['type']=='command.accepted'])==1
 assert s.ctx.resources.current('system/battle','dp')==8;exact(s)

def test_bad_qualification_rolls_back_payment_and_random():
 p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':'1/0'};s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):
  with s.session.atomic():s.ctx.behavior.plan('source')
 assert s.checkpoint()==before

def test_owned_spawn_not_public_roster_but_real_cost_and_ownership():
 p=fixture();p['entities'][0]['components'].pop('behavior');p['entities'][0]['components']['abilities']=['ability/summon']
 p['abilities'].append({'id':'ability/summon','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'spawn','definition':'unit/target','owner':'source','parameters':{'position_from_payload':True,'max_owned':1}}]},'timeline':[]})
 p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];s=make(p)
 s.submit({'action':'skill','source':'source','ability':'ability/summon','payload':{'position':{'row':1,'col':0}}},at=0);s.advance(1)
 children=[e for e in s.session.world.entities() if e['definition_id']=='unit/target']
 assert len(children)==1 and children[0]['components']['ownership']['owner']==s.session.world.resolve('source')
 exact(s)

def test_no_config_legacy_does_not_infer_target_free_permission():
 p=fixture();p['selectors'][0].pop('eligibility');p['entities'][1]['components']['selection_state']['target_free']=True;s=make(p)
 before=s.checkpoint();assert s.ctx.spatial.eligible('source','selector/target')==[s.session.world.resolve('target')];assert s.checkpoint()==before
 s.advance(1);assert s.ctx.resources.current('target','hp')==88;exact(s)

def test_standalone_qualification_half_open_public_packet():
 p=fixture();p['entities'][0]['components'].pop('behavior');p['abilities'][0]['activation']={'mode':'manual','on_start':[{'op':'damage','damage_type':'true'}]};p['abilities'][0]['timeline']=[];p['abilities'][0]['duration_seconds']=0
 s=make(p);s.submit({'action':'skill','source':'target','ability':'ability/hide'},at=0)
 s.submit({'action':'skill','source':'source','ability':'ability/fire'},at=1)
 s.submit({'action':'skill','source':'source','ability':'ability/fire'},at=3);s.advance(4)
 hits=[e for e in s.session.events if e['type']=='damage.accepted']
 assert len(hits)==1 and hits[0]['time']==3 and hits[0]['payload']['amount']==12;exact(s)

def test_standalone_heal_free_uses_ability_context_readonly():
 p=fixture();p['entities'][0]['components'].pop('behavior');p['entities'][1]['components']['selection_state']['heal_free']=True;s=make(p)
 selector=s.program.definitions['selector/target'];before=s.checkpoint()
 assert s.ctx.spatial.qualifies('source','target',selector)
 assert not s.ctx.spatial.qualifies('source','target',selector,{'parameters':{'healing':True}})
 assert s.checkpoint()==before
