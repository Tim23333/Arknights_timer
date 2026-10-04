"""Persist public snmage actual Ready/SP/projectile/Cold CP and head replays."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_buff_application_v7_candidate'
OUT=ROOT/'packages/campaign/chapter06_units/snmage/evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter06_units.snmage.test_module import package,deploy,sp,ready,flags,damage
    from tools.chapter06_units.snmage.build_module import COLD,CORE,READY,SKILL,NORMAL
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    base=OUT.parent;tests=base/'author.tests.json';result=json.loads(tests.read_bytes())
    if implementation_digest()!=CORE or not result['passed'] or result['exit_code']!=0 or result['implementation_after']!=CORE:raise ValueError('Actual author tests required')
    paths=list((ROOT/'tools/chapter06_units/snmage').glob('*.py'))+[base/'model.json',base/'source.reference.json',tests,COLD,ROOT/'tools/chapter06/cold/policies.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in paths};OUT.mkdir(parents=True,exist_ok=True);records=[]
    cases=[('normal_ready_cold',{},146,565,8500,2,0),('two_sources_frozen',{'initial_sp':2,'second':True},24,324,8200,2,0),('cancelled_skill',{'initial_sp':2},21,31,10000,0,0)]
    for name,options,cp_tick,end,hp,expected_sp,expected_flags in cases:
        path=OUT/(name+'.probe.json');write(path,package(**options));reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6268,providers=reg)
        deploy(s)
        if name=='cancelled_skill':s.submit({'action':'withdraw','source':'target'},at=22)
        s.session.advance(cp_tick)
        middle={'tick':cp_tick,'mage_sp':sp(s),'ready_instances':ready(s),'target_flags':flags(s),'damage_packets':damage(s)}
        if name=='normal_ready_cold' and (sp(s)!=2 or len(ready(s))!=1):raise ValueError('Actual Ready/SP differs')
        if name=='two_sources_frozen' and 16 not in flags(s):raise ValueError('Actual cross-source Frozen differs')
        cp=OUT/(name+'.checkpoint.json');cp_sha=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,cp_sha),providers=reg)
        s.session.advance(end-cp_tick);restored.session.advance(end-cp_tick)
        rp=OUT/(name+'.replay.json');write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
        obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
        actual={'mage_sp':sp(s),'ready_instance_count':len(ready(s)),'target_hp':s.ctx.resources.current('target','hp'),'target_alive':s.ctx.alive('target'),'target_flags':flags(s),'damage_packets':damage(s),'ability_starts':[(e['time'],e['payload']['source'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started'],'attack_accepted':[(e['time'],e['payload']['source'],e['payload']['ability'],e['payload']['cast']) for e in s.session.events if e['type']=='attack.accepted'],'projectile_launches':[(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='projectile.launched']}
        if actual['target_hp']!=hp or actual['mage_sp']!=expected_sp or len(actual['target_flags'])!=expected_flags or obs!=cp_obs or obs!=rp_obs:raise ValueError('Actual mechanism/CP/head differs: '+name)
        records.append({'name':name,'end_tick':end,'actual_middle':middle,'actual_end':actual,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':cp_sha,'tick':cp_tick,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(OUT/(name+'.events.jsonl'),s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True})
    after={str(p):sha(p) for p in paths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Content/provider/runtime guard drift')
    report={'schema':'ark-sim/ch6-snmage-author-evidence/v1','author_checks_passed':True,'core_start':CORE,'core_end':implementation_digest(),'source_at_start':before,'source_at_completion':after,'identity_stable':True,'witnesses':records,'independent_reviewed':False,'formal_approved':False,'whole_stage_executed':False,'client_verified':False,'scope':'Exact snmage normal/Cold EnemySkill/SP/Ready and real projectile payload; no remaining boss/death bug/story stage claim'}
    p=OUT/'author.evidence.json';write(p,report);print(json.dumps({'author_checks_passed':True,'witnesses':3,'report_sha256':sha(p)}))
if __name__=='__main__':main()
