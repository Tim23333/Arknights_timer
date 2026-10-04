"""Source-bound crate stock/stat/terrain module; route destruction separate."""
from copy import deepcopy
import argparse,json,hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter03_plans/source.plan.json'
PIN='d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6'
OUT=ROOT/'packages/campaign/chapter03_traps/crate.partial.reference_model.json'


def build():
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Frozen crate source plan drift')
    plan=json.loads(raw);native=plan['selected_native_prefabs']['trap_001_crate'];rows=list(native['components'].values())
    root=next(r['raw'] for r in rows if r['native_class']=='MapDependentTrap');mode=next(r['raw'] for r in rows if r['native_class']=='TrapMode')
    asset=ROOT.parent/native['source']['path']
    if hashlib.sha256(asset.read_bytes()).hexdigest()!=native['source']['sha256']:raise ValueError('Pinned crate asset drift')
    import UnityPy;objects={o.path_id:o for o in UnityPy.load(str(asset)).objects}
    for pid,row in native['components'].items():
        if objects[int(pid)].read_typetree()!=row['raw']:raise ValueError('Actual crate source component drift')
    source=plan['predefined_table_subsets']['trap_001_crate'];phase=source['character']['phases'][0];start,end=phase['attributesKeyFrames']
    if start['data']!=end['data']:raise ValueError('Crate endpoints require growth conversion')
    attrs=start['data'];config=source['source_native_configs'][0]['native']
    if config['initialCnt']!=5 or config['inst']['level']!=1 or config['inst']['phase']!='PHASE_0':raise ValueError('Native crate card config changed')
    if mode['_keepCurrentPassableMask']!=1 or mode['_tileOptions']['overrideObstacleLikeMoveCost']!=1 or root['_occupiedRemainingCharacterCnt']!=0:raise ValueError('Crate map options need new adapter')
    return {'schemaVersion':2,'manifest':{'id':'package/chapter03/crate_partial','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{'packages/campaign/chapter03_plans/source.plan.json':PIN,str(asset.resolve()):native['source']['sha256']},
        'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'native_cards':deepcopy(config),
        'required_battle_resources':{'crate_cards':{'initial':5,'capacity':5}},'native_runtime_ready':False,
        'model_gaps':['Weighted obstacle route selection with keepCurrentPassableMask and obstacle attack/destruction',
            'Exact native trap passive Buff/abnormal states and class category permission'],
        'client_feedback':['Source2025asset/currenttable correspondence','Native path obstacle cost comparator'],
        'scope':'Actual stats, finite card requirement, cost/refund/terrain ownership; no complete crate claim'}},
        'entities':[{'id':'unit/ch3/crate','kind':'entity','tags':['player','token','ground','route_obstacle'],
            'metadata':{'native_id':'trap_001_crate','native_config':config,'native_block_count_table':attrs['blockCnt'],
                'declared_model_blocking':'Ordinary character blocking disabled until obstacle contact/destruction policy supplied'},
            'components':{'spatial':{},'attributes':{'base':{'max_hp':attrs['maxHp'],'atk':attrs['atk'],'def':attrs['def'],'mres':attrs['magicResistance'],
                'block_count':0,'deploy_cost':attrs['cost'],'redeploy_time':attrs['respawnTime'],'mass_level':attrs['massLevel']}},
                'resources':{'hp':{'initial':attrs['maxHp'],'capacity':attrs['maxHp'],'role':'health'}},'abilities':[],
                'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'base_cost':attrs['cost'],'cooldown_seconds':attrs['respawnTime'],
                    'refund_ratio':root['_withdrawCostRecoverRatio'],'capacity':root['_occupiedRemainingCharacterCnt'],'terrain':'ground',
                    'stock':{'resource':'crate_cards','amount':1},'parameters':{'max_instances':5,'refund_cap_raw_ratio':root['_maxWithdrawCostRatioOfRawCost']}},
                'selection_state':{'side':0,'motion':1,'category':root['_category'],'unit_type':4},
                'terrain_overlays':[{'key':'native_crate','priority':0,'values':{'buildableType':mode['_tileOptions']['buildableType'],
                    'obstacleLikeMoveCost':True,'physicalHeight':mode['_rewriteHeight']},'preserve':['passableMask']}]
                }}]}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Crate source module changed')
    else:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'source_card_count':5,'complete_crate':False}))
