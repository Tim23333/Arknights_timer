"""Full native map/birth/roster composition draft; source-admission remains pending."""
import argparse,json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
CORE='cba02a10cbf6e4f2736c2ee65386bd22a0cb11b04a0a8a9ed91518ed3f78fb31'
OUT=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter06_review.stage_converter_v7 import compose
    from tools.campaign_content_composition_v2 import compose_modules,reachable_content
    from tools.chapter08_boss.talula_skill_policies_v3 import providers as boss
    from tools.chapter08_special.policies_v2 import providers as special
    from tools.chapter08_ranged.policies_v1 import providers as ranged
    from tools.chapter08_environment.policies_v1 import providers as infection
    assert implementation_digest()==CORE
    source=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json';plan=json.loads(source.read_bytes());stage=plan['stages']['level_main_08-16'];native=deepcopy(stage['native_document']);assert stage['spawn_count']==32
    modules={
        'enemy_1107_uoffcr':'ranged/uoffcr.module.v3.json','enemy_1108_uterer':'uterer/module.v1.reference.json',
        'enemy_1112_emppnt':'special/emppnt.module.v3.json','enemy_1113_empace':'special/empace.module.v3.json',
        'enemy_1503_talula':'boss/talula.restart.burn.v4.reference.json'}
    mods=[];bindings={};variants=[];pins={str(source):sha(source)}
    for vid in stage['variant_ids']:
        v=plan['variants'][vid];key=v['native_enemy']['native_id'];path=ROOT/'packages/campaign/chapter08_consumers'/modules[key];p=json.loads(path.read_bytes())
        unit=next(u for u in p['entities'] if u['components'].get('attributes',{}).get('base',{}).get('max_hp')==v['native_enemy']['resolved']['attributes']['maxHp'])
        mods.append((key,p));pins[str(path)]=sha(path);bindings[key]={'unit':unit['id'],'motion':'WALK'};variants.append({'variant_id':vid,'native_reference':v['native_reference'],'unit':unit['id'],'module':path.relative_to(ROOT).as_posix()})
    rosterpath=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';roster=json.loads(rosterpath.read_bytes());mods.append(('fixed12',roster));pins[str(rosterpath)]=sha(rosterpath)
    profiles={'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}
    for name in ('infection.module.v3.json','volcano.module.v1.json'):
        path=ROOT/'packages/campaign/chapter08_consumers/environment'/name;p=json.loads(path.read_bytes());mods.append((name,p));pins[str(path)]=sha(path)
        if name.startswith('infection'):profiles['tile_infection']=p['manifest']['metadata']['tile_profile']
        else:profiles.update(p['manifest']['metadata']['tile_profiles'])
    scene,controls=compose(native,'level_main_08-16',bindings,profiles)
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
    if controls:mods.append(('native_info_controls',{'definitions':controls}))
    spawnpath=ROOT/'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json';spawn=json.loads(spawnpath.read_bytes());mods.append(('native_spawn_rectangle',{'rules':[r for r in spawn['rules'] if r['id']=='rule/m7_spawn_rectangle']}));pins[str(spawnpath)]=sha(spawnpath)
    definitions,_=compose_modules(mods);speedid=scene['rules']['movement.speed'];speed=deepcopy(definitions[speedid]);speed['parameters']['multiplier']=native['options']['moveMultiplier']
    reg={**boss(),**special(),**ranged(),**infection()};p,report=reachable_content(scene,mods,{speedid:{'definition':speed,'reason':'Exactsource moveMultiplier.5','source':str(source)}},manifest_id='package/ch8/native_draft/jt82_v1',providers=reg)
    assert sum(a.get('count',1) for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')==32
    assert scene['parameters']['deploy_capacity']==9 and scene['resources']['dp']['initial']==10 and scene['resources']['life']['initial']==3
    p['manifest']['metadata'].update(source_locks=pins,variant_bindings=variants,required_core=CORE,builder_sha=sha(Path(__file__)),native_options=native['options'],native_predefines=native['predefines'],source_births=32,
        admission_status='source_composition_draft_only',stage_export_allowed=False,
        pending_required_gates=['Independentwhole sourcefield→consumer review','Native marker selector filter semantics and actual mark source (selection-only witness not enough)','Dynamic status resistance remaining lifetime if used','Source clock/initial mode/restart/core independent/fullsuite gates','Environment geometry/random policies peer review','Fullpublic fixed12 lifeoverlay commands/whole3way'],
        full_stage_executed=False,client_verified=False)
    Compiler(providers=reg).compile(p);return p

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);args=ap.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT));p=build();assert not OUT.exists();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(OUT),'source_births':32,'actual_compile':True,'whole_stage':False}))
