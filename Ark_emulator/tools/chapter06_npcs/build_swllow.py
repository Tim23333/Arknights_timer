"""Exact no-skill E2L25 Yan/Swallow NPC, source-backed attack and critical talent."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json'
INPUTS=ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json'
OUT=ROOT/'packages/campaign/chapter06_npcs/swllow.model.json'
CID='char_367_swllow';UID='unit/ch6/npc/'+CID;AID='ability/ch6/npc/swllow_normal'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    source=json.loads(SOURCE.read_bytes());inputs=json.loads(INPUTS.read_bytes())
    row=next(r for r in inputs['records'] if r['character_id']==CID);s=row['stats'];raw=row['normal_attack_source']['raw']
    assert row['skill_index']==-1 and row['selected_skill'] is None
    assert raw['_damageType']==1 and raw['_waitForAttackEvent']==1 and raw['_projectileKey']=='projectile_swllow'
    assert raw['_atkScale']==1 and raw['_activeBuffs']==[] and raw['_selectTargetSource']==2
    anim=row['normal_animation']['bindings_by_face']['front'];assert [(e['name'],e['frame']) for e in anim['events']]==[('OnAttack',2)]
    begin=anim['begin_animation']['duration']['frame'];assert begin==5
    talent=row['selected_talents'][0]['candidate'];bb={r['key']:r['value'] for r in talent['blackboard']}
    assert bb=={'attack_speed':6.0,'prob':.15,'atk_scale':1.5}
    proc=source['bson_templates']['templates']['critical_atkscale']['parsed']['eventToActions']['ON_CALCULATE_DAMAGE']
    assert [a['$type'].split('+')[1].split(',')[0] for a in proc]==['Dice','AtkScaleUp']
    native=source['projectiles'][raw['_projectileKey']]
    movement=next(c['raw'] for c in native['components'].values() if c['native_class']=='AdvancedMovement')
    projectile=next(c['raw'] for c in native['components'].values() if c['native_class']=='SimpleProjectile')
    assert movement['_speed']==15 and projectile['_lifeTime']==10 and projectile['_maxHitNum']==1 and projectile['_stopWhenSourceInvalid']==0
    ranges=ROOT/'ark_emulator/data_range_table.json';rng=json.loads(ranges.read_bytes())[row['range_id']]
    SID='selector/ch6/npc/swllow';PID='projectile/ch6/npc/swllow';CRIT='rule/ch6/npc/swllow_critical';BUFF='buff/ch6/npc/swllow_talent'
    request="{'op':'damage','damage_type':inputs.effect.damage_type,'attack':inputs.effect.attack,'defense':inputs.effect.defense,'resistance':inputs.effect.resistance,'scale':inputs.effect.scale*(params.atk_scale if nodes.proc else 1),'additions':inputs.effect.additions}"
    rules=[{'id':CRIT,'kind':'calculation_rule','contract':'damage.request','parameters':{'prob':bb['prob'],'atk_scale':bb['atk_scale']},
        'implementation':{'type':'graph','nodes':[{'id':'proc','expression':'inputs.samples[0].value < params.prob'},
            {'id':'result','expression':"{'accepted':True,'effect':"+request+",'effects':[],'events':[]}"}],'output':'nodes.result'}},
        {'id':'rule/ch6/npc/swllow_windup','kind':'calculation_rule','contract':'ability.windup','parameters':{'minimum':.01},
            'implementation':{'type':'expression','expression':'inputs.timing_parameters.seconds / max(inputs.attributes.attack_speed_ratio,params.minimum)'}},
        {'id':'rule/ch6/npc/swllow_trajectory','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},
        {'id':'rule/ch6/npc/swllow_collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}]
    unit={'id':UID,'kind':'entity','tags':['player','ground','native_npc'],'metadata':{'native_character':CID,'native_instance':row['native_instance']},
        'components':{'attributes':{'base':{'max_hp':s['maxHp'],'atk':s['atk'],'def':s['def'],'mres':s['magicResistance'],
            'attack_interval':s['baseAttackTime'],'attack_speed_ratio':s['attackSpeed']/100,'block_count':s['blockCnt'],'taunt_level':s['tauntLevel']}},
            'resources':{'hp':{'initial':s['maxHp'],'capacity_attribute':'max_hp','role':'health'}},'spatial':{},
            'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},
            'abilities':[AID],'buffs':{'initial':[BUFF]}}}
    ability={'id':AID,'kind':'ability','activation':{'mode':'automatic_attack','settle_blocking':True,'parameters':{'auto_only':True}},
        'initial_cooldown_seconds':begin/30,'selector':SID,'target_capture':'at_cast','rules':{'ability.windup':'rule/ch6/npc/swllow_windup'},
        'timeline':[{'at_seconds':2/30,'effect':{'op':'damage','damage_type':'physical','scale':1,'projectile_definition':PID,
            'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}}],
        'metadata':{'native_attack':deepcopy(raw),'animation_source':deepcopy(row['normal_animation'])}}
    buff={'id':BUFF,'kind':'buff','modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':bb['attack_speed']/100}],
        'damage_hooks':[{'phase':'before','rule':CRIT,'samples':{'stream':'imp','count':1}}]}
    selector={'id':SID,'kind':'selector','region':{'type':'grid_offsets','offsets':[[-r['row'],r['col']] for r in rng['grids']]},
        'filters':[{'tag':'enemy'},{'tag':'ground'},{'state':'alive'}],'limit':1,'parameters':{'include_blocked':True}}
    proj={'id':PID,'kind':'projectile','motion':{'rule':'rule/ch6/npc/swllow_trajectory','parameters':{'mode':'homing','speed':movement['_speed']}},
        'collision':{'rule':'rule/ch6/npc/swllow_collision','parameters':{'enabled':True,'radius':0}},'lifetime_seconds':projectile['_lifeTime'],
        'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,
        'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel','target_hidden':'cancel',
            'finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True}}
    return {'schemaVersion':2,'manifest':{'id':'package/ch6/npc/swllow','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{str(SOURCE.relative_to(ROOT)):sha(SOURCE),str(INPUTS.relative_to(ROOT)):sha(INPUTS),str(ranges.relative_to(ROOT)):sha(ranges)},
        'builder_sha':sha(Path(__file__)),'native_no_skill':True,'native_npc_not_fixed12':True,
        'policies':{'windup':'Normalized ASPD and ceil; initial five-frame begin only. Native three-part coroutine restart behavior remains replaceable.',
            'selection':'Native range/ground trait and blocked inclusion; generic player target ordering, later source-priority audit required.',
            'crit':'Source ON_CALCULATE_DAMAGE Dice15% then scale1.5, one existing imp-stream draw per accepted eligible packet; no forced seed.',
            'sp':'No selected skill -> no fabricated SP capacity or skill. Talent ASD6 remains active; any later selected skill requires new input.'},
        'complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}},
        'rules':rules,'entities':[unit],'abilities':[ability],'buffs':[buff],'selectors':[selector],'projectiles':[proj]}


def main():
    assert not OUT.exists();data=build();OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(OUT),'npc':CID,'hp':data['entities'][0]['components']['resources']['hp']['initial']}))


if __name__=='__main__':main()
