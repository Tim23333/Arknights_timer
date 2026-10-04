"""Real C6 source content prunes only unused definitions with explicit providers."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from tools.campaign_content_composition_v2 import reachable_content
from tools.chapter06.cold.policies import providers as cold
from tools.chapter06_npcs.providers_v2 import providers as npcs


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    data=ROOT/'validation/campaign/chapter06_join_inventory_v7/compile_input.json';source=json.loads(data.read_bytes())
    providers={**cold(),**npcs()};scene={'kind':'scenario',**source['scenarioDraft']}
    for check in [scene]:check['dependencies']=['unit/ch6/npc/char_017_huang','unit/ch6/predefined/frosts/source_level1']
    modules=[('source_content',{'definitions':source['definitions']})]
    helper=ROOT/'tools/campaign_content_composition_v2.py';before={str(p):sha(p) for p in [data,helper,Path(__file__)]}
    result,report=reachable_content(scene,modules,providers=providers,manifest_id='package/ch6/composition_provider_probe')
    assert 'unit/ch6/npc/char_017_huang' in report['retained_ids'] and 'unit/ch6/predefined/frosts/source_level1' in report['retained_ids']
    assert 'unit/ch6/npc/char_002_amiya' in report['removed_ids']
    expected=Compiler(providers=providers).compile(scene,packages={'schemaVersion':2,'definitions':source['definitions']})
    actual=Compiler(providers=providers).compile(result)
    assert all(thaw(getattr(expected,key))==thaw(getattr(actual,key)) for key in ('definitions','scenario','ruleset','rules'))
    try:reachable_content(scene,modules)
    except ValueError:missing_provider_rejected=True
    else:raise AssertionError('Missing content provider accepted')
    assert before=={str(p):sha(Path(p)) for p in before}
    out=ROOT/'validation/campaign/chapter06_provider_composition_v2';out.mkdir(exist_ok=False)
    (out/'composed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    proof={'passed':True,'core':implementation_digest(),'source_guards':before,'retained':report['retained_ids'],
        'removed':report['removed_ids'],'program':actual.fingerprint,'unpruned_program':expected.fingerprint,
        'all_executable_definitions_rules_scene_unchanged':True,'missing_custom_provider_rejected':missing_provider_rejected,
        'scope':'Real source compile/closure pruning with explicit content providers; no actor execution or fullstage claim'}
    path=out/'verification.json';path.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha':sha(path)}))


if __name__=='__main__':main()
