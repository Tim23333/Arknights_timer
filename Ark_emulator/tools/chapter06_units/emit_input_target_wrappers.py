"""Persist native INPUT_TARGET2 blocked/invalid-blocker public CP/head witnesses."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
DEST=ROOT/'packages/campaign/chapter06_units/input_target_evidence'
CORE='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter06_units.test_input_target_wrappers import package,deploy,hits,COLD
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    if implementation_digest()!=CORE:raise ValueError('Frozen candidate required')
    paths=[Path(__file__),ROOT/'tools/chapter06_units/build_input_target_wrappers.py',ROOT/'tools/chapter06_units/test_input_target_wrappers.py',ROOT/'packages/campaign/chapter06_units/snmage_v3/model.json',ROOT/'packages/campaign/chapter06_units/snbow_v2/model.json',ROOT/'packages/campaign/chapter06_units/snmage_v2/model.json',ROOT/'packages/campaign/chapter06_units/snbow/model.json',ROOT/'packages/campaign/chapter06_units/input_target.author.tests.json',ROOT/'packages/campaign/chapter06_units/input_target.regression.tests.json',COLD,ROOT/'tools/chapter06/cold/policies.py',RUNTIME/'ark_sim/rules/contracts.json']
    for file in ('input_target.author.tests.json','input_target.regression.tests.json'):
        if not json.loads((ROOT/'packages/campaign/chapter06_units'/file).read_bytes())['passed']:raise ValueError('Actual author/regression required')
    before={str(p):sha(p) for p in paths};DEST.mkdir(parents=True,exist_ok=True);records=[]
    for kind,initial,invalid in [('mage',0,False),('mage',2,False),('bow',0,False),('mage',2,True),('bow',0,True)]:
        name=kind+str(initial)+('_invalid' if invalid else '_blocked');path=DEST/(name+'.probe.json');write(path,package(kind,initial_sp=initial,invalid_blocker=invalid));reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6293,providers=reg);deploy(s)
        s.session.advance(1)
        if s.ctx.spatial.blocked_by('enemy')!=s.session.world.resolve('blocker'):raise ValueError('Actual firsttick relation notsettled')
        cp=DEST/(name+'.checkpoint.json');pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg);s.session.advance(160);restored.session.advance(160)
        rp=DEST/(name+'.replay.json');write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
        actual={'blocked_by':s.ctx.spatial.blocked_by('enemy'),'blocker':s.session.world.resolve('blocker'),'bait':s.session.world.resolve('bait'),'bait_hp':s.ctx.resources.current('bait','hp'),'damage_packets':[(e['time'],e['payload']['target'],e['payload']['amount']) for e in hits(s)],'casts':[(e['time'],e['payload']['ability'],list(e['payload']['targets'])) for e in s.session.events if e['type']=='ability.started']}
        obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
        if obs!=cp_obs or obs!=rp_obs or actual['bait_hp']!=20000 or (invalid and actual['damage_packets']) or (not invalid and (not actual['damage_packets'] or any(x[1]!=actual['blocker'] for x in actual['damage_packets']))):raise ValueError('Sourcehardgate/CP/head differs')
        records.append({'name':name,'actual':actual,'end_tick':161,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':pin,'tick':1,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(DEST/(name+'.events.jsonl'),s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True})
    after={str(p):sha(p) for p in paths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Old/new/source/runtime guard drift')
    report={'schema':'ark-sim/ch6-input-target2-wrapper-author-evidence/v1','author_checks_passed':True,'core':CORE,'old_bytes_preserved':True,'source_at_start':before,'source_at_completion':after,'witnesses':records,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
    p=DEST/'author.evidence.json';write(p,report);print(json.dumps({'author_checks_passed':True,'witnesses':5,'report_sha256':sha(p)}))
if __name__=='__main__':main()
