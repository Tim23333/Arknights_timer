"""Source-backed EMP skill/device slice; tile overlays stay an explicit gap."""
from copy import deepcopy
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter01_sources/native.reference.json'
RANGES=ROOT.parent/'unpack_work/campaign_tables/range_table.reference_56a.json'
OUTPUT=ROOT/'packages/campaign/chapter01_devices/emp.partial.json'
REFERENCE=ROOT/'packages/campaign/chapter01_devices/emp.source.json'
RANGE_SHA='a98344d688a8933c4dd7ddaae3cb76c4347295359a18b60b918042cc2542d9d9'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def raw_component(source,name):
    values=[c for c in source['components'].values() if c['native_class']==name]
    if len(values)!=1:raise ValueError('EMP source component missing/ambiguous: '+name)
    return deepcopy(values[0]['raw'])


def build():
    if sha(RANGES)!=RANGE_SHA:raise ValueError('Pinned EMP range table changed')
    stage=read(SOURCE)['stages']['level_main_01-12'];character=stage['predefined_character_sources']['trap_002_emp']
    skill=stage['predefined_skill_sources']['sktok_emp']['levels'][0]
    prefab=stage['predefined_prefab_sources']['trap_002_emp'];skill_prefab=stage['predefined_skill_prefabs']['sktok_emp']
    for source in (prefab['source'],skill_prefab['source']):
        if sha(ROOT.parent/source['path'])!=source['sha256']:raise ValueError('EMP original asset changed')
    phase=character['phases'][0];low,high=phase['attributesKeyFrames'];level=10
    stats={key:float(Fraction(str(value))+(Fraction(str(high['data'][key]))-Fraction(str(value)))*Fraction(level-low['level'],high['level']-low['level']))
        for key,value in low['data'].items() if isinstance(value,(int,float)) and not isinstance(value,bool)}
    if (stats['atk'],stats['maxHp'],stats['blockCnt'])!=(1000,100,0):raise ValueError('EMP E0L10 stat source changed')
    bb={p['key']:p['value'] for p in skill['blackboard']};sp=skill['spData']
    attack=raw_component(skill_prefab,'MeleeAttack');cast=raw_component(skill_prefab,'CastSkillWithCost')
    retirement=raw_component(skill_prefab,'ActionToOwner');trap=raw_component(prefab,'MapDependentTrap')
    mode=raw_component(prefab,'TrapMode');passive=raw_component(prefab,'PassiveBuffAbility')
    assert (sp['spCost'],sp['initSp'],bb['cost'],bb['stun'])==(5,0,10,7)
    assert (attack['_preDelay'],attack['_cooldown'],attack['_damageType'],attack['_atkScale'])==(.75,1.5,2,1)
    assert attack['_selectTargetTiming']==1 and attack['_allowNoTarget']==0 and cast['_allowNoTarget']==1
    assert retirement['_runActionOnEvent']==3 and retirement['_onlyRunOnce']==1
    actions=json.loads(retirement['_actions']['SerializedState'])
    assert len(actions)==1 and all(actions[0][k] is True for k in ('_withdrawSource','_switchToDeadState','_force'))
    assert passive['_buffs'][0]['attributes']['abnormalFlags']==[5]
    assert (trap['_sideType'],trap['_category'],trap['_occupiedRemainingCharacterCnt'])==(1,2,0)
    grids=read(RANGES)[skill['rangeId']]['grids']
    assert len(grids)==9 and {(g['row'],g['col']) for g in grids}=={(r,c) for r in (-1,0,1) for c in (-1,0,1)}
    native_inst=stage['native_level_document']['predefines']['tokenInsts'][0]
    assert native_inst['inst']['characterKey']=='trap_002_emp' and native_inst['inst']['level']==10 and native_inst['alias'] is None
    rows=len(stage['native_level_document']['mapData']['map'])
    position={'row':rows-1-native_inst['position']['row'],'col':native_inst['position']['col']}
    reference={'schema':'ark-sim/chapter01-emp-source/v1','source_sha256':sha(SOURCE),
        'range_table':{'path':str(RANGES),'sha256':RANGE_SHA,'range':read(RANGES)[skill['rangeId']],
            'url':'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/56aee3d6c5a29c3a0d192456d70d14252cbb0804/cn/gamedata/excel/range_table.json'},
        'character':character,'selected_skill':skill,'prefab':prefab,'skill_prefab':skill_prefab,
        'level_config':native_inst,'E0L10_linear_stats':stats,'native_position':native_inst['position'],'V2_position':position,
        'enum_declaration_bindings':{'INVINCIBLE':5,'ON_CAST_END':3,'TRAP_OR_ITEM':2,'WALK_ONLY':1},
        'native_method_bodies_recovered':False,'external_2025_token_vs_local_2026_version_pending':True}
    retirement_condition="inputs.payload.source == context.owner.id and inputs.payload.ability == 'ability/chapter01_emp/burst'"
    package={'schemaVersion':2,'status':'partial_device_model_tile_overlay_not_implemented',
        'manifest':{'id':'package/chapter01/emp_slice','version':'0.1','requires':['preset/ark_standard'],
            'metadata':{'native_id':'trap_002_emp','source_sha256':sha(SOURCE),'builder_sha256':sha(Path(__file__)),
                'source_range_sha256':RANGE_SHA,'client_pending':['CastSkillWithCost finish-clock/callback and category filters','native token2025/local2026 correspondence'],
                'model_gaps':['MapDependentTrap/TrapMode live tile buildability/passability/height overlay and ownership cleanup'],
                'formal_approval':False}},
        'entities':[{'id':'unit/chapter01_emp','kind':'entity','tags':['ally','device','profession:TRAP'],
            'metadata':{'native_id':'trap_002_emp','config':{'elite_phase':0,'level':10,'potential_rank':0,'favor':0,'skill_level':1},
                'native_category':2,'native_side':1,'native_alias':None,'native_tile_fields_preserved':mode},
            'components':{'attributes':{'base':{'max_hp':100,'atk':1000,'def':0,'mres':0,'attack_speed_ratio':1,'block_count':0}},
                'resources':{'hp':{'initial':100,'capacity':100,'role':'health'},
                    'sp':{'initial':0,'capacity':5,'recovery_rate':1,'recovery':{'mode':'periodic','interval_seconds':1},
                        'parameters':{'freeze_while_cast':True,'freeze_cast_modes':['manual'],'pause_at_full':True}}},
                'spatial':{},'abilities':['ability/chapter01_emp/burst'],'buffs':{'initial':['buff/chapter01_emp/invincible']},
                'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'policy':'policy/ark_ground_deploy','base_cost':5,'capacity':0,'cooldown_seconds':5,'terrain':'ground'}}}],
        'abilities':[{'id':'ability/chapter01_emp/burst','kind':'ability','duration_seconds':1.5,
            'activation':{'mode':'manual','costs':[{'resource':'sp','amount':5},{'resource':'dp','amount':10,'owner':'battle'}],
                'parameters':{'allow_no_targets':True}},
            'timeline':[{'at_seconds':.75,'effect':{'op':'damage','selector':'selector/chapter01_emp/enemies','damage_type':'arts','scale':1,
                'on_success':[{'op':'apply_buff','buff':'buff/chapter01_emp/stun'}]}}],
            'events':[{'event':'ability.finished','condition':retirement_condition,'effects':[{'op':'retire','target':'source','parameters':{'reason':'dead'}}]}],
            'metadata':{'native_skill_id':'sktok_emp','clock_profile':'specified .75s packet/1.5s cast-end model; callback timing client_pending',
                'target_profile':'resample before spell at packet .75s; all living ground enemies in grid x-4; noTarget cast allowed by root'}}],
        'buffs':[{'id':'buff/chapter01_emp/invincible','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/chapter01_emp/invincible'}]},
            {'id':'buff/chapter01_emp/stun','kind':'buff','duration_seconds':7,'control':{'attack':False,'move':False,'abilities':False}}],
        'rules':[{'id':'rule/chapter01_emp/invincible','kind':'calculation_rule','contract':'damage.pipeline',
            'implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.result'}}],
        'selectors':[{'id':'selector/chapter01_emp/enemies','kind':'selector','limit':None,
            'region':{'type':'grid_offsets','offsets':[[g['row'],g['col']] for g in grids],'rotate_with_facing':True},
            'filters':[{'tag':'enemy'},{'tag':'ground'},{'state':'alive'}]}],
        'scenarioDraft':{'id':'scenario/chapter01_emp_slice','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':11},
            'resources':{'dp':{'initial':50,'capacity':99}},'initialEntities':[{'definition':'unit/chapter01_emp','position':position,'facing':'up'}],
            'waves':[],'objectives':{}}}
    return reference,package


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    reference,package=build()
    for path,value in [(REFERENCE,reference),(OUTPUT,package)]:
        raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        if args.check:
            if not path.exists() or path.read_bytes()!=raw:raise ValueError('EMP source/output changed: '+str(path))
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    print(json.dumps({'output':str(OUTPUT),'package_sha256':sha(OUTPUT),'formal_approval':False}))
