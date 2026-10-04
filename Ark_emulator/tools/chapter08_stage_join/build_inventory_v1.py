"""Exact per-stage source consumer inventory, never automatic stage admission."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json'
MODULES={
    'enemy_1107_uoffcr':'ranged/uoffcr.module.v3.json',
    'enemy_1108_uterer':'uterer/module.v1.reference.json',
    'enemy_1110_uamord':'ranged/uamord.module.v4.json',
    'enemy_1111_ucommd':'ranged/ucommd.module.v2.json',
    'enemy_1112_emppnt':'special/emppnt.module.v1.json',
    'enemy_1113_empace':'special/empace.module.v1.json',
    'enemy_1503_talula':'boss/talula.restart.v3.reference.json',
}
OUT=ROOT/'validation/campaign/chapter08_stage_inventory_v1/inventory.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    assert sha(SOURCE)=='9fd95c8f85d4cd464976954c08f97a40a9f855cb3dca23bcd73c6f403d779a66'
    source=json.loads(SOURCE.read_bytes());variants={};pins={str(SOURCE):sha(SOURCE)}
    for vid,v in source['variants'].items():
        resolved=v['native_enemy']['resolved'];key=v['native_enemy']['native_id'];module=MODULES.get(key)
        if module is None:
            variants[vid]={'variant_id':vid,'native_reference':v['native_reference'],'module':None,'source_consumer_status':'pending_complete_bsnake','stage_admitted':False};continue
        path=ROOT/'packages/campaign/chapter08_consumers'/module;pins[str(path)]=sha(path);d=json.loads(path.read_bytes());expected=resolved['attributes']
        candidates=[e for e in d.get('entities',[]) if e.get('kind')=='entity' and e.get('components',{}).get('attributes',{}).get('base',{}).get('max_hp')==expected['maxHp']]
        # There must be one explicit source combat actor, separate from devices.
        assert len(candidates)==1,(vid,[e['id'] for e in candidates]);unit=candidates[0];attrs=unit['components']['attributes']['base']
        wanted={'max_hp':expected['maxHp'],'atk':expected['atk'],'def':expected['def'],'mres':expected['magicResistance'],
            'move_speed':expected['moveSpeed'],'attack_interval':expected['baseAttackTime'],'attack_speed_ratio':expected['attackSpeed']/100,'mass_level':expected['massLevel']}
        assert all(type(attrs[k]) in (int,float) and attrs[k]==n for k,n in wanted.items()),vid
        meta=d['manifest']['metadata'];refs=unit.get('metadata',{}).get('native_reference')
        if refs is not None:assert refs==v['native_reference'],vid
        assert unit['components']['lifecycle']['leak_loss']==resolved['lifePointReduce']
        variants[vid]={'variant_id':vid,'native_reference':v['native_reference'],'module':path.relative_to(ROOT).as_posix(),'module_sha':sha(path),
            'unit':unit['id'],'base_stats':wanted,'required_runtime':meta.get('required_runtime'),'source_consumer_status':'authored_requires_independent_composition_gate',
            'module_pending':meta.get('pending_required_consumers',[]),'stage_admitted':False}
    stages=[]
    for sid,s in source['stages'].items():
        rows=[variants[v] for v in s['variant_ids']];stages.append({'stage':sid,'native_births':s['spawn_count'],'exact_variants':rows,
            'missing_variants':[r['variant_id'] for r in rows if r['module'] is None],'control_counts':s['control_count_by_type'],
            'terrain_keys':sorted(s['tile_cell_counts']),'native_predefines':s['predefines'],'actual_stage_compiled':False,'whole_stage_executed':False})
    assert pins=={name:sha(Path(name)) for name in pins}
    return {'schema':'ark-sim/chapter08-source-consumer-inventory/v1','source_pins':pins,'stages':stages,'variants':variants,
        'remaining_stage_dependencies':['Volcano full geometry/UniformRandom8..12/NoSource1000','infection300s complete source review','Native branch/PLAY_OPERA controls and hiddenflame actions',
            'Talula statusresist dynamic duration/fullsource review and generic restart gates','bsnake complete5mode source consumers','Currentcombinedcore 12roster/source closure and source-input admission',
            'Onlybase99999 overlay/publiclegalcommands/wholecontinuous+CP+head and numeric audit'],
        'whole_stage_executed':False,'client_verified':False}
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(OUT),'stages':[(s['stage'],len(s['exact_variants']),s['missing_variants']) for s in p['stages']]}))
