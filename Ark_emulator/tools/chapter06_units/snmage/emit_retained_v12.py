"""Original frozen content, v12 actual pre-kill disk CP and public head replay."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v12_candidate'
OUT=ROOT/'packages/campaign/chapter06_units/snmage/retained_v12'
CORE='6192789537ba5250da2cd781f6583a8b7ce7dccfcfba4a5bb9fc5f535674d419'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from ark_sim.domains.buff_application import pure_attributes
    from tools.chapter06_units.snmage.test_module import package,deploy,sp,flags,damage
    from tools.chapter06_units.snmage.build_module import COLD
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    if not Path(ark_sim.__file__).resolve().is_relative_to(RUNTIME) or implementation_digest()!=CORE:raise ValueError('Required isolated v12')
    old=OUT.parent;guards=[Path(__file__),old/'model.json',old/'source.reference.json',old/'required.retained_payload.actual.json',old/'required.retained_payload.tests.json',ROOT/'tools/chapter06_units/snmage/test_required_retained_payload.py',ROOT/'tools/chapter06_units/snmage/test_module.py',COLD,ROOT/'tools/chapter06/cold/policies.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in guards};OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'prekill.probe.json';write(path,package(initial_sp=2));reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6268,providers=reg)
    deploy(s);s.submit({'action':'skill','source':'target','ability':'ability/test/snmage/kill'},at=22)
    s.session.advance(21)
    if not s.ctx.alive('mage') or s.ctx.resources.current('mage','hp')!=8000 or flags(s) or sp(s)!=0:raise ValueError('CP must precede source death with real in-flight skill')
    cp=OUT/'prekill.checkpoint.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg)
    s.session.advance(3);restored.session.advance(3)
    middle={'time':24,'source_alive':s.ctx.alive('mage'),'source_hp':s.ctx.resources.current('mage','hp'),'source_sp':sp(s),'target_hp':s.ctx.resources.current('target','hp'),'target_flags':flags(s),'target_attack_speed_ratio':pure_attributes(s.ctx,s.session.world.resolve('target'))['attack_speed_ratio'],'target_buffs':s.ctx.get('target',('buffs','instances'),[]),'damage_packets':damage(s)}
    if middle['source_alive'] or middle['source_hp']!=0 or middle['source_sp']!=0 or middle['target_hp']!=9700 or middle['target_flags']!=[23] or middle['target_attack_speed_ratio']!=.7 or middle['damage_packets']!=[(22,8000),(23,300)]:raise ValueError('Actual retained source payload differs')
    if len(middle['target_buffs'])!=1 or middle['target_buffs'][0]['expires_at']!=323:raise ValueError('Exact incoming Cold10 expiry required')
    s.session.advance(298);restored.session.advance(298)
    if flags(s)!=[23] or s.session.time!=322:raise ValueError('Cold must survive to last pre-expiry boundary')
    s.session.advance(2);restored.session.advance(2)
    rp=OUT/'prekill.replay.json';write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
    obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
    if obs!=cp_obs or obs!=rp_obs or flags(s) or s.ctx.get('target',('buffs','instances'),[]) or sp(s)!=0 or s.ctx.resources.current('mage','hp')!=0:raise ValueError('Actual CP/head/expiry/source-state differs')
    after={str(p):sha(p) for p in guards}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Original source/module/failure/runtime guard drift')
    report={'schema':'ark-sim/ch6-snmage-retained-v12-author-proof/v1','required_source_case_passed':True,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False,'core_start':CORE,'core_end':implementation_digest(),'source_at_start':before,'source_at_completion':after,'old_failure_preserved':True,'actual_middle':middle,'end_tick':324,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':pin,'tick':21,'before_kill22':True,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(OUT/'prekill.events.jsonl',s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True,'scope':'Exact original required source case only; Root generic peer and complete snmage gate remain separate'}
    dest=OUT/'prekill.author.proof.json';write(dest,report);print(json.dumps({'required_source_case_passed':True,'checkpoint_equal':True,'replay_equal':True,'report_sha256':sha(dest)}))
if __name__=='__main__':main()
