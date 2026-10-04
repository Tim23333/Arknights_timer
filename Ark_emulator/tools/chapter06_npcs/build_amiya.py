"""Exact native no-skill Amiya source numbers, one main action-bearing projectile."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim.domains.selection import DEFAULT_STATE
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json';INPUTS=ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source=json.loads(SOURCE.read_bytes());row=next(r for r in json.loads(INPUTS.read_bytes())['records'] if r['character_id']=='char_002_amiya');stats=row['stats']
    assert row['skill_index']==-1 and row['normal_attack_source']['native_class']=='MultiRangedAttack'
    raw=row['normal_attack_source']['raw'];assert raw['_additionalTimes']==2 and raw['_onlyFeedActionsToFirstOne']==1
    cfg=deepcopy(source['prefabs']['char_002_amiya']['components']['-4721031247130689434']['raw'])
    assert cfg['_targetMotion']==3 and cfg['_targetSide']==2
    movement=next(c['raw'] for c in source['projectiles']['projectile_amiya']['components'].values() if c['native_class']=='AmiyaDefaultMovement')
    assert movement['_startDistance']==2.5 and movement['_startDuration']==movement['_time']==.15000000596046448
    defaults=deepcopy(DEFAULT_STATE);defaults.update(side=0,motion=1,category=1,unit_type=1)
    uid='unit/ch6/npc/char_002_amiya';aid='ability/ch6/npc/amiya_normal';sid='selector/ch6/npc/amiya';pid='projectile/ch6/npc/amiya'
    eligible='rule/ch6/npc/amiya_eligible';motion='rule/ch6/npc/amiya_motion';collision='rule/ch6/npc/amiya_collision'
    rules=[{'id':eligible,'kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
        {'id':motion,'kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'reference.c6.amiya_movement'},
            'parameters':{'start_duration':movement['_startDuration'],'travel_duration':movement['_time'],'start_distance':movement['_startDistance']}},
        {'id':collision,'kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}]
    unit={'id':uid,'kind':'entity','tags':['player','ground','native_npc'],'metadata':{'native_character':'char_002_amiya','native_instance':row['native_instance']},
        'components':{'attributes':{'base':{'max_hp':stats['maxHp'],'atk':stats['atk'],'def':stats['def'],'mres':stats['magicResistance'],
            'attack_interval':stats['baseAttackTime'],'attack_speed_ratio':1,'block_count':stats['blockCnt']}},
            'resources':{'hp':{'initial':stats['maxHp'],'capacity_attribute':'max_hp','role':'health'}},'spatial':{},'selection_state':defaults,
            'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[aid],'buffs':{'initial':['buff/ch6/npc/amiya_sp_talent']}}}
    ranges=ROOT/'ark_emulator/data_range_table.json';rangevalue=json.loads(ranges.read_bytes())[row['range_id']]
    selector={'id':sid,'kind':'selector','region':{'type':'grid_offsets','offsets':[[-c['row'],c['col']] for c in rangevalue['grids']]},
        'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1,
        'eligibility':{'rule':eligible,'parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}}}
    buff={'id':'buff/ch6/npc/amiya_sp_talent','kind':'buff','events':[
        {'event':'damage.accepted','condition':'inputs.payload.source == context.owner.id and inputs.payload.amount > 0',
            'effects':[{'op':'modify_resource','resource':'sp','delta':2,'parameters':{'if_resource_present':True}}]},
        {'event':'combat.kill','condition':'inputs.payload.source == context.owner.id',
            'effects':[{'op':'modify_resource','resource':'sp','delta':8,'parameters':{'if_resource_present':True}}]}]}
    ability={'id':aid,'kind':'ability','activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},'initial_cooldown_seconds':4/30,
        'selector':sid,'target_capture':'at_cast','timeline':[{'at_seconds':raw['_preDelay'],'effect':{'op':'damage','damage_type':'arts','scale':1,
            'projectile_definition':pid,'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}}],
        'metadata':{'normal_attack_source':row['normal_attack_source'],'empty_visual_projectile_source':source['projectiles']['projectile_amiya_empty'],
            'visual_additional_times':2,'visual_only_no_extra_damage':True}}
    projectile={'id':pid,'kind':'projectile','motion':{'rule':motion},'collision':{'rule':collision,'parameters':{'enabled':True,'radius':0}},
        'lifetime_seconds':10,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,
        'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel','target_hidden':'cancel',
            'finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True}}
    data={'schemaVersion':2,'manifest':{'id':'package/ch6/npc/amiya_reference','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{str(SOURCE.relative_to(ROOT)):sha(SOURCE),str(INPUTS.relative_to(ROOT)):sha(INPUTS),str(ranges.relative_to(ROOT)):sha(ranges)},
        'builder_sha':sha(Path(__file__)),'native_no_skill':True,'policies':{
            'timing':'4frame first begin plus nativepreDelay .48300001025 ceil15; not fake3 copies of19f OnAttack because waitForAttackEvent0.',
            'trajectory':'Two source .15000000596 stages modeled as planar interpolation; startDistance2.5 retained, exact nativecurvature/sourcehandoff unresolved replaceable policy.',
            'additional_visual':'Native onlyFeedActionsToFirstOne1: two empty projectile visuals preserved as metadata, no extra combat damage.',
            'talent':'Attack2/kill8 source BB retained; native no selected skill produces no fabricated SP store; later selectedskill uses newinput.',
            'source_lifetime':'Live source-owner hooks on retained projectiles explicit reference policy.'},
        'complete_source_policies':False,'whole_stage_executed':False,'client_verified':False}},'rules':rules,'entities':[unit],
        'buffs':[buff],'abilities':[ability],'selectors':[selector],'projectiles':[projectile]}
    path=ROOT/'packages/campaign/chapter06_npcs/amiya.model.json';assert not path.exists();path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(path),'hp':stats['maxHp'],'atk':stats['atk'],'selected_skill':None}))


if __name__=='__main__':main()
