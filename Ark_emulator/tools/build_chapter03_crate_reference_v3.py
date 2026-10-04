"""Bind source DEFAULT card timing and forbid-seal reference policy."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'packages/campaign/chapter03_traps/crate.reference_v2.partial.json'
PIN='eeee6f654c0c2344743a396bd46d0cfa941a891bd27838ad81f3eace0fbec7cc'
PLAN=ROOT/'packages/campaign/chapter03_plans/source.plan.json'
PLAN_PIN='d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6'
OUT=ROOT/'packages/campaign/chapter03_traps/crate.reference_v3.model.json'


def build():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PIN or hashlib.sha256(PLAN.read_bytes()).hexdigest()!=PLAN_PIN:raise ValueError('Frozen crate source changed')
    plan=json.loads(PLAN.read_bytes());native=plan['selected_native_prefabs']['trap_001_crate']
    raw=next(c['raw'] for c in native['components'].values() if c['native_class']=='MapDependentTrap')
    if raw['_cardPolicy']!=0 or raw['_ignoreBlockAnyRoutes']!=0 or raw['_buildCondition']['advancedBuildableMask']!=1:raise ValueError('Source card/placement policy requires a new adapter')
    p=json.loads(PARENT.read_bytes());deploy=p['entities'][0]['components']['deployable']
    if deploy['base_cost']!=5 or deploy['cooldown_seconds']!=5:raise ValueError('Exact source device numbers changed')
    deploy['cooldown_start']='deploy';deploy['parameters']['advanced_build_mask']=1
    deploy['connectivity']={'rule':'rule/ch3/crate_reference_connectivity','parameters':{}}
    p['rules'].append({'id':'rule/ch3/crate_reference_connectivity','kind':'rule','contract':'deploy.connectivity',
         'implementation':{'type':'provider','provider':'model.deploy.ground_connectivity'},
         'parameters':{'diagonal':True,'allow_corner_cut':False},
         'metadata':{'reference':'https://prts.wiki/w/障碍物','policy':'Every explicitly protected original ground start/end must remain connected; conservative no-corner temporary blocked-cell test, actual movement retains obstacle cost1000'}})
    p['manifest']['id']+='/deploy_start_connectivity_v3'
    p['manifest']['metadata'].update(parent_module_sha256=PIN,source_plan_sha256=PLAN_PIN,
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_card_policy=raw['_cardPolicy'],source_ignoreBlockAnyRoutes=raw['_ignoreBlockAnyRoutes'],
        source_advanced_build_mask=raw['_buildCondition']['advancedBuildableMask'],required_contracts=['deploy.connectivity','deploy.cooldown','blocking.obstacle'],
        model_gaps=[],source_complete_for_declared_profile=True,native_runtime_ready=False,
        feedback_pending=['Source2025 asset versus fixed20260929 table','Declared no-corner/cell-rounding connectivity comparator versus native navigation','Reference typical obstacle cost1000 versus native weighting precision'],
        scope='Executable exact source card stats plus explicit reference fixed fee/DEFAULT5sec/forbid-seal/1000weight profile; stage evidence and independent consumer review required',
        whole_stage_executed=False,actual_client_verified=False)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Reference crate v3 bytes changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'source_cost':5,'cooldown_start':'deploy','connectivity':True,'obstacle_weight':1000}))
