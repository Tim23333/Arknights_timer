"""Weedy selected-S3 model with native splash/rupture and explicit physics profile."""
import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.build_attack_skill_recipes import read,sha,character_components
from tools.build_offensive_skill_recipes import projectile_source
from tools.normalize_campaign_operators import interpolate,half_away_integer
from tools.extract_campaign_animation_bindings import character_bindings,resolve_animation,library_identity

OUTPUT=ROOT/'packages/campaign/skills.weedy.json'
HOST='unit/campaign_weedy_selected'
TOKEN='unit/campaign_weedy_cannon'
SKILL='ability/campaign_weedy_s3'
TOKEN_SKILL='ability/campaign_weedy_cannon_s3'
DEPLOY='ability/campaign_weedy_deploy_cannon'
RUPTURE='buff/campaign_weedy_rupture'
PUSH_RULE='rule/campaign_weedy_push_model'
DISTANCE_RULE='rule/campaign_weedy_distance_damage'


def literal_push_profile(path):
    for node in ast.parse(path.read_text(encoding='utf8')).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PUSH_FORCE_TABLE' for t in node.targets):
            table=ast.literal_eval(node.value)
            if set(table)!=set(range(-3,4)) or any(len(r)!=4 or any(v<0 for v in r) for r in table.values()):
                raise ValueError('Historical force model table malformed')
            return {'id':'historical_effect_push_linear_time_projection_v1','native_curve_verified':False,
                'source_sha256':sha(path),'extraction':'AST literal only; no V1 code imported/executed',
                'delta_levels':list(range(-3,4)),'effect_distances':[table[i][3] for i in range(-3,4)],
                'initial_speeds':[table[i][1] for i in range(-3,4)],
                'semantics':'force + source_bonus - mass, clamp[-3,3]; duration2d/v0; linear time projection by V2',
                'pending':['native deceleration/force curve and collision calibration','behind-source force decrease2 interpretation',
                           'DamageByDistance MAX_DISTANCE4 meaning (cap/teleport test) not resolved']}
    raise ValueError('Historical literal PUSH_FORCE_TABLE missing')


def projectile_geometry(path,components):
    import UnityPy
    objects={o.path_id:o for o in UnityPy.load(str(path)).objects}
    extra={};radii=[]
    for component in components.values():
        ptr=component['fields'].get('_rangeToLoad')
        if not ptr:continue
        if ptr['m_FileID']!=0 or ptr['m_PathID'] not in objects:raise ValueError('Splash geometry link missing/external')
        tree=objects[ptr['m_PathID']].read_typetree();goid=tree['m_GameObject']['m_PathID']
        go=objects[goid].read_typetree();extra[str(goid)]={'type':'GameObject','tree':go}
        for link in go['m_Component']:
            ptr=link.get('component',link);obj=objects[ptr['m_PathID']];data=obj.read_typetree()
            extra[str(obj.path_id)]={'type':obj.type.name,'tree':data}
            if obj.type.name=='CircleCollider2D':radii.append(data['m_Radius'])
    if not radii or len(set(radii))!=1:raise ValueError('Native splash radius missing/ambiguous')
    return radii[0],extra


