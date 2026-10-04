"""Minimal immutable ordinary Boss receipt with persisted real rebirth CP/head."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
OUT=ROOT/'packages/campaign/chapter06_boss/frstar2/evidence'
CORE='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter06_boss.frstar2.test_module import package,deploy,kill,hp,events,dealt
    from tools.chapter06_boss.frstar2.build_module import COLD
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    base=OUT.parent;reports=['profile.rebirth.tests.json','focused.tests.json','ice.immunity.tests.json','extra.control.tests.json','trap.joint.tests.json']
    for name in reports:
        r=json.loads((base/name).read_bytes())
        if not r['passed'] or r['implementation_after']!=CORE:raise ValueError('Actual grouped final test did not pass: '+name)
    paths=list((ROOT/'tools/chapter06_boss/frstar2').glob('*.py'))+[base/'model.json',base/'source.closure.json',*[base/n for n in reports],COLD,ROOT/'tools/chapter06/cold/policies.py',ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in paths}
    if implementation_digest()!=CORE:raise ValueError('Frozen base only')
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'rebirth.probe.json';write(path,package());reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6216,providers=reg)
    deploy(s);kill(s,5);s.session.advance(6)
    if hp(s)!=0 or s.ctx.active('boss') or not s.ctx.alive('boss'):raise ValueError('Actual real zeroHP awaiting rebirth required')
    cp=OUT/'rebirth.checkpoint.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg)
    s.session.advance(333);restored.session.advance(333);rp=OUT/'rebirth.replay.json';write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
    obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
    actual={'boss_hp':hp(s),'boss_alive':s.ctx.alive('boss'),'boss_active':s.ctx.active('boss'),'damage_packets':dealt(s),'rebirth_starts':[e['time'] for e in events(s,'entity.rebirth.started')],'rebirth_finishes':[e['time'] for e in events(s,'entity.rebirth.completed')],'branch_phases':[e['time'] for e in events(s,'branch.phase_started')],'died_events':len(events(s,'entity.died'))}
    if obs!=cp_obs or obs!=rp_obs or actual['boss_hp']!=30000 or actual['rebirth_finishes']!=[305] or actual['died_events']!=0:raise ValueError('Actual final bounded CP/head profile differs')
    after={str(p):sha(p) for p in paths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Source/model/helper/runtime changed during finalbound proof')
    report={'schema':'ark-sim/ch6-frstar2-ordinary-final-author-evidence/v1','author_checks_passed':True,'core':CORE,'source_guard_scope':'Guards start at this final bound wrapper; earlier independent/grouped runs remain own actual identities, no invented beforeguard','source_at_start':before,'source_at_completion':after,'grouped_actual_pass_counts':{'profile_rebirth':3,'burst_and_cp':6,'ice_immunity':4,'priority_intrinsic':5,'real_trap_joint':1},'actual':actual,'end_tick':339,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':pin,'tick':6,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(OUT/'rebirth.events.jsonl',s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True,'previous_pytest_cp_scope':'Actual tmp-path write/reload/head assertions; older temporary checkpoints expired naturally and are not claimed as retained files','complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
    p=OUT/'author.evidence.json';write(p,report);print(json.dumps({'author_checks_passed':True,'actual_grouped_tests':19,'checkpoint_equal':True,'replay_equal':True,'report_sha256':sha(p)}))
if __name__=='__main__':main()
