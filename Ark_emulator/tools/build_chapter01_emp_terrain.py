"""New owned-terrain EMP model; frozen category slice stays unchanged."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'packages/campaign/chapter01_devices/emp.category.json'
SOURCE=ROOT/'packages/campaign/chapter01_devices/emp.source.json'
OUTPUT=ROOT/'packages/campaign/chapter01_devices/emp.terrain.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(BASE)=='79ed4124a4dec23f199fd9edf83e6c473a166a803dd973fb02f4560a9841b24d'
    assert sha(SOURCE)=='7496c92a4d8772569af6a4a49802ab6fa0a9e7c7c1dc75d3890b074af63a1176'
    n=json.loads(SOURCE.read_bytes());p=json.loads(BASE.read_bytes())
    for src in (n['prefab']['source'],n['skill_prefab']['source']):
        assert sha(ROOT.parent/src['path'])==src['sha256'],'EMP original asset changed'
    def component(name):return deepcopy(next(c['raw'] for c in n['prefab']['components'].values() if c['native_class']==name))
    trap=component('MapDependentTrap');mode=component('TrapMode');options=mode['_tileOptions']
    for key in ('_keepCurrentPassableMask','_rewriteTileHeightType','_rewriteTileHeight','_rewriteTileAdvancedBuildMask'):
        assert type(mode[key]) is int and mode[key] in (0,1),key
    for key in ('_rewriteTileOptions','_withdrawable'):
        assert type(trap[key]) is int and trap[key] in (0,1),key
    assert type(options['overrideObstacleLikeMoveCost']) is int and options['overrideObstacleLikeMoveCost'] in (0,1)
    assert trap['_rewriteTileOptions']==1 and trap['_occupiedRemainingCharacterCnt']==0 and trap['_withdrawable']==1
    assert options=={'heightType':0,'buildableType':0,'passableMask':2,'advancedBuildMask':0,'overrideObstacleLikeMoveCost':1},options
    assert (mode['_keepCurrentPassableMask'],mode['_rewriteTileHeightType'],mode['_rewriteTileHeight'],mode['_rewriteTileAdvancedBuildMask'])==(1,0,1,0)
    height=mode['_rewriteHeight'];assert abs(height-.4)<1e-7
    p['status']='source_backed_device_model_owned_terrain_client_pending'
    m=p['manifest']['metadata'];m['terrain_builder_sha256']=sha(Path(__file__));m['terrain_source_sha256']=sha(SOURCE)
    m['model_gaps']=['3D physical height collision/vertical movement is outside this 2D model']
    m['client_pending']+=['Native obstacleLikeMoveCost weight/body unknown; explicit model normal1/obstacle3',
        'TrapMode native priority/body unknown; explicit model priority0/stable layer sequence']
    m['terrain_profile']={'native':{'MapDependentTrap':trap,'TrapMode':mode},
        'consumer':{'buildableType':'deploy.eligibility','passableMask':'preserved current ground path/collision',
          'heightType':'preserved current deployment metadata','advancedBuildMask':'preserved current advanced deployment mask default1',
          'physicalHeight':'effective tile data exposed to replaceable deploy.eligibility; 2D vertical physics pending',
          'overrideObstacleLikeMoveCost':'effective movementCost normal1/obstacle3 weighted shortest-path profile'},
        'formal_approval':False}
    c=p['entities'][0]['components']
    c['terrain_overlays']=[{'key':'native_trap_mode','priority':0,
        'values':{'buildableType':0,'physicalHeight':height,'obstacleLikeMoveCost':True},
        'preserve':['passableMask','heightType','advancedBuildMask']}]
    c['deployable']['parameters']={'advanced_build_mask':1}
    assert trap['_buildCondition']['advancedBuildableMask']==1
    return p
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');args=a.parse_args()
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:assert OUTPUT.read_bytes()==raw,'EMP terrain artifact differs'
    else:OUTPUT.write_bytes(raw)
