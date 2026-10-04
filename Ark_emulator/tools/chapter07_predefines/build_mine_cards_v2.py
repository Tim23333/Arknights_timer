"""Bind source mine card stock/cost/capacity/cooldown without altering enemy HP."""
import json
from pathlib import Path
from tools.chapter07_predefines.build_ore_v1 import ROOT, SOURCE, sha


def main():
    folder=ROOT/'packages/campaign/chapter07_predefines_consumer'
    p=json.loads((folder/'mine.module.v1.json').read_bytes())
    source=json.loads(SOURCE.read_bytes())
    native=next(i['raw_native'] for i in source['stages']['level_main_07-16']['instances']
                if i['raw_native']['inst']['characterKey']=='trap_012_mine')
    unit=p['entities'][0]
    unit['components']['attributes']['base'].update(deploy_cost=5,redeploy_time=7)
    unit['components']['deployable']={
        'base_cost':5,'terrain':'ground','capacity':0,'cooldown_seconds':7,
        'cooldown_start':'retire','refund_ratio':0,
        'parameters':{'max_instances':1,'advanced_build_mask':1},
        'stock':{'resource':'stock_ch7_mine','amount':1},
        'rules':{'deploy.cost':'rule/ch7/predefined/mine/card_cost'}}
    unit['metadata']={'native_card':native,'stock_resource':'stock_ch7_mine',
                      'native_occupiedRemainingCharacterCnt':0,
                      'source_deployment_semantics':'cost5/stock15/capacity0/max1/retirecooldown7/refund0; initial stock supplied by native stage adapter'}
    p['rules'].append({'id':'rule/ch7/predefined/mine/card_cost','kind':'rule',
                      'contract':'deploy.cost','implementation':{'type':'expression','expression':'inputs.base_cost'}})
    for b in p['buffs']:
        if b['id'].endswith('/mode_timer'):
            b['effects'][0]['condition']="inputs.targets[0].components.behavior.state == 'mode0'"
    for entry in p['abilities'][0]['timeline']:
        if entry['effect']['op']=='area':
            entry['effect']['effects'][1]['parameters']={'consider_unhurtable':False}
    p['manifest']['id']='package/ch7/predefined/mine/v2'
    p['manifest']['metadata']['source_locks'][str(Path(__file__).resolve())]=sha(Path(__file__))
    p['manifest']['metadata']['reference_policy'] += (
        ' Frame resource recovery includes tick0, 750 steps reach SP25 at tick749 in currentfloat backend; explicit reference calibration pending. '
        'Mode timer performs only mode0->mode1 once. Native card stock15 belongs to battle resource, fixed fee and zero slot occupation.')
    out=folder/'mine.module.v2.json';assert not out.exists()
    out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha256':sha(out),'native_stock':native['initialCnt']}))


if __name__=='__main__':main()
