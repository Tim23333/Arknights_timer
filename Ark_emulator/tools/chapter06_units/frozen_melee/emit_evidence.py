"""Freeze two exact melee consumers with actual status clocks and CP/head journals."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
OUT=ROOT/'packages/campaign/chapter06_units/frozen_melee/evidence'
CORE='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter06_units.frozen_melee.test_module import status_package,deploy,cold,hp,packets,COLDMODULE
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    base=OUT.parent;tests=base/'author.tests.json';passed=json.loads(tests.read_bytes())
    if implementation_digest()!=CORE or not passed['passed'] or passed['implementation_after']!=CORE:raise ValueError('Frozen candidate/source author tests required')
    paths=list((ROOT/'tools/chapter06_units/frozen_melee').glob('*.py'))+[base/'model.json',base/'dependency.priority.json',tests,COLDMODULE,ROOT/'tools/chapter06/cold/policies.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in paths};OUT.mkdir(parents=True,exist_ok=True);records=[]
    for native in ('enemy_1065_snwolf_2','enemy_1069_icebrk'):
        for case in ('target_frozen','source_silenced','source_cold'):
            name=native+'.'+case;p=status_package(native,source_receiver=case=='source_cold');path=OUT/(name+'.probe.json');write(path,p);reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLDMODULE]);s=Engine.create(program,seed=6269,providers=reg)
            if case=='source_cold':cold(s,(0,));deploy(s,at=1)
            else:
                deploy(s);cold(s)
                if case=='source_silenced':s.submit({'action':'skill','source':'controller','ability':'ability/test/frozen_melee/silence'},at=10)
            s.session.advance(10);cp=OUT/(name+'.checkpoint.json');pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg)
            s.session.advance(201);restored.session.advance(201);rp=OUT/(name+'.replay.json');write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
            actual={'enemy_hp':hp(s),'target_hp':hp(s,'blocker'),'source_alive':s.ctx.alive('enemy'),'damage_packets':packets(s),'source_buffs':s.ctx.get('enemy',('buffs','instances'),[])}
            if case!='source_cold':
                expected=[(17,330),(59,545),(101,545),(143,545),(185,330)] if native=='enemy_1065_snwolf_2' else [(30,1975),(120,1975),(210,730)]
                if actual['damage_packets']!=expected:raise ValueError('Real source passive/silence packets differ')
            else:
                owner=s.session.world.resolve('enemy');start=next(e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==owner);hit=actual['damage_packets'][0][0]
                if hit-start!=(23 if native=='enemy_1065_snwolf_2' else 42):raise ValueError('Real scaled source clock differs')
            obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
            if obs!=cp_obs or obs!=rp_obs:raise ValueError('Actual disk/head observation differs')
            records.append({'name':name,'native':native,'case':case,'actual':actual,'end_tick':211,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':pin,'tick':10,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(OUT/(name+'.events.jsonl'),s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True})
    after={str(p):sha(p) for p in paths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Frozen content/runtime/source drift')
    report={'schema':'ark-sim/ch6-frozen-melee-author-evidence/v1','author_checks_passed':True,'core':CORE,'source_at_start':before,'source_at_completion':after,'witnesses':records,'complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
    path=OUT/'author.evidence.json';write(path,report);print(json.dumps({'author_checks_passed':True,'witnesses':6,'report_sha256':sha(path)}))
if __name__=='__main__':main()
