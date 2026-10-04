import json,hashlib
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];MODULE=ROOT/'packages/campaign/chapter05_boss/faust/complete.v2.reference.json';BRANCH=ROOT/'packages/campaign/chapter05_boss/faust/branch.reference.json';INPUTS=[];CAPTURES=[]
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=='a686526a89a18afdf4cbfcfb9c9066d302c859e6caee6d904ea5ce67fcf63862'
SUMMON='ability/ch5/faust/summon_ballis'
def fixture(ready=False,far=False,route=False):
 p=json.loads(MODULE.read_bytes());b=json.loads(BRANCH.read_bytes());trap={'id':'unit/peer/registered','kind':'entity','tags':['phase_probe_only'],'components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(trap)
 hero={'id':'unit/peer/hero','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':20000,'atk':100,'def':37,'block_count':1}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'abilities':['ability/peer/phase','ability/peer/retire','ability/peer/immune3'],'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(hero)
 p['buffs'].append({'id':'buff/peer/immune3','kind':'buff','duration_seconds':.1,'active_rule':'rule/ch5/faust/active','selection_flags':{'abnormal_immunes':[3]}})
 p['abilities'].extend([{'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('phase',{'op':'advance_branch','parameters':{'branch':'faust_ballis'}}),('retire',{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}),('immune3',{'op':'apply_buff','target':2,'buff':'buff/peer/immune3'})]])
 src={'definition':'unit/ch5/faust/level0','instanceAlias':'boss','position':{'row':1,'col':1}}
 if ready:src['components']={'ability_timing':{'initial_cooldowns':{SUMMON:0}}}
 if route:src['route']={'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':8},'checkpoints':[]}
 heroitem={'definition':hero['id'],'instanceAlias':'hero','position':{'row':8,'col':32} if far else {'row':1,'col':1 if route else 2}}
 p['scenarioDraft']={'id':'scene/peer/full_faust','ruleset':'ruleset/ark_standard','rules':deepcopy(p['manifest']['metadata']['stage_rules']),'branches':{'faust_ballis':b['program']},'map':{'rows':10,'cols':35},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':25,'capacity':99}},'initialEntities':[src,heroitem]+[{'definition':trap['id'],'instanceAlias':key,'active':False,'registration_key':key,'position':{'row':4,'col':i+1}} for i,key in enumerate(b['required_registrations'])]}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=51577)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def exact(s,tmp,n):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(n);r.advance(n);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_actual15second_summon_beats_normal_then17second_critical_on_shared150clock(tmp_path):
 s=make(fixture());s.advance(476);exact(s,tmp_path,169);capture(s,'source_priorities')
 starts=[(e['time'],e['payload']['ability']) for e in ev(s,'ability.started') if e['payload']['source']==2]
 assert starts==[(0,'ability/ch5/faust/normal'),(150,'ability/ch5/faust/normal'),(300,'ability/ch5/faust/normal'),(450,SUMMON),(600,'ability/ch5/faust/critical')]
 assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted')]==[(43,963),(193,963),(343,963),(643,1963)]
 assert [e['time'] for e in ev(s,'entity.activated')]==[477] and s.ctx.branches.state()['faust_ballis']['cursor']==1
 assert s.ctx.get('boss',('runtime','cooldowns',SUMMON))==1400
def test_exact_native7_phases_activate10_existing_ids_and_exhaustion_stops_empty_cast(tmp_path):
 b=json.loads(BRANCH.read_bytes());assert len(b['program']['phases'])==7 and len(b['required_registrations'])==10
 s=make(fixture(far=True));ids={k:s.session.world.resolve(k) for k in b['required_registrations']}
 for t in range(7):s.submit({'action':'skill','source':'hero','ability':'ability/peer/phase'},at=t)
 s.advance(4);exact(s,tmp_path,526);capture(s,'seven_phase_closure')
 assert s.ctx.branches.state()['faust_ballis']['cursor']==7 and not s.ctx.branches.facts()['faust_ballis']['available']
 assert len(ev(s,'entity.activated'))==10 and all(s.ctx.active(ref) and s.session.world.resolve(k)==ref for k,ref in ids.items())
 assert not any(e['payload']['source']==2 for e in ev(s,'ability.started')) and not ev(s,'damage.accepted')
 assert len([e for e in s.session.world.entities() if e['definition_id']=='unit/peer/registered'])==10
def test_requester_exit_before27_cancels_uncommitted_summon_and_leaves_all_registrations_dormant(tmp_path):
 s=make(fixture(True,far=True));s.submit({'action':'skill','source':'hero','ability':'ability/peer/retire'},at=10);s.advance(5);exact(s,tmp_path,51);capture(s,'cancel_windup')
 assert not s.ctx.active('boss') and s.ctx.branches.state()['faust_ballis']['cursor']==0
 assert not ev(s,'entity.activated') and not [t for t in s.session.scheduler.pending if t['kind']=='domain.branch.action']
def test_dynamic_blockfree_immunity_boundary_during_real_summon_preserves_cast_and_phase_clock(tmp_path):
 s=make(fixture(True,route=True));s.submit({'action':'skill','source':'hero','ability':'ability/peer/immune3'},at=5);s.advance(7)
 assert s.ctx.spatial.blocked_by('boss')==s.session.world.resolve('hero');h=write_ordered(tmp_path/'immune.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'immune.json',h));s.advance(1);r.advance(1)
 assert s.ctx.spatial.blocked_by('boss') is None and 3 in s.ctx.spatial.selection_state('boss',DEFAULT_STATE)['abnormal_flags']
 s.advance(23);r.advance(23);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'dynamic_summon')
 assert [e['time'] for e in ev(s,'entity.activated')]==[27] and s.ctx.get('boss',('runtime','next_attack'))==150
