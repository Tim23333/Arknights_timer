from pathlib import Path
from copy import deepcopy
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'packages/campaign/chapter03_sources/native.reference.json';PARENT=ROOT/'packages/campaign/chapter02_behavior/reference50/skulsr.model.json';OUT=ROOT/'packages/campaign/chapter03_models/skulsr.level1.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    if sha(SOURCE)!='d6a1d5294e1419d6ee41022efa1ef93a0ad44b6effb80c4bdfcf7fc3e7cd1e35' or sha(PARENT)!='7cdd091a4ce55f73f40a591dc7eb87f54e135afacfeaf1f33b71f2e04d8c2b6a':raise ValueError('frozen source/parent drift')
    source=json.loads(SOURCE.read_bytes());v=next(v for v in source['variants'].values() if v['native_enemy']['native_id']=='enemy_1500_skulsr');a=v['native_enemy']['resolved']['attributes'];bb={x['key']:x['value'] for x in v['native_enemy']['resolved']['talentBlackboard']}
    assert v['native_enemy']['native_level']==1 and a['maxHp']==30000 and a['atk']==1300 and bb['atkup.hp_ratio']==.5
    p=json.loads(PARENT.read_bytes());names={row['id']:'ch3/'+row['id'] for rows in p.values() if isinstance(rows,list) for row in rows if isinstance(row,dict) and 'id' in row}
    def rename(value):
        if isinstance(value,dict):return {k:rename(v) for k,v in value.items()}
        if isinstance(value,list):return [rename(v) for v in value]
        return names.get(value,value) if isinstance(value,str) else value
    p=rename(p);unit=p['entities'][0];base=unit['components']['attributes']['base']
    for key,target in [('maxHp','max_hp'),('atk','atk'),('def','def'),('magicResistance','mres'),('moveSpeed','move_speed'),('baseAttackTime','attack_interval'),('massLevel','mass_level')]:base[target]=a[key]
    base['attack_speed_ratio']=a['attackSpeed']/100
    unit['components']['resources']['hp']={'initial':a['maxHp'],'capacity_attribute':'max_hp','role':'health'};unit['components']['lifecycle']['leak_loss']=v['native_enemy']['resolved']['lifePointReduce']
    unit['metadata'].update(native_variant=v['variant_id'],native_variant_id=v['variant_id'],source_stage='level_main_03-08',source_attributes=a,source_talent_BB=bb)
    modebuff=next(b for b in p['buffs'] if b['id']==names['buff/skulsr_mode1']);modebuff['modifiers'][0]['value']=bb['atkup.atk']
    for ability in p['abilities']:
        if ability['id'] in (names['ability/skulsr_enter'],names['ability/skulsr_leave']):
            activation=ability['activation'];activation['parameters'].pop('hp_threshold',None);activation['parameters']['hp_ratio']=bb['atkup.hp_ratio']
            activation['condition']=activation['condition'].replace('params.hp_threshold','inputs.resources.hp.observed_capacity * params.hp_ratio')
            # Capacity changes can alter the ratio without changing current HP.
            extra=deepcopy(ability);extra['id']+='/capacity';extra['activation']['event']='resource.capacity_changed';p['abilities'].append(extra);unit['components']['abilities'].append(extra['id'])
    unit['metadata']['threshold_profile']='actual observed effective HP capacity * exact BB.5; initial source15000; capacity_changed and HP events; hp0 never enters'
    p['manifest']['id']='package/chapter03/skulsr_level1/reference50';p['manifest']['metadata']={'source_locks':{'packages/campaign/chapter03_sources/native.reference.json':sha(SOURCE),'packages/campaign/chapter02_behavior/reference50/skulsr.model.json':sha(PARENT)},
        'builder_sha256':sha(Path(__file__)),'native_variant':v['variant_id'],'source_stage':'level_main_03-08','attributes':a,'talent_BB':bb,
        'declared_profile':'Reuse frozen reference50 packet/motion/phase policies, source level1 stats; namespace-isolated definitions; dynamic half-effective-maxHP phase',
        'feedback_pending':['source historical prefab HPchecker.4 vs selected DB/reference.5','native loader/FSM/packet mapping and callback/body/timing','projected9 impact, captured primary invalid/hidden policy retained from explicit parent profile'],
        'source_complete_for_declared_profile':True,'client_verified':False,'formal_approved':False,'stage_executed':False}
    return p
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('boss module stale')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':sha(OUT),'HP':30000,'ATK':1300,'phase_initial_threshold':15000,'client':False}))
