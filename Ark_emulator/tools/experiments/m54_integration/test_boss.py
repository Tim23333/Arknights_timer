import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[]
def fixture(melee=False):
 p=json.loads((ROOT/'packages/campaign/chapter02_behavior/reference50/skulsr.model.json').read_bytes());uid=p['entities'][0]['id']
 target={'id':'unit/probe','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'def':100,'mres':0,'block_count':1 if melee else 0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 if melee:target['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}
 fly=deepcopy(target);fly['id']='unit/fly';fly['tags']=['player','flying'];fly['components']['attributes']['base']['def']=200;fly['components']['selection_state']['motion']=2
 director={'id':'unit/director','kind':'entity','tags':['director'],'components':{'spatial':{},'abilities':['ability/wound','ability/restore']}}
 p['entities'] += [target,fly,director];p['selectors'].append({'id':'selector/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
 p['abilities'] += [{'id':'ability/wound','kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'modify_resource','resource':'hp','value':5249}]},'parameters':{'blocks_attacks':False},'timeline':[]},{'id':'ability/restore','kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'modify_resource','resource':'hp','value':5250}]},'parameters':{'blocks_attacks':False},'timeline':[]}]
 initial=[{'definition':uid,'instanceAlias':'boss','position':{'row':2,'col':0},'route':{'motionMode':0,'startPosition':{'row':2,'col':0},'endPosition':{'row':2,'col':7},'checkpoints':[]}},{'definition':'unit/probe','instanceAlias':'main','position':{'row':2,'col':1}},{'definition':'unit/director','instanceAlias':'director','position':{'row':5,'col':7}}]
 if not melee:initial += [{'definition':'unit/fly','instanceAlias':'fly','position':{'row':3,'col':2}},{'definition':'unit/probe','instanceAlias':'outside','position':{'row':3,'col':2.5}}]
 if melee:
  initial[1]['position']={'row':2,'col':0}
  p['buffs'].append({'id':'buff/fixture/preblock','kind':'buff','duration_seconds':1/30,'control':{'attack':False,'abilities':False}})
  initial[0]['components']={'buffs':{'initial':['buff/fixture/preblock']}}
 p['scenarioDraft']={'id':'scene/skulsr_reference','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':6,'cols':8},'initialEntities':initial};return p
def make(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':4650,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=4650)
def exact(s,tmp_path):
 pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_automatic_f14_f17_dual_packet_grid_splash_air_and_def_phase(tmp_path):
 s=make(fixture());s.advance(24);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[20,20,23,23]
 assert [e['payload']['amount'] for e in hits]==pytest.approx([159.99999046325684,59.99999046325684,209.99999046325684,159.99999046325684])
 assert s.ctx.resources.current('outside','hp')==10000
 assert len([e for e in s.session.events if e['type']=='attack.accepted'])==1
 assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[14,17]
 exact(s,tmp_path)
def test_actual_blocked_melee_f53_no_grenade_or_debuff(tmp_path):
 s=make(fixture(True));s.advance(55);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in hits]==[(54,900)]
 assert not any(e['type']=='projectile.launched' for e in s.session.events)
 assert not any(e['type']=='buff.applied' and e['payload'].get('buff')=='buff/chapter02/skulsr_defdown' for e in s.session.events);exact(s,tmp_path)
def test_hp_strict50_enter_and_exact50_restore(tmp_path):
 p=fixture(True);p['entities'][0]['components']['resources']['hp']['initial']=5250;s=make(p);s.advance(1);assert s.ctx.resources.current('boss','mode')==0
 s.submit({'action':'skill','source':'director','ability':'ability/wound'},at=2);s.advance(3);assert s.ctx.resources.current('boss','mode')==1
 s.submit({'action':'skill','source':'director','ability':'ability/restore'},at=6);s.advance(3);assert s.ctx.resources.current('boss','mode')==0;exact(s,tmp_path)

def test_ranged_phase_damage_below50_is150percent_and_restores(tmp_path):
 p=fixture();p['entities'][0]['components']['resources']['hp']['initial']=5249
 # Initial phase is established by a recorded wound event before ranged casting.
 p['buffs'].append({'id':'buff/fixture/phase_ready','kind':'buff','duration_seconds':1/30,'control':{'attack':False}})
 p['scenarioDraft']['initialEntities'][0]['components']={'buffs':{'initial':['buff/fixture/phase_ready']}}
 s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/wound'},at=0);s.advance(25)
 assert s.ctx.resources.current('boss','mode')==1
 hits=[e for e in s.session.events if e['type']=='damage.accepted']
 assert [e['payload']['amount'] for e in hits]==pytest.approx([289.99998569488525,189.99998569488525,339.99998569488525,289.99998569488525])
 assert [e['time'] for e in hits]==[21,21,24,24];exact(s,tmp_path)

