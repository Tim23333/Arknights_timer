"""Current exact-variant source consumers, without inferring module admission."""
import hashlib
import json
from pathlib import Path
from tools.campaign_content_composition_v2 import compose_modules
from tools.chapter06_review.stage_converter_v7 import exact
from tools.chapter06_review.source_locks_v1 import verify

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter07_sources/native.reference.json'
PLAN=ROOT/'packages/campaign/chapter07_plans/source.plan.json'
PATHS=[
    'packages/campaign/chapter07_ordinary/sotihd.module.v4.reference.json',
    'packages/campaign/chapter07_ordinary_remaining/sotisd.module.v3.reference.json',
    'packages/campaign/chapter07_strength_melee/module.enemy_1078_sotisc.v6.json',
    'packages/campaign/chapter07_strength_melee/module.enemy_1083_sotiab.v6.json',
    'packages/campaign/chapter07_strength_melee/module.enemy_1083_sotiab_2.v6.json',
    'packages/campaign/chapter07_boss/demons/enemy_1084_sotidm.module.v1.json',
    'packages/campaign/chapter07_boss/demons/enemy_1085_sotiwz.module.v1.json',
    'packages/campaign/chapter07_boss/demons/enemy_1085_sotiwz_2.module.v1.json',
    'packages/campaign/chapter07_global_support/sotidp.module.v1.json',
]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    assert sha(SOURCE)=='8bd457cc8f24d154b304a8cf0a946b9e2a83ae1dcfc01a08073a97364dc1119e'
    assert sha(PLAN)=='e5a60611432f7413689af811a069fb33aac57123bd58190f51161f8a01129339'
    source=json.loads(SOURCE.read_bytes());plan=json.loads(PLAN.read_bytes())
    modules=[(name,json.loads((ROOT/name).read_bytes())) for name in PATHS]
    definitions,_=compose_modules(modules);rows={}
    keys={'max_hp':'maxHp','atk':'atk','def':'def','mres':'magicResistance',
          'move_speed':'moveSpeed','attack_interval':'baseAttackTime'}
    for name,module in modules:
        locks=verify(module)
        for unit in module.get('entities',[]):
            meta=unit.get('metadata',{});vid=meta.get('native_variant_id',meta.get('native_variant'))
            if not vid:
                bindings=module['manifest']['metadata'].get('variant_bindings',[])
                bound=[row for row in bindings if row['unit_definition']==unit['id']]
                if len(bound)==1:vid=bound[0]['variant_id']
            if vid not in source['variants']:raise ValueError('Unknown exact variant '+str(vid))
            if vid in rows:raise ValueError('Duplicate exact source variant '+vid)
            original=source['variants'][vid]
            if 'native_reference' in meta and not exact(meta['native_reference'],original['native_reference']):
                raise ValueError('Raw source reference differs '+vid)
            raw=original['native_enemy']['resolved']['attributes'];actual=unit['components']['attributes']['base']
            for dst,src in keys.items():
                if type(actual[dst]) is bool or actual[dst]!=raw[src]:raise ValueError('Base source stat differs '+vid+'/'+dst)
            if unit['components']['resources']['hp']['initial']!=raw['maxHp']:
                raise ValueError('Initial HP differs '+vid)
            rows[vid]={'variant_id':vid,'native_reference':original['native_reference'],
                       'definition':unit['id'],'module':name,'module_sha256':sha(ROOT/name),
                       'source_locks_checked':locks,'base_stats_match':True,
                       'authoring_available':True,'source_complete_admitted':False,
                       'required_next_gate':'Current-core independent source mechanism/qualification/timing and full stage compatibility; module presence alone is not admission.'}
    stages=[]
    for stage,profile in plan['stages'].items():
        required=profile['variant_ids']
        stages.append({'native_id':stage,'code':{'level_main_07-15':'7-17','level_main_07-16':'7-18'}[stage],
                       'required_variants':required,'available':[rows[v] for v in required if v in rows],
                       'missing_variants':[v for v in required if v not in rows],
                       'native_options':profile['native_document']['options'],
                       'whole_stage_ready':False})
    return {'schema':'ark-sim/chapter07-join-source-consumer-inventory/v1',
            'source_locks':{str(SOURCE):sha(SOURCE),str(PLAN):sha(PLAN),str(Path(__file__).resolve()):sha(Path(__file__))},
            'module_count':len(modules),'composed_definition_count':len(definitions),
            'exact_variant_count':len(source['variants']),'available_count':len(rows),
            'stages':stages,'whole_stage_created':False,'client_verified':False}


def main():
    out=ROOT/'validation/campaign/chapter07_join_inventory_v1/inventory.json';assert not out.exists()
    value=build();out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(out),'available':value['available_count'],
        'missing':{s['code']:s['missing_variants'] for s in value['stages']}}))


if __name__=='__main__':main()
