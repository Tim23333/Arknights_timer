"""Independent endpoints: public stat probes, cast claims and output validation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m17_peer import probe as h
from copy import deepcopy
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.adapters.api import implementation_digest
def director(p,effects,at=50):
    p['entities'].append({'id':'unit/peer_director','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100,'atk':0,'def':0,'mres':0}},
      'spatial':{},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'abilities':['ability/peer_director']}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer_director','instanceAlias':'director','position':{'row':0,'col':0}})
    p['abilities'].append({'id':'ability/peer_director','kind':'ability','activation':{'mode':'manual','on_start':effects},'timeline':[]})
def C4_hit_time_source_stat():
    p=h.scene();p['buffs'].append({'id':'buff/peer_atk100','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]})
    director(p,[{'op':'apply_buff','target':2,'buff':'buff/peer_atk100'}]);s=h.make(p)
    s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0)
    s.submit({'action':'skill','source':'director','ability':'ability/peer_director'},at=50);s.advance(115)
    amounts=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']
    assert amounts==[926,926],repr(amounts) # explicit child at_hit: (native470 + probe100)*1.8 - inputDEF100
    assert s.ctx.resources.current('target1','hp')==4074;h.roundtrip(s)
def normal_cast_claim_two_frames_multiple_pending_groups():
    p=deepcopy(h.fixture(h.read(h.PACKAGE,h.PIN),positions=((3,5),)))
    p['entities'][0]['components']['resources']['sp']={'initial':0,'capacity':20,'recovery_rule':'rule/peer_sp',
      'recovery':{'mode':'event','event':'attack.accepted','owner_role':'source','amount':1}}
    p['rules'].append({'id':'rule/peer_sp','kind':'calculation_rule','contract':'resource.recovery',
       'implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
    s=h.make(p);s.advance(36)
    assert [e['time'] for e in s.session.events if e['type']=='damage.accepted']==[21,35]
    assert [e['time'] for e in s.session.events if e['type']=='attack.accepted']==[21]
    assert s.ctx.resources.current('w','sp')==1
    s.advance(120);assert [e['time'] for e in s.session.events if e['type']=='damage.accepted']==[21,35,141,155]
    assert [e['time'] for e in s.session.events if e['type']=='attack.accepted']==[21,141] and s.ctx.resources.current('w','sp')==2
    assert len(s.ctx.get('w',('runtime','attack_recovery_claims')))==1
    h.roundtrip(s)
def wrong_launch_trajectory_output_must_not_create_jobs():
    p=h.scene();p['rules'].append({'id':'rule/peer_missing_reached','kind':'calculation_rule','contract':'projectile.trajectory',
      'implementation':{'type':'expression','expression':"{'position':inputs.positions[0].position,'motion_state':{}}"}})
    p['projectiles'][1]['motion']['rule']='rule/peer_missing_reached';s=h.make(p);before=s.checkpoint()
    ability=s.program.definitions['ability/chapter01_w_c4_0'];effect=thaw(ability['timeline'][0]['effect'])
    try:s.ctx.projectiles.launch('w','target0',effect,thaw(ability),{},None)
    except ValueError:pass
    else:raise AssertionError('launch accepted trajectory without reached; created invalid persistent state/jobs')
    assert s.checkpoint()==before
def invalid_callback_rolls_back_and_wait_claim_preserved():
    p=h.scene();p['projectiles'][1]['on_invalid']=[{'op':'modify_resource','resource':'missing','delta':1}]
    s=h.make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);s.advance(20)
    instances=s.ctx.get('system/battle',('projectiles','instances'));key=next(iter(instances));cp=s.checkpoint()
    try:s.ctx.projectiles.expire(s.session,{'projectile':key})
    except ValueError:pass
    else:raise AssertionError('bad on_invalid resource accepted')
    assert s.checkpoint()==cp and s.ctx.get('system/battle',('projectiles','instances',key,'state'))=='active'
    assert next(iter(s.ctx.get('w',('runtime','casts')).values()))['pending_projectiles']==1
def moving_captured_target_never_retargets_nearer_neighbor():
    p=h.fixture(h.read(h.PACKAGE,h.PIN),positions=((3,4),(4,3)))
    target=next(e for e in p['entities'] if e['id']=='unit/chapter01_w_target');target['components']['abilities']=['ability/move_trace']
    p['abilities'].append({'id':'ability/move_trace','kind':'ability','activation':{'mode':'manual','on_start':[
       {'op':'move','target':'source','position':{'row':3,'col':5}}]},'timeline':[]})
    s=h.make(p);s.submit({'action':'skill','source':'target0','ability':'ability/move_trace'},at=10);s.advance(36)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[21,35]
    assert all(e['payload']['target']==s.session.world.resolve('target0') for e in hits) and s.ctx.resources.current('target1','hp')==5000
    h.roundtrip(s)
if __name__=='__main__':
    cases=[];start=implementation_digest()
    for name,fn in [('C4_hit_time_source',C4_hit_time_source_stat),('normal_claim_groups',normal_cast_claim_two_frames_multiple_pending_groups),
      ('launch_output_preflight',wrong_launch_trajectory_output_must_not_create_jobs),('invalid_callback_rollback',invalid_callback_rolls_back_and_wait_claim_preserved),
      ('moving_capture_identity',moving_captured_target_never_retargets_nearer_neighbor)]:
        h.LAST=None
        try:fn();c={'case':name,'result':'passed'}
        except Exception as e:c={'case':name,'result':'failed','error':repr(e)}
        if h.LAST is not None:
            s=h.LAST;c.update({'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'initial_scenario':thaw(s.program.scenario),
               'commands':s.export_replay(),'snapshot':s.snapshot(),'events':[thaw(e) for e in s.session.events]})
        cases.append(c)
    out=h.ROOT/'validation/campaign/m17_peer_extended_initial.json';out.write_text(json.dumps({'core_start':start,'core_end':implementation_digest(),
      'runtime_module':h.ark_sim.__file__,'actual_files_before_decode':h.LOADED,'formal_approval':False,'cases':cases},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core':start,'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))
