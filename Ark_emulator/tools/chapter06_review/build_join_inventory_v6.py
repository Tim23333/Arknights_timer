"""Exact current source consumers and remaining full-stage dependencies."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.campaign_content_composition import compose_modules
from tools.chapter06.cold.policies import providers


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert implementation_digest()=='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
    files=[ROOT/'packages/campaign/chapter06_cold/model.json']+[ROOT/'packages/campaign/chapter06_units'/name for name in
        ['melee_v2/model.json','snmage_v3/model.json','snslime/model.json','frozen_melee/model.json','snbow_v2/model.json']]
    sourcepath=ROOT/'packages/campaign/chapter06_sources/native.reference.json';planpath=ROOT/'packages/campaign/chapter06_plans/source.plan.json'
    paths=files+[sourcepath,planpath,Path(__file__)];before={str(p):sha(p) for p in paths}
    source=json.loads(sourcepath.read_bytes());plan=json.loads(planpath.read_bytes());bindings=[]
    parts=[(str(p.relative_to(ROOT)),json.loads(p.read_bytes())) for p in files]
    definitions,provenance=compose_modules(parts)
    for d in definitions.values():
        if d.get('kind')!='entity' or 'enemy' not in d.get('tags',[]):continue
        metadata=d.get('metadata',{});vid=metadata.get('native_variant_id')
        if vid is None:continue
        assert vid in source['variants']
        native=source['variants'][vid]
        if metadata.get('native_reference') is not None:assert metadata['native_reference']==native['native_reference']
        attributes=native['native_enemy']['resolved']['attributes'];actual=d['components']['attributes']['base']
        for key,raw in [('max_hp','maxHp'),('atk','atk'),('def','def'),('mres','magicResistance'),('move_speed','moveSpeed')]:assert actual[key]==attributes[raw]
        assert d['components']['resources']['hp']['initial']==attributes['maxHp']
        bindings.append({'variant':vid,'unit':d['id'],'native_reference':native['native_reference'],
                         'module_provenance':provenance[d['id']],'source_attributes_checked':True})
    assert len(bindings)==7 and len({b['variant'] for b in bindings})==7
    package={'schemaVersion':2,'definitions':list(definitions.values()),'scenarioDraft':{'id':'scene/ch6/current_consumer_compile_inventory',
        'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},'dependencies':[b['unit'] for b in bindings]}}
    program=Compiler(providers=providers()).compile(package)
    present={b['variant'] for b in bindings};missing=sorted(set(source['variants'])-present);assert len(missing)==2
    assert before=={str(p):sha(p) for p in paths}
    stages={}
    for key,stage in plan['stages'].items():
        required=set(stage['variant_ids']);stages[key]={'source_births':stage['spawn_count'],'current_compiled_variants':sorted(required&present),
            'missing_enemy_variants':sorted(required-present),'complete_stage':False}
    out=ROOT/'validation/campaign/chapter06_join_inventory_v6';assert not out.exists();out.mkdir(parents=True)
    report={'core':implementation_digest(),'bindings':bindings,'current_definition_count':len(definitions),'compiled_dependency_count':len(program.dependency_ids),
        'missing_enemy_variants':missing,'stages':stages,'guards':before,'program_fingerprint':program.fingerprint,
        'remaining_non_enemy_dependencies':['Two FrostNova/boss consumers including story_s','Frost traps/branch activation','Fence/portal tile sources','Three exact native NPCs','Five actual story controls and fixed12 training exception'],
        'scope':'Exact module combination/source stats/compile closure only; no actors run, native policy/client/whole-stage not approved'}
    target=out/'inventory.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'variants':len(bindings),'missing':missing,'definitions':len(definitions),'sha':sha(target)}))


if __name__=='__main__':main()
