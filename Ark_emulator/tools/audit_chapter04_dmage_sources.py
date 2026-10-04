"""Exact dmage source graph, enum facts and declared reference-policy audit."""
from pathlib import Path
import argparse,hashlib,json

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter04_sources/native.reference.json'
PIN='3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603'
DUMP=ROOT.parent/'Ark_data/dump.cs'
OUT=ROOT/'packages/campaign/chapter04_dmage/source.reference.json'

def sha(p):
    digest=hashlib.sha256()
    with p.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def build():
    assert sha(SOURCE)==PIN
    dump_before=sha(DUMP);s=json.loads(SOURCE.read_bytes())
    variant_key='enemy_1022_dmage@0/ed10af8ce8e1725f'
    variant=s['variants'][variant_key];prefab=s['prefabs'][variant['prefab_key']]
    skill_component=next((key,value) for key,value in prefab['components'].items() if value.get('native_class')=='EnemySkill')
    component_id,skill=skill_component
    trigger_key=str(skill['raw']['_trigger']['m_PathID']);trigger=prefab['components'][trigger_key]
    trigger_go=trigger['gameobject_path_id']
    selector=next((key,value) for key,value in prefab['components'].items()
        if value.get('native_class')=='AdvancedSelector' and value['gameobject_path_id']==trigger_go)
    skill_go=skill['gameobject_path_id']
    attack=next((key,value) for key,value in prefab['components'].items()
        if value.get('native_class')=='RangedAttack' and value['gameobject_path_id']==skill_go)
    animation=next((key,value) for key,value in prefab['components'].items()
        if value.get('native_class')=='ThreePartChannelingAnimation' and value['gameobject_path_id']==skill_go)
    projectile_key=attack[1]['raw']['_projectileKey'];projectile=s['projectiles'][projectile_key]
    basic=variant['modes'][0]['nodes']['_attack']
    enums={};enum_prefixes=('public const FilterUtil.FilterType HATRED_DES =',
        'public const FilterUtil.FilterType NOT_STUNNED_HATRED_DES =',
        'public const Modifier.SourceAttackType BUFF =','public const AbnormalFlag STUNNED =',
        'public const AbnormalFlag SILENCED =','public const BuffData.StatusResistable AUTOMATIC =')
    with DUMP.open(encoding='utf8') as file:
        for number,line in enumerate(file,1):
            text=line.strip()
            for prefix in enum_prefixes:
                if text.startswith(prefix):enums[prefix]={'line':number,'declaration':text,'value':int(text.split('=',1)[1].strip().rstrip(';'))}
    assert [enums[key]['value'] for key in enum_prefixes]==[4,12,4,0,12,2]
    anims=s['animations'][variant['prefab_key']]['parsed']['animations']
    selected_anims={key:anims[key] for key in ['Attack','Skill_Begin','Skill_Loop','Skill_End']}
    assert [selected_anims[key]['duration']['frame'] for key in ['Skill_Begin','Skill_Loop','Skill_End']]==[26,14,20]
    assert selected_anims['Skill_Loop']['events'][0]['frame']==0
    assert skill['raw']['_maxTriggerTime']==1 and attack[1]['raw']['_attackType']==4
    assert selector[1]['raw']['_postFilter']==12
    assert sha(DUMP)==dump_before and sha(SOURCE)==PIN
    geometry=[g for g in prefab['geometry_sources'] if g['gameobject_path_id']==trigger_go]
    bb={row['key']:row['value'] for row in variant['native_enemy']['resolved']['skills'][0]['blackboard']}
    assert bb=={'hit_duration':20.0,'atk_scale':.35,'range_radius':3.0}
    active_buffs=attack[1]['raw']['_activeBuffs']
    assert len(active_buffs)==1 and active_buffs[0]['templateKey']=='empty' and active_buffs[0]['attributes']['abnormalFlags']==[0]
    result={'schema':'ark-sim/chapter04-dmage-source-audit/v1','source_path':str(SOURCE.relative_to(ROOT)),
        'source_sha256':PIN,'variant_id':variant_key,'variant':variant,'prefab_source':prefab['source'],
        'source_graph':{'enemy_skill':{'path_id':component_id,**skill},'skill_trigger':{'path_id':trigger_key,**trigger},
            'skill_selector':{'path_id':selector[0],**selector[1]},'skill_attack':{'path_id':attack[0],**attack[1]},
            'skill_animation':{'path_id':animation[0],**animation[1]},'skill_geometry':geometry,
            'normal_attack':basic,'projectile_key':projectile_key,'projectile':projectile},
        'animations':selected_anims,'blackboard':bb,
        'bson':{'template':'empty','record':s['bson_templates']['templates']['empty'],
            'source':s['bson_templates']['source'],'payload_sha256':s['bson_templates']['payload_sha256'],
            'target_lasso_buff_serialized':False},
        'enums':enums,'dump':{'path':str(DUMP),'sha256':dump_before,
            'native_method_bodies_recovered':False,'required_unknown_bodies':['LassoProjectile.DoLink',
                'LinkProjectile._InitDamageSplitter','EnemySkill._GetRangeRadius','ThreePartChannelingAnimation callbacks']},
        'reference_website':{'url':'https://prts.wiki/w/%E8%90%A8%E5%8D%A1%E5%85%B9%E6%9C%AF%E5%B8%88',
            'checked_date':'2026-10-03','role':'secondary behavior reference, not native method reconstruction',
            'paraphrase':'A captured ground friendly is stunned repeatedly each second during a bounded 20-second link; arts damage rate is35%ATK, silence ends the skill, and stunned units are not selected.'},
        'planned_policies':{'activation':'existing automatic manual ability plus finite one-use resource cost; consume on accepted cast start',
            'targeting':'source postfilter12 maps STUN0 exclusion; taunt/newest-ID deterministic ordering remains explicit replacement',
            'range':'actual skill BB3.0 point radius; raw CircleCollider2D2.0 is fallback source geometry, not silently substituted',
            'windup':'Skill_Begin26 authoredframes then Skill_Loop OnAttack0 launch; not loop14 damage period',
            'flight':'declared planar homing speed10 to captured target; native HarpoonMovement body/physics pending',
            'link_duration':'actual hit_duration20 overrides raw generic linkDuration5/life5 for held phase; raw5 retained for flight limit',
            'damage':'integrate source atk*.35 arts rate using actual quantum packets; Native MeleeModifierSplitter body pending',
            'refresh':'target infinite STUN0 refreshed each1second, all owned leases removed on channel end/interruption/death',
            'caster_hold':'actual self-active STUN0 represented as cast-owned hold; own hold does not interrupt its same cast',
            'recovery':'retain source _minPostDelayWhenProjectileInvalid0.6669999957 alongside authored Skill_End20frames; ceiling quantizer referencepolicy',
            'sp':'SourceAttackType BUFF4 is explicit; continuous damage ignore-SP policy must be declared, not hidden unused params'},
        'runtime_created':False,'whole_stage_executed':False,'client_verified':False,
        'builder_sha256':sha(Path(__file__))}
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        assert OUT.read_bytes()==raw,'Audit source bytes changed'
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with OUT.open('xb') as file:file.write(raw)
    print(json.dumps({'path':str(OUT),'sha256':hashlib.sha256(raw).hexdigest()}))
