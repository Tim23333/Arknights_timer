"""Persist crossbow public retained/captured-target/status/selection clocks CP/head."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
DEST=ROOT/'packages/campaign/chapter06_units/snbow/evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter06_units.snbow.test_module import package,deploy,cold,packets,hp
    from tools.chapter06_units.snbow.build_module import CORE,COLD,OUT
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    tests=OUT/'author.tests.json';passed=json.loads(tests.read_bytes())
    if implementation_digest()!=CORE or not passed['passed'] or passed['implementation_after']!=CORE:raise ValueError('Frozen author/runtime required')
    paths=list((ROOT/'tools/chapter06_units/snbow').glob('*.py'))+[OUT/'model.json',OUT/'source.reference.json',tests,COLD,ROOT/'tools/chapter06/cold/policies.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in paths};DEST.mkdir(parents=True,exist_ok=True);records=[]
    cases=['target_frozen','source_dead','source_dead_frozen_policy','target_invalid','captured_selection','source_cold']
    for name in cases:
        p=package(two=name=='captured_selection')
        if name=='source_cold':p['entities'][0]['tags'].append('cold_receiver');p['entities'][1]['tags'].remove('cold_receiver')
        path=DEST/(name+'.probe.json');write(path,p);reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6266,providers=reg)
        if name=='source_cold':cold(s,(0,));deploy(s,at=1)
        else:deploy(s)
        if name in ('target_frozen','source_dead_frozen_policy'):cold(s)
        if name.startswith('source_dead'):s.submit({'action':'skill','source':'target','ability':'ability/test/snbow/kill'},at=13)
        if name=='target_invalid':s.submit({'action':'withdraw','source':'target'},at=13)
        if name=='captured_selection':deploy(s,'other',at=5,col=1,row=1)
        s.session.advance(13);cp=DEST/(name+'.checkpoint.json');pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg)
        end=232 if name=='target_frozen' else 90;s.session.advance(end-13);restored.session.advance(end-13);rp=DEST/(name+'.replay.json');write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
        target=s.session.world.resolve('target')
        expected=[(15,target,335),(87,target,335),(159,target,335),(231,target,190)] if name=='target_frozen' else [(15,target,190)] if name.startswith('source_dead') else [] if name=='target_invalid' else [(15,target,190),(89,s.session.world.resolve('other'),190)] if name=='captured_selection' else [(22,target,190)]
        actual={'source_alive':s.ctx.alive('archer'),'source_hp':hp(s,'archer'),'target_hp':hp(s),'damage_packets':packets(s),'launches':[(e['time'],e['payload']['target']) for e in s.session.events if e['type']=='projectile.launched'],'invalidations':[(e['time'],e['payload']['reason']) for e in s.session.events if e['type']=='projectile.invalid']}
        obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
        if actual['damage_packets']!=expected or obs!=cp_obs or obs!=rp_obs:raise ValueError('Actual public crossbow/CP/head differs: '+name)
        records.append({'name':name,'actual':actual,'expected_damage_packets':expected,'end_tick':end,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':pin,'tick':13,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(DEST/(name+'.events.jsonl'),s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True,'postdeath_passive_policy_unverified':name=='source_dead_frozen_policy'})
    after={str(p):sha(p) for p in paths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Source/model/runtime guard drift')
    report={'schema':'ark-sim/ch6-snbow-author-evidence/v1','supported_author_checks_passed':True,'core':CORE,'source_at_start':before,'source_at_completion':after,'witnesses':records,'postdeath_passive_lifetime_native_unverified':True,'complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
    p=DEST/'author.evidence.json';write(p,report);print(json.dumps({'supported_author_checks_passed':True,'witnesses':6,'report_sha256':sha(p)}))
if __name__=='__main__':main()
