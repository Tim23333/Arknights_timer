"""Persist additional public silence, source Frozen and target-death CP/head probes."""
import json,hashlib
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter06_units.snmage.test_module import package,controlled_package,deploy,sp,ready,flags,damage
from tools.chapter06_units.snmage.build_module import OUT,COLD,CORE
from tools.chapter06.cold.policies import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations,export_events

def target_dead_package():
    p=package(initial_sp=2)
    p['selectors'].append({'id':'selector/test/snmage/target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/test/snmage/killtarget','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/snmage/target','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    p['entities'].append({'id':'unit/test/snmage/killtarget','kind':'entity','tags':['test_controller'],'components':{'attributes':{'base':{'max_hp':10,'atk':10000}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/test/snmage/killtarget']}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/test/snmage/killtarget','instanceAlias':'controller','position':{'row':1,'col':7}})
    return p
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))

@pytest.mark.parametrize('name,cp_tick,end,expected_hp', [('silence',25,145,9400),('source_frozen',3,175,9700),('target_dead',21,31,0)])
def test_public_control_durable_full_head_evidence(name,cp_tick,end,expected_hp):
    package_data=target_dead_package() if name=='target_dead' else controlled_package(cold=name=='source_frozen')
    dest=OUT/'control_evidence';dest.mkdir(parents=True,exist_ok=True);p=dest/(name+'.probe.json');write(p,package_data)
    reg=providers();program=Compiler(providers=reg).compile(p,packages=[COLD]);s=Engine.create(program,seed=6268,providers=reg)
    if name=='silence':
        s.submit({'action':'skill','source':'controller','ability':'ability/test/snmage/silence'},at=0);deploy(s,at=1)
    elif name=='source_frozen':
        for tick in (0,1):s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=tick)
        deploy(s,at=2)
    else:
        deploy(s);s.submit({'action':'skill','source':'controller','ability':'ability/test/snmage/killtarget'},at=22)
    s.session.advance(cp_tick);middle={'time':cp_tick,'sp':sp(s),'ready_count':len(ready(s)),'target_flags':flags(s),'damage':damage(s)}
    checkpoint=dest/(name+'.checkpoint.json');pin=write_ordered(checkpoint,s.checkpoint());restored=Engine.restore(program,load_bound(checkpoint,pin),providers=reg)
    s.session.advance(end-cp_tick);restored.session.advance(end-cp_tick)
    rp=dest/(name+'.replay.json');write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
    obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
    actual={'target_hp':s.ctx.resources.current('target','hp'),'target_alive':s.ctx.alive('target'),'sp':sp(s),'ready_count':len(ready(s)),'target_flags':flags(s),'damage':damage(s)}
    report={'schema':'ark-sim/ch6-snmage-public-control-probe/v1','name':name,'core':CORE,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'middle':middle,'actual':actual,'expected_target_hp':expected_hp,'end':end,'package':{'path':str(p),'sha256':sha(p)},'checkpoint':{'path':str(checkpoint),'sha256':pin,'tick':cp_tick,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(dest/(name+'.events.jsonl'),s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':obs==cp_obs,'replay_equal':obs==rp_obs,'required_retained_source_payload_still_open':True,'whole_stage_executed':False,'client_verified':False}
    write(dest/(name+'.report.json'),report)
    assert actual['target_hp']==expected_hp and sp(s)==0 and not ready(s)
    assert obs==cp_obs==rp_obs
    if name=='target_dead':assert flags(s)==[] and not [e for e in s.session.events if e['type']=='attack.accepted']
    else:assert 23 in flags(s)
