"""Correct constant device fee and reference obstacle weight; explicit gaps."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'packages/campaign/chapter03_traps/crate.obstacle.reference_model.json'
PIN='7ba4d02d0ce44b14e5bf091fc6335267d3443073f3a4cc08de64a9ed32a56052'
OUT=ROOT/'packages/campaign/chapter03_traps/crate.reference_v2.partial.json'


def build():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PIN:raise ValueError('Frozen source crate drift')
    p=json.loads(PARENT.read_bytes());unit=p['entities'][0]
    deploy=unit['components']['deployable'];deploy['rules']={'deploy.cost':'rule/ch3/crate_fixed_fee'}
    unit['components']['terrain_overlays'][0]['rule']='rule/ch3/crate_reference_weight'
    p['rules'] += [
        {'id':'rule/ch3/crate_fixed_fee','kind':'rule','contract':'deploy.cost','implementation':{'type':'expression','expression':'inputs.base_cost'},
         'metadata':{'reference':'https://prts.wiki/w/障碍物','policy':'Source device base cost5 for each finite card; does not inherit operator repeat_ratio'}},
        {'id':'rule/ch3/crate_reference_weight','kind':'rule','contract':'terrain.tile_options','parameters':{'obstacle_like_cost':1000,'normal_cost':1},
         'implementation':{'type':'provider','provider':'ark.terrain.tile_options'},
         'metadata':{'reference':'https://prts.wiki/w/障碍物','policy':'Declared reference typical obstacle path weight1000; passableMask is preserved, not a permanent walk wall'}}]
    p['manifest']['id']+='/reference_fee_weight_v2'
    p['manifest']['metadata'].update(parent_source_sha256=PIN,reference_checked_date='2026-10-03',reference_url='https://prts.wiki/w/障碍物',
       builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       required_source_policies={'constant_deployment_cost':5,'cooldown_seconds':5,'cooldown_starts':'after_deploy','path_cost':1000,'forbid_sealing_ground_routes':True},
       model_gaps=['Deploy-start cooldown must use new M63 consumer, not existing retire default',
                   'Reject placement that seals any configured original ground route requires new pure connectivity consumer'],
       native_runtime_ready=False,full_stage_executed=False,actual_client_verified=False)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Reference crate derivative changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'cost':5,'obstacle_weight':1000,'complete':False}))