def source():
    normpath=ROOT/'packages/campaign/operators.normalized.json';rosterpath=ROOT/'packages/campaign/roster.reference.json'
    normal=read(normpath);roster=read(rosterpath)
    operator=next(r for r in normal['operators'] if r['character_id']=='char_400_weedy')
    cfg=operator['config']
    if (cfg['elite_phase'],cfg['level'],cfg['potential_rank'],cfg['trust_percent'],cfg['skill_level_index'])!=(2,70,0,100,9):
        raise ValueError('Fixed Weedy configuration drifted')
    level=operator['selected_skill']['level'];bb={b['key']:b['value'] for b in level['blackboard']}
    if level['spData']['spCost']!=33 or level['spData']['initSp']!=20 or level['spData']['maxChargeTime']!=1:
        raise ValueError('Native selected SP contract changed')
    if level['skillType']!='MANUAL' or level['spData']['spType']!='INCREASE_WITH_TIME':raise ValueError('Native manual/time-SP changed')
    token=normal['dependent_characters']['token_10009_weedy_cannon']['raw_character']
    token_level=normal['linked_token_skills']['sktok_weedy_token']['raw_skill']['levels'][9]
    if token_level['blackboard']!=level['blackboard'] or token_level['spData']['spCost']!=0:raise ValueError('Native token M3 parameters differ')
    selected={}
    closure={(r['cabin'],r['pathID']):r for r in roster['frozen']['linked_components']}
    for key in ('skchr_weedy_3','sktok_weedy_token'):
        proto=roster['frozen']['prefab_catalog'][key]
        if any(closure.get((r['cabin'],r['pathID']))!=r for r in proto['components']):raise ValueError('Native skill CAB closure mismatch')
        attack=next(c for c in proto['components'] if c['fields'].get('_projectileKey')=='projectile_weedy_s3')
        fields=attack['fields'];selector=closure.get((attack['cabin'],fields['_selector']['m_PathID']))
        if selector is None or selector['fields']['_targetMotion']!=3 or selector['fields']['_maxNum']!=1:raise ValueError('Native launch selector changed')
        if fields['_damageType']!=2 or fields['_waitForProjectileInvalid']!=1 or fields['_waitForAttackEvent']!=1:raise ValueError('Native projectile/arts timing changed')
        selected[key]={'prefab':proto,'attack_fields':fields,'selector':selector}
    templatespath=ROOT/'ark_emulator/data_buff_templates.json';templates=read(templatespath)
    keys=('knockback[dir]','rupture','trigger_token_skill_within_range','die_to_kill_token')
    frozen_templates={k:templates[k] for k in keys}
    if frozen_templates['rupture']['eventToActions']['ON_BUFF_FINISH'][0]['_damageType']!='PURE':raise ValueError('Rupture finish damage changed')
    charpath,charcomps,modes=character_components('char_400_weedy')
    framepath=ROOT.parent/'data/tables/effect_frames.json';frames=read(framepath)['characters']['char_400_weedy']
    events=[e for e in frames['anims']['Skill_3']['ev'] if e['n']=='OnAttack']
    if len(events)!=1:raise ValueError('Native skill launch event ambiguous')
    spine_assets={};bindings=character_bindings('char_400_weedy',spine_assets)
    animator=bindings['serialized_animator_components'][str(bindings['animator_path_id'])]['fields']
    skill_bindings={face:resolve_animation('Skill_3',animator['_animations'],spine_assets[face_source['payload_sha256']]['parsed'])
                   for face,face_source in bindings['face_sources'].items()}
    exact_events=[[e for e in b['events'] if e['name']=='OnAttack'] for b in skill_bindings.values()]
    if any(len(e)!=1 or e[0]['frame']!=10 or not e[0]['exact_authored_frame'] for e in exact_events):
        raise ValueError('Exact native Weedy S3 event binding changed')
    projectile,components,speed=projectile_source('projectile_weedy_s3');radius,geometry=projectile_geometry(projectile,components)
    constants=ROOT/'ark_emulator/consts.py';profile=literal_push_profile(constants)
    attrs,inputs=interpolate(token['phases'][2]['attributesKeyFrames'],70)
    # Token favor frames explicitly contain zero; no absent-key zero fallback.
    if not token['favorKeyFrames'] or any(f['data']['atk']!=0 for f in token['favorKeyFrames']):raise ValueError('Token favor requires calibration')
    token_stats={k:half_away_integer(v) for k,v in attrs.items() if k in ('atk','maxHp','def','cost')}
    metadata={'status':'selected_skill_model_partial','official_unit_complete':False,'client_validated':False,
        'fixed_config':cfg,'official_selected_skill':operator['selected_skill'],'native_token_level':token_level,
        'native_token_character':token,'native_talents':operator['talents'],'native_skills':selected,
        'native_character_components':charcomps,'native_buff_templates':frozen_templates,
        'native_projectile_components':components,'native_projectile_geometry':geometry,'native_frames':frames,
        'exact_weedy_animation_bindings':bindings,'exact_skill_bindings_by_face':skill_bindings,
        'exact_spine_assets':spine_assets,'spine_reader_identity':library_identity(),
        'push_profile':profile,'token_growth_profile':{'id':'same_owner_e2_level70_direct_token_frames_half_away_v1',
            'client_inheritance_verified':False,'growth_inputs':inputs,'model_stats':token_stats},
        'token_timing_profile':'host on-start trigger invokes token immediately; absent token animation is explicit model boundary',
        'rupture_merge_profile':'same definition/target EXTEND old expiry+8; incoming source; native source/elapsed semantics pending',
        'pending_mechanics':['native_force_curve_and_collision_client_calibration','native_rupture_EXTEND_source_attribution_and_time',
            'native_token_prefab_and_normal_attack_animation_absent_in_local_charpack',
            'native_token_linked_skill_animation_clock_unknown','source_version_correspondence',
            'native_hatred_target_priority_and_air_push_eligibility_pending','native_no_target_forward_projectile_pending'],
        'source_hashes':{'normalized':sha(normpath),'roster':sha(rosterpath),'templates':sha(templatespath),
            'character':sha(charpath),'frames':sha(framepath),'projectile':sha(projectile),'historical_push':sha(constants),
            'attack_helper':sha(ROOT/'tools/build_attack_skill_recipes.py'),'offensive_helper':sha(ROOT/'tools/build_offensive_skill_recipes.py'),
            'normalization_helper':sha(ROOT/'tools/normalize_campaign_operators.py'),'builder':sha(Path(__file__))}}
    metadata['source_hashes']['frame_helper']=sha(ROOT/'tools/extract_campaign_animation_bindings.py')
    return operator,level,bb,token_stats,metadata,exact_events[0][0]['seconds'],speed,radius