def support_probes(p):
 director=next(u for u in p['entities'] if u['id']=='unit/director');director['components']['attributes']={'base':{'atk':1000}};director['components']['abilities'] += ['ability/retire_boss','ability/test_def']
 p['entities'][1]['tags'].append('testmain')
 p['selectors'].append({'id':'selector/testmain','kind':'selector','region':{'type':'all'},'filters':[{'tag':'testmain'}],'limit':1})
 p['abilities'] += [{'id':'ability/retire_boss','kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'parameters':{'blocks_attacks':False},'timeline':[]},{'id':'ability/test_def','kind':'ability','selector':'selector/testmain','activation':{'mode':'manual'},'parameters':{'blocks_attacks':False},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'physical','scale':1}}]}]
 return p

def test_refresh5seconds_def_half_open_actual_hit_after_source_exit(tmp_path):
 p=support_probes(fixture());p['scenarioDraft']['initialEntities']=[x for x in p['scenarioDraft']['initialEntities'] if x['instanceAlias']!='outside'];s=make(p)
 s.submit({'action':'skill','source':'director','ability':'ability/retire_boss'},at=25)
 s.submit({'action':'skill','source':'director','ability':'ability/test_def'},at=172);s.submit({'action':'skill','source':'director','ability':'ability/test_def'},at=173);s.advance(175)
 hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==s.session.world.resolve('director')]
 assert [(e['time'],e['payload']['amount']) for e in hits]==[(172,950),(173,900)]
 exact(s,tmp_path)

def test_source_withdraw_after_f14_retains_first_projectile_cancels_f17(tmp_path):
 p=support_probes(fixture());s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/retire_boss'},at=16);s.advance(25)
 assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[14]
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[20,20]
 assert [e['payload']['amount'] for e in hits]==pytest.approx([159.99999046325684,59.99999046325684]);exact(s,tmp_path)

def test_three_second_cooldown_next_cast90_and_refreshed_def(tmp_path):
 s=make(fixture());s.advance(114)
 assert [e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']=='ability/skulsr_attack_0']==[0,90]
 assert [e['time'] for e in s.session.events if e['type']=='attack.accepted']==[20,110]
 hits=[e for e in s.session.events if e['type']=='damage.accepted']
 assert [e['time'] for e in hits]==[20,20,23,23,110,110,113,113]
 assert [e['payload']['amount'] for e in hits[4:]]==pytest.approx([209.99999046325684,159.99999046325684,209.99999046325684,159.99999046325684]);exact(s,tmp_path)

def test_flying_can_be_splash_but_not_native_ground_primary_empty_set_moves(tmp_path):
 p=fixture();p['scenarioDraft']['initialEntities']=[x for x in p['scenarioDraft']['initialEntities'] if x['instanceAlias'] not in ['main','outside']]
 s=make(p);before=s.session.random.snapshot();s.advance(10)
 assert not any(e['type'] in ['attack.accepted','projectile.launched'] for e in s.session.events)
 assert s.ctx.resources.current('fly','hp')==10000 and s.ctx.get('boss',('spatial','position'))['col']>0
 assert s.session.random.snapshot()['samples']==before['samples'];exact(s,tmp_path)

def test_primary_retirement_uses_explicit_cancel_profile_not_ghost_splash(tmp_path):
 p=support_probes(fixture());p['scenarioDraft']['initialEntities']=[x for x in p['scenarioDraft']['initialEntities'] if x['instanceAlias']!='outside']
 director=next(u for u in p['entities'] if u['id']=='unit/director');director['components']['abilities'].append('ability/retire_main');p['abilities'].append({'id':'ability/retire_main','kind':'ability','selector':'selector/testmain','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'timeline':[]})
 s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/retire_main'},at=16);s.advance(25)
 assert not any(e['type']=='damage.accepted' for e in s.session.events)
 assert s.ctx.resources.current('fly','hp')==10000
 assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[14,17]
 assert [e['time'] for e in s.session.events if e['type']=='projectile.invalid' and e['payload'].get('reason')=='target_invalid']==[16,18]
 exact(s,tmp_path)
