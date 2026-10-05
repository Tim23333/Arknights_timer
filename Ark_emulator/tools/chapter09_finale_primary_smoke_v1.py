"""Verify promoted primary import/immutable catalog and deterministic custom rules."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter09_mandra_full_v1.catalog108 import test_catalog_exact107_plus_capture_and_immutable
from tools.chapter09_stage919_assembly_v1.providers_v3 import providers


def main():
    core=implementation_digest();assert core=='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
    test_catalog_exact107_plus_capture_and_immutable();proof=[]
    for ruleset,expected in [('ruleset/ark_standard',850),('ruleset/custom_balance',60)]:
        program=Compiler().compile(ROOT/'packages/custom/custom_guard.json',ruleset=ruleset);s=Engine.create(program,seed=123);s.advance(10);r=Engine.restore(program,s.checkpoint());s.advance(20);r.advance(20);h=replay(program,s.export_replay());assert s.checkpoint()==r.checkpoint()==h.checkpoint();assert s.ctx.state()['damage_dealt']==expected;proof.append({'ruleset':ruleset,'actual_damage':expected,'CPP_head_full_equal':True})
    p=Compiler(providers=providers()).compile(ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v4.life99999.json')
    modules={name:str(Path(m.__file__).resolve()) for name,m in sys.modules.items() if name.startswith('ark_sim') and getattr(m,'__file__',None)}
    assert all(Path(path).is_relative_to(ROOT/'ark_sim') for path in modules.values())
    out=ROOT/'validation/campaign/chapter09_finale_primary_v1/smoke.json';assert not out.exists();out.write_text(json.dumps({'passed':True,'actual_exit':0,'primary_core':core,'catalog108_exact_and_immutable':True,'actual_custom_rules':proof,'stage_source_program':p.fingerprint,'actual_modules':modules,'whole_stage':False},indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'primary_core':core,'catalog':108}))


if __name__=='__main__':main()
