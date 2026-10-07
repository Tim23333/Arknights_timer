"""Independent static native-enemy conversion audit; no model acceptance."""
import json,hashlib,sys,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter10_stage_source_peer_v1.source_preflight import exact
SOURCE=ROOT/'packages/campaign/chapter0_source_prepare/enemies.native.v1.json';PLAN=ROOT/'packages/campaign/chapter0_source_prepare/source.plan.v3.json';MODULE=ROOT/'packages/campaign/chapter0_consumers/enemies.module.v1.json';OUT=ROOT/'validation/campaign/chapter0_source_peer_v1';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    paths=[SOURCE,PLAN,MODULE,ROOT/'tools/chapter0_source_prepare/build_consumers_v1.py',Path(__file__)];before={str(p):sha(p) for p in paths}
    assert sha(SOURCE)=='ad8a610ad5b3fbebe16a000f5098084accab4a346492dd686e937f22925fe360' and sha(PLAN)=='b0fde50c99f7f6ddcbc55079b46d822178a5da71f52ab5bc9cc488b54e66c95a' and sha(MODULE).startswith('233febf9')
    source=json.loads(SOURCE.read_bytes());plan=json.loads(PLAN.read_bytes());module=json.loads(MODULE.read_bytes());entities={e['id']:e for e in module['entities']};abilities={a['id']:a for a in module['abilities']};selectors={s['id']:s for s in module['selectors']};assert len(entities)==8 and len(abilities)==len(selectors)==7
    assert [t['native_id'] for t in plan['targets']]==['main_00-10','main_00-11']
    for dataset in [source,plan]:
        for path,pin in dataset['source_locks'].items():
            locked=Path(path)
            if not locked.is_absolute():locked=ROOT.parent/locked
            assert sha(locked)==pin,path
    rows=[]
    for id,variant in source['variants'].items():
        key=variant['prefab_key'];raw=variant['native_enemy']['resolved'];attrs=raw['attributes'];root=source['prefabs'][key]['components'][str(variant['root_path_id'])]['raw'];mode=variant['modes'][0];node=mode['nodes']['_combat'];e=entities['unit/ch0/'+key]
        assert len(variant['modes'])==1 and mode['raw']['_generalAbilities']==[] and root['_commonAbilities']==[] and variant['passive_and_skill_components']==[] and root['_delayToBorn']==0
        assert root['_sideTypeIndex']==1 and e['components']['selection_state']['side']==1
        expected={'max_hp':attrs['maxHp'],'atk':attrs['atk'],'def':attrs['def'],'mres':attrs['magicResistance'],'move_speed':attrs['moveSpeed'],'attack_speed_ratio':attrs['attackSpeed']/100,'attack_interval':attrs['baseAttackTime'],'mass_level':attrs['massLevel'],'block_cost':root['_blockVolume']};exact(expected,e['components']['attributes']['base'])
        exact({'hp':{'role':'health','initial':attrs['maxHp'],'capacity':attrs['maxHp']}},e['components']['resources']);assert e['components']['lifecycle']['leak_loss']==raw['lifePointReduce']==1
        assert attrs['hpRecoveryPerSec']==attrs['spRecoveryPerSec']==0 and attrs['stunImmune'] is False and e['components']['selection_state']['abnormal_immunes']==[]
        m=2 if raw['motion']=='FLY' else 1;assert e['components']['selection_state']['motion']==m and e['components']['spatial']=={'motion_mode':m-1,'route_motion_mode':m-1}
        if node['native_class']=='MeleeAttack':
            n=node['raw'];assert n['_selectTargetSource']==2 and n['_preDelay']==0 and n['_waitForAttackEvent']==1 and n['_damageType']==1
            a=abilities['ability/ch0/'+key+'/combat'];b=node['animation_binding'];hit=next(x for x in b['events'] if x['name']=='OnAttack');assert hit['exact_authored_frame'] and b['duration']['exact_authored_frame']
            exact(a['timeline'],[{'at_seconds':hit['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':n['_atkScale']}}]);exact(a['activation'],{'mode':'automatic_attack','interval_seconds':attrs['baseAttackTime']});exact(a['duration_seconds'],b['duration']['seconds']);exact(a['metadata']['native_owned_node'],node)
            sel=selectors[a['selector']];exact(sel['region'],{'type':'all','blocked_only':True});exact(sel['filters'],[{'tag':'player'},{'state':'alive'}]);assert sel['limit']==1 and e['components']['abilities']==[a['id']]
            row={'key':key,'hit_frame':hit['frame'],'full_frame':b['duration']['frame'],'native_timeMode':n['_timeMode'],'native_maxAnimScale':n['_maxAnimScale'],'native_affectedBySlowDown':n['_affectedBySlowDown'],'native_selectTargetTiming':n['_selectTargetTiming'],'native_interrupt_target_dead':n['_interuptIfTargetDead']}
        else:
            assert key=='enemy_1005_yokai' and node['native_class']=='EmptyAnimatedAbility' and raw['motion']=='FLY' and attrs['atk']==0 and e['components']['abilities']==[]
            assert mode['nodes']['_attack']['status']==mode['nodes']['_attackTrigger']['status']=='native_null';row={'key':key,'nonattacking_actual_empty_combat':True,'fly_physical_and_route_mode':1}
        exact(e['metadata']['native_variant'],variant);exact(e['metadata']['root_component'],root);rows.append(row)
    assert sorted(r['hit_frame'] for r in rows if 'hit_frame' in r)==[10,10,12,12,12,18,19]
    after={str(p):sha(p) for p in paths};assert before==after
    report={'schema':'ark-sim/chapter0-source-consumer-static-peer/v1','static_source_input_approved':True,'source_before':before,'source_after':after,'source_equal':True,'source_conversions':rows,'side_encoding':'Literal Enemy._sideTypeIndex=1 retained as V2 enemy side index1. This is an index, not SideType bitmask1(ALLY)/2(ENEMY); no inverted new mapping applied.','boundaries':['category1/unit_type2 are declared reference selection classification; no recovered native getter/body proof.','All selected stunImmuneFalse and zero HP/SP regeneration agree; unresolved/undefined other immunity flags are not certified true native absence.','Native maxAnimScale/timeMode/affectedBySlowDown/selectTargetTiming fields are preserved in metadata, but dynamic ASPD/slowing/target-death timing behavior needs separate actual gate; constant100ASPD conversion alone cannot prove those behaviors.','Yokai EmptyAnimatedAbility retained as source evidence; no fabricated attack/trigger. Visual animation is not modeled.','No stage story/popups/blocker fade/route conversion or whole process is approved by this enemy conversion review.','Source assets/version policy remains as embedded; parser rejects missing ownership, general/common lists actually empty.'], 'model_approved':False,'whole_stage_approved':False,'client_verified':False,'simulation_started':False}
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'source.review.v1.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'static_source_input_approved':True,'sha256':sha(path),'module_SHA':sha(MODULE)}))
if __name__=='__main__':main()
