"""Persist actual Cold/Frozen source-bound mechanism, disk CP and head replay."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent/'unpack_work/campaign_buff_application_v7_candidate'
OUT = ROOT/'packages/campaign/chapter06_cold/evidence'
CORE = '4ef955c5d5a7628382fc3d15003bb0a30c749832d210ca50897355568ec8d329'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v): p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))

def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter06.cold.test_consumer import fixture_package,apply,hit,instances,flags
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    if not Path(ark_sim.__file__).resolve().is_relative_to(RUNTIME) or implementation_digest()!=CORE:raise ValueError('Candidate identity differs')
    tests=ROOT/'packages/campaign/chapter06_cold/author.tests.json'
    passed=json.loads(tests.read_bytes())
    if not passed['passed'] or passed['exit_code']!=0 or passed['implementation_after']!=CORE:raise ValueError('Actual author tests required')
    guardpaths=list((ROOT/'tools/chapter06/cold').glob('*.py'))+[ROOT/'packages/campaign/chapter06_cold/model.json',ROOT/'packages/campaign/chapter06_cold/source.decoded.json',tests,RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in guardpaths}
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    for name,ratio,factor,immune,damage,end in [('five_to_ten',1.5,1,[],130,402),('resistant',2.5,.5,[],230,252),('frozen_immune',2.5,1,[16],80,402)]:
        package=fixture_package(ratio=ratio,factor=factor,immune=immune)
        path=OUT/(name+'.probe.json');write(path,package)
        reg=providers();program=Compiler(providers=reg).compile(path);s=Engine.create(program,seed=616,providers=reg)
        apply(s,10);apply(s,5,at=20,source='caster2');hit(s,at=21);apply(s,10,at=100)
        s.session.advance(10);cp=OUT/(name+'.checkpoint.json');cp_sha=write_ordered(cp,s.checkpoint())
        restored=Engine.restore(program,load_bound(cp,cp_sha),providers=reg)
        s.session.advance(12);restored.session.advance(12)
        middle={'tick':22,'flags':flags(s),'instances':instances(s),'controls':s.ctx.buffs.controls('target'),'hp':s.ctx.resources.current('target','hp'),'sp':s.ctx.resources.current('target','sp')}
        if middle['hp']!=10000-damage or (16 in middle['flags'])!= (not bool(immune)):raise ValueError('Actual source mechanism differs: '+name)
        s.session.advance(end-22);restored.session.advance(end-22)
        record=OUT/(name+'.replay.json');write(record,s.export_replay())
        repeated=replay(program,json.loads(record.read_bytes()),providers=reg)
        obs=observations(s);cp_obs=observations(restored);replay_obs=observations(repeated)
        if obs!=cp_obs or obs!=replay_obs or instances(s) or flags(s):raise ValueError('Actual CP/replay/expiry differs: '+name)
        journal=export_events(OUT/(name+'.events.jsonl'),s)
        records.append({'name':name,'end_tick':end,'actual_middle':middle,'actual_damage':[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted'],
            'expected_damage':[(21,damage)],'program':program.fingerprint,'runtime':s.runtime_fingerprint,
            'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':cp_sha,'tick':10,'actually_reloaded':True},
            'replay':{'path':str(record),'sha256':sha(record)},'journal':journal,'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':replay_obs,'checkpoint_equal':True,'replay_equal':True})
    after={str(p):sha(p) for p in guardpaths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Source identity drift')
    report={'schema':'ark-sim/chapter06-cold-author-evidence/v1','author_checks_passed':True,'independent_reviewed':False,'formal_approved':False,'whole_stage_executed':False,'client_verified':False,
        'runtime_module':ark_sim.__file__,'core_start':CORE,'core_end':implementation_digest(),'source_at_start':before,'source_at_completion':after,'witnesses':records,
        'scope':'Reusable source e2c Cold/Frozen5/10 and TARGETFROZEN attack multiplier; no completed stage or story/NPC claim'}
    dest=OUT/'author.evidence.json';write(dest,report)
    print(json.dumps({'author_checks_passed':True,'report_sha256':sha(dest),'witnesses':len(records)}))

if __name__=='__main__':main()
