"""Independent native operands in actual C6 joined package, before full run."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.chapter06_review.stage_converter_v7 import exact
from tools.chapter06_review.stage_converter_v6 import route_ir


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    pack=ROOT/'validation/campaign/chapter06_join_draft_v1/06-14.json';plan=ROOT/'packages/campaign/chapter06_plans/source.plan.json'
    p=json.loads(pack.read_bytes());native=json.loads(plan.read_bytes())['stages']['level_main_06-14']['native_document'];scene=p['scenarioDraft']
    defs={d['id']:d for d in p['definitions']};rows=len(native['mapData']['map']);records=[]
    for w,sw in zip(native['waves'],scene['timeline']['waves']):
        assert (w['preDelay'],w['postDelay'],w['maxTimeWaitingForNextWave'])==(sw['pre_delay_seconds'],sw['post_delay_seconds'],sw['max_wait_seconds'])
        for f,sf in zip(w['fragments'],sw['fragments']):
            assert f['preDelay']==sf['pre_delay_seconds'] and len(f['actions'])==len(sf['actions'])
            for a,sa in zip(f['actions'],sf['actions']):
                assert exact(a,sa['metadata']['native_action'])
                assert (a['count'],a['preDelay'],a['interval'],a['managedByScheduler'],not a['dontBlockWave'],a['blockFragment'])==(sa['count'],sa['delay_seconds'],sa['interval_seconds'],sa['managed'],sa['blocks_wave'],sa['blocks_fragment'])
                if a['actionType']!='SPAWN':
                    assert a['actionType'] in ('DISPLAY_ENEMY_INFO','PREVIEW_CURSOR') and sa['kind']=='control'
                    assert defs[sa['definition']]['steps'][0]['effects'][0]['payload']['native_action']==a
                    continue
                assert sa['kind']=='spawn';raw=native['routes'][a['routeIndex']];converted=route_ir(raw,rows)
                actual=sa['spawn']['route'];assert all(exact(actual[k],v) for k,v in converted.items())
                assert exact(sa['spawn']['placement']['offset'],{'row':-raw['spawnOffset']['y'],'col':raw['spawnOffset']['x']})
                assert exact(sa['spawn']['placement']['random_range'],{'row':raw['spawnRandomRange']['y'],'col':raw['spawnRandomRange']['x']})
                records.append({'key':a['key'],'count':a['count'],'route_index':a['routeIndex'],'passed':True})
    assert sum(r['count'] for r in records)==50
    assert len(scene['roster'])==12 and scene['parameters']['deploy_capacity']==9
    assert scene['resources']['dp']['initial']==10 and scene['resources']['life']=={'initial':3,'capacity':3}
    assert scene['resources']['dp']['recovery']['interval_seconds']==native['options']['costIncreaseTime']
    assert defs[scene['rules']['movement.speed']]['parameters']['multiplier']==native['options']['moveMultiplier']==.5
    raw_tiles=[native['mapData']['tiles'][i] for row in native['mapData']['map'] for i in row]
    masks={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3};build={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3}
    for raw,tile in zip(raw_tiles,scene['map']['tiles']):
        assert tile['tileKey']==raw['tileKey'] and tile['passableMask']==masks[raw['passableMask']] and tile['buildableType']==build[raw['buildableType']]
        assert exact(tile['blackboard'],raw['blackboard']) and exact(tile['effects'],raw['effects']) and tile['heightType']==raw['heightType']
    assert scene['seed']==native['randomSeed'] and len(scene['initialEntities'])==2
    for raw,item in zip(native['predefines']['tokenInsts'],scene['initialEntities']):
        assert exact(raw,item['parameters']['native_instance']) and item['active'] is False and item['registration_key']==raw['alias']
        assert item['position']=={'row':rows-1-raw['position']['row'],'col':raw['position']['col']}
    assert len(scene['branches']['frstar_frosts']['phases'])==1
    out=ROOT/'validation/campaign/chapter06_stage_source_join_v1';out.mkdir(exist_ok=False)
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'source_sha':sha(plan),'package_sha':sha(pack),'actions':records,
        'source_births':50,'fixed12_selected':12,'native_options_map_routes_predefines_unchanged':True,
        'scope':'Root exact source operand checks for compiled ordinaryBoss draft package; no final sourceBoss/fullstage/client acceptance'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':sha(target)}))


if __name__=='__main__':main()
