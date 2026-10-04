import hashlib,json
from pathlib import Path
from tools.campaign_content_composition import compose_modules
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    plan_path=ROOT/'packages/campaign/chapter05_plans/source.plan.json';plan=json.loads(plan_path.read_bytes())
    paths=[ROOT/p for p in ['packages/campaign/chapter05_units/ordinary.reference_model.json',
        'packages/campaign/chapter05_units/regenerating/model.json','packages/campaign/chapter05_units/special/model.selection_settle.reference.json',
        'packages/campaign/chapter05_boss/mephi/model.json','packages/campaign/chapter05_boss/faust/complete.v2.reference.json',
        'packages/campaign/roster/fixed12.m26.reference_module.json']]
    definitions,_=compose_modules([(str(p),json.loads(p.read_bytes())) for p in paths]);units={}
    for d in definitions.values():
        if d['kind']!='entity':continue
        meta=d.get('metadata',{});vid=meta.get('native_variant_id',meta.get('native_variant'))
        if not vid and meta.get('native_reference'):
            matches=[v for v,row in plan['variants'].items() if row['native_reference']==meta['native_reference']]
            assert len(matches)==1;vid=matches[0]
        if vid:
            assert vid not in units;units[vid]=d['id']
    stages={}
    for key,s in plan['stages'].items():
        assert all(vid in units for vid in s['variant_ids'])
        stages[key]={'births':s['spawn_count'],'variants':{vid:units[vid] for vid in s['variant_ids']},
            'options':s['native_document']['options']}
    assert len(stages['level_main_05-09']['variants'])==4 and len(stages['level_main_05-10']['variants'])==6
    out=ROOT/'validation/campaign/chapter05_join/enemy_matrix_selection_settle.json';out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf8') as f:json.dump({'passed':True,'stages':stages,'definitions_without_conflict':len(definitions),
        'pins':{str(p.relative_to(ROOT)):sha(p) for p in paths+[plan_path]},'compiled_full_stage':False,
        'remaining':'Actual ballista module, predefined/branch composition and complete stage execution'},f,ensure_ascii=False,indent=2)
    print(json.dumps({'passed':True,'definitions':len(definitions),'sha':sha(out)}))
if __name__=='__main__':main()