def build(require_complete=False):
    op,level,bb,tokstats,meta,launch,speed,radius=source()
    if require_complete:raise ValueError('complete native Weedy unsupported: '+';'.join(meta['pending_mechanics']))
    idx='floor(clamp(inputs.force + inputs.displacement_parameters.source_force_bonus - inputs.mass, -3, 3)) + 3'
    profile=meta['push_profile'];distance=f'params.distances[{idx}]';velocity=f'params.speeds[{idx}]'
    pushrule={'id':PUSH_RULE,'kind':'calculation_rule','version':'1','contract':'movement.displacement',
        'implementation':{'type':'graph','nodes':[{'id':'plan','expression':f'{{"distance": {distance}, "duration": 2 * {distance} / {velocity} if {velocity} > 0 else 0}}'}],'output':'nodes.plan'},
        'parameters':{'distances':profile['effect_distances'],'speeds':profile['initial_speeds']}}
    dotrule={'id':DISTANCE_RULE,'kind':'calculation_rule','version':'1','contract':'damage.pipeline',
        'implementation':{'type':'graph','nodes':[{'id':'damage','expression':
            '{"accepted": True, "amount": inputs.effect.distance * inputs.effect.parameters.value / inputs.effect.parameters.per_distance, "allocations": [], "events": []}'}],'output':'nodes.damage'}}
    rupture={'id':RUPTURE,'kind':'buff','duration_seconds':bb['duration'],'interval_seconds':bb['interval'],
        'stacking':{'mode':'extend','identity':['definition','target'],'max_stacks':1},
        'movement_damage':{'effect':{'op':'damage','damage_type':'true','rules':{'damage.pipeline':DISTANCE_RULE},
                                   'parameters':{'value':bb['value'],'per_distance':bb['dist']}}},
        'metadata':{'native_overrideKey':'rupture','native_overrideType':3,'native_EXTEND_model_merge_unverified':True}}
    range_path=ROOT/'ark_emulator/data_range_table.json';range_data=read(range_path)[level['rangeId']]
    meta['source_hashes']['range_json']=sha(range_path)
    selectors=[{'id':'selector/weedy_launch','kind':'selector','region':{'type':'grid_offsets',
            'offsets':[[-g['row'],g['col']] for g in range_data['grids']]},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1},
        {'id':'selector/weedy_owned_nearby','kind':'selector','region':{'type':'manhattan','radius':4},
         'filters':[{'tag':'weedy_cannon'},{'owner':'source'},{'state':'alive'}]},]
    def shell(identifier,token=False):
        push={'op':'push','force':bb['force'],'direction':'source_facing','distance':0,'rules':{'movement.displacement':PUSH_RULE},
              'parameters':{'mass_attribute':'mass_level','force_bonus_attribute':'force_bonus'}}
        impact={'op':'area','center':'target','radius':radius,'filters':[{'tag':'enemy'},{'state':'alive'}],
            'effects':[{'op':'damage','damage_type':'arts','scale':bb['atk_scale'],'read_mode':{'source_attributes':'at_launch'},
                'on_success':[push,{'op':'apply_buff','buff':RUPTURE,'condition':'inputs.targets[0].components.runtime.alive'}]}]}
        activation={'mode':'manual','costs':[] if token else [{'resource':'sp','amount':level['spData']['spCost']}],
            'parameters':{'counts_as_attack':True,'auto_only':token}}
        if not token:activation['on_start']=[{'op':'trigger_ability','ability':TOKEN_SKILL,'selector':'selector/weedy_owned_nearby'}]
        return {'id':identifier,'kind':'ability','activation':activation,'selector':'selector/weedy_launch','target_capture':'at_cast',
            'parameters':{'projectile_speed':speed,'wait_for_projectiles':True},
            'timeline':[{'at_seconds':0 if token else launch,'effect':impact}],
            'metadata':{'native_duration_minus_one':True,'rupture_duration_is_not_caster_channel':True,
                        'token_event_timing_model_only':token}}
    basepath=ROOT/'packages/campaign/units.base.json';base=read(basepath)
    hero=deepcopy(next(e for e in base['entities'] if e['id']=='unit/char_400_weedy'));hero['id']=HOST
    hero['metadata'].update(complete_operator=False,selected_skill_model=True)
    hero['components']['attributes']['base']['force_bonus']=0
    hero['components']['resources']['sp']={'initial':level['spData']['initSp'],'capacity':level['spData']['spCost'],
        'recovery_rate':level['spData']['increment'],'recovery':{'mode':'periodic','interval_seconds':1},
        'parameters':{'pause_at_full':True,'freeze_while_cast':True,'freeze_cast_modes':['manual']}}
    hero['components']['abilities']=[SKILL,DEPLOY]
    hero['components']['buffs']={'initial':['buff/weedy_cannon_sp_emitter']}
    cannon={'id':TOKEN,'kind':'entity','tags':['player','ground','token','weedy_cannon'],
        'metadata':{'native_token_id':'token_10009_weedy_cannon','normal_attack_pending_no_fake_clock':True},
        'components':{'attributes':{'base':{'atk':tokstats['atk'],'max_hp':tokstats['maxHp'],'def':tokstats['def'],
            'mres':0,'force_bonus':1,'attack_interval':2.4,'block_count':0}},'spatial':{},'abilities':[TOKEN_SKILL],
            'resources':{'hp':{'initial':tokstats['maxHp'],'capacity':tokstats['maxHp'],'role':'health'}},
            'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    enemy={'id':'unit/weedy_force_probe','kind':'entity','tags':['enemy','ground'],
        'components':{'attributes':{'base':{'max_hp':1000000,'atk':0,'def':9999,'mres':20,'mass_level':0,
            'move_speed':0,'block_cost':1}},'spatial':{},'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'}},
            'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    deploy={'id':DEPLOY,'kind':'ability','activation':{'mode':'manual','costs':[{'owner':'battle','resource':'dp','amount':tokstats['cost']}],
        'on_start':[{'op':'spawn','definition':TOKEN,'owner':'source','lifetime_seconds':20,
            'parameters':{'max_owned':1,'on_owner_retire':'remove'},'position':{'row':3,'col':3},'facing':'right'}]},
        'timeline':[],
        'metadata':{'lifetime20_source':'E2 talent description; native token lifetime prefab not available'}}
    buff_sp_parent={'id':'buff/weedy_cannon_sp_emitter','kind':'buff',
        'aura':{'selector':'selector/weedy_owned_nearby','buff':'buff/weedy_cannon_sp_member'}}
    buff_sp_member={'id':'buff/weedy_cannon_sp_member','kind':'buff','stacking':{'mode':'independent'},'interval_seconds':3,
        'effects':[{'op':'modify_resource','target':'source','resource':'sp','delta':1,
                    'parameters':{'respect_recovery_freeze':True}}]}
    meta['source_hashes']['base_units']=sha(basepath)
    meta['scope']='fixed-config selected Weedy S3 model + owned cannon linked-S3/SP/lifetime; no native full-operator approval'
    return {'schemaVersion':2,'status':'selected_skill_model_partial','manifest':{'id':'package/campaign_weedy_s3','version':'1','metadata':meta},
        'entities':[hero,cannon,enemy],'abilities':[shell(SKILL),shell(TOKEN_SKILL,True),deploy],
        'selectors':selectors,'buffs':[rupture,buff_sp_parent,buff_sp_member],'rules':[pushrule,dotrule],
        'scenarioDraft':{'id':'scenario/weedy_selected_skill','ruleset':'ruleset/ark_standard',
            'metadata':{'not_formal_mainline':True,'client_validated':False},'map':{'rows':7,'cols':18},
            'resources':{'dp':{'initial':20,'capacity':99}},'initialEntities':[
                {'definition':HOST,'instanceAlias':'weedy','position':{'row':3,'col':2},'facing':'right'},
                {'definition':enemy['id'],'instanceAlias':'enemy','position':{'row':3,'col':4}}]}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    result=build()
    if args.check:
        if read(OUTPUT)!=result:raise ValueError('Weedy selected recipe source/output identity drift')
    else:OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print('Weedy source-backed selected-S3 model built; native full approval unavailable')


if __name__=='__main__':main()
