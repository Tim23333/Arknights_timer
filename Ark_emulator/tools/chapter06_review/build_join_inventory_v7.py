"""Compile current C6 content closure with exact source variants and NPCs."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.campaign_content_composition import compose_modules
from tools.chapter06.cold.policies import providers as cold
from tools.chapter06_npcs.providers_v2 import providers as npcs


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert implementation_digest()=='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b'
    modules=[ROOT/'packages/campaign/chapter06_cold/model.json']+[ROOT/'packages/campaign/chapter06_units'/n for n in
        ['melee_v2/model.json','snmage_v3/model.json','snslime/model.json','frozen_melee/model.json','snbow_v2/model.json']]
    modules += [ROOT/'packages/campaign/chapter06_npcs'/n for n in ['swllow.v2.model.json','huang.v7.model.json','amiya.v3.model.json','story_controls.v2.model.json']]
    modules += [ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json']
    sourcepath=ROOT/'packages/campaign/chapter06_sources/native.reference.json'
    before={str(p):sha(p) for p in modules+[sourcepath,Path(__file__)]}
    source=json.loads(sourcepath.read_bytes());defs,provenance=compose_modules([(p.name,json.loads(p.read_bytes())) for p in modules])
    present={d['metadata']['native_variant_id']:d['id'] for d in defs.values() if d['kind']=='entity' and d.get('metadata',{}).get('native_variant_id')}
    assert len(present)==7
    wanted=[d['id'] for d in defs.values() if d['kind']=='entity']
    p={'schemaVersion':2,'definitions':list(defs.values()),'scenarioDraft':{'id':'scene/ch6/source_content_closure_v7',
        'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},'dependencies':wanted}}
    reg={**cold(),**npcs()};program=Compiler(providers=reg).compile(p)
    assert before=={str(path):sha(Path(path)) for path in before}
    out=ROOT/'validation/campaign/chapter06_join_inventory_v7';out.mkdir(exist_ok=False)
    (out/'compile_input.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    report={'passed':True,'core':implementation_digest(),'guards':before,'definition_count':len(defs),
        'dependency_count':len(program.dependency_ids),'program':program.fingerprint,
        'exact_enemy_variants':present,'missing_enemy_variants':sorted(set(source['variants'])-set(present)),
        'actual_compiled_source_npcs':3,'actual_compiled_frost_trap':True,
        'scope':'Current combined source content compile, no ordinary or story boss added without finalized source proof. No full stage or client accuracy claim.',
        'whole_stage_executed':False,'independent_combined_review':False}
    target=out/'inventory.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'definitions':len(defs),'sha':sha(target)}))


if __name__=='__main__':main()
