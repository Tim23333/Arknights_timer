"""Bind native 4-9 volcano operands to replaceable periodic field rules."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'packages/campaign/chapter04_environment/source.reference.json'
SOURCE_PIN = '148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8'
OUT = ROOT/'packages/campaign/chapter04_environment/volcano.reference_module.json'


def build():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_PIN:
        raise ValueError('Frozen environment source changed')
    source = json.loads(raw)
    prefab = source['prefabs']['tile_volcano']
    def component(name):
        rows = [(key, row) for key,row in prefab['components'].items() if row.get('native_class') == name]
        if len(rows) != 1:
            raise ValueError('Missing/ambiguous native field component: '+name)
        return rows[0]
    trigger_id, trigger = component('UniformRandomTrigger')
    cast_id, cast = component('CastTile')
    tr, cr = trigger['raw'], cast['raw']
    actions = json.loads(cr['_actions']['SerializedState'])
    if len(actions) != 1:
        raise ValueError('Expected exact native NoSourceDamage node')
    node = actions[0]
    checks = {'_damageType':'PURE', '_damageKey':'damage', '_ignoreForSp':False,
              '_damageWithoutModify':False, '_attackType':'NONE', '_isEnvDamage':False,
              '_isUndeadable':False, '_ignoreCancelReasonMask':'NONE', '_instantKillLikeDamage':False,
              '_isNotChangeableValue':False, '_multiplierByKey':False, '_multiplierKey':'cnt',
              '_modifierKey':'', '$type':'Torappu.Battle.Action.Nodes+NoSourceDamage'}
    if node != checks or tr['_preDelay'] != -1.0 or tr['_defaultInterval'] != 1.0:
        raise ValueError('Native field node/clock requires a new source adapter')
    target = cr['_targetOptions']
    advanced_expected={'enableAdvancedOptions':1,'ignoreTargetFree':0,'ignoreAllyTargetFree':0,
        'ignoreHealFree':0,'ignoreMotionMode':0,'ignoreTargetSide':0,'excludeSomeAbnormalFlags':0,
        'containSomeAbnormalFlags':0,'excludeAbnormalFlag':0,'containAbnormalFlag':0,'purposeMask':0,
        'professionMask':0,'checkUnitType':0,'unitTypeMask':0,'onlyIgnoreSomeOfTargetFreeCase':0,
        'abnormalFlag':0,'abnormalCombo':0}
    if set(target)!={'targetSide','targetMotion','targetCategory',*advanced_expected} or any(
            type(target[k]) is not type(v) or target[k]!=v for k,v in advanced_expected.items()):
        raise ValueError('Native advanced target policy requires an explicit adapter')
    if cr['_castMaxCnt']!=-1 or any(json.loads(cr[k]['SerializedState']) is not None
            or cr[k]['SerializedObjectReferences'] for k in ('_actionsOnTrigger','_actionsToSlot')):
        raise ValueError('Limited count or additional tile actions require an explicit consumer')
    if cr['_actions']['SerializedObjectReferences'] or tr['_preDelayEffect']:
        raise ValueError('Referenced tile action or pre-delay effect needs an explicit consumer')
    if [cr['_sourceSide'], target['targetSide'], target['targetMotion'], target['targetCategory'],
        cr['_onlyCombatEnemyInExtraRange'], cr['_injectEnvDmgFlagToBlackboard']] != [0,3,1,1,1,1]:
        raise ValueError('Native field target policy drift')
    tiles = source['stage_tile_operands']['level_main_04-09']
    expected = {'damage':700.0, 'cd_min':13.0, 'cd_max':19.0}
    if len(tiles) != 8 or any({row['key']:row['value'] for row in t['blackboard']} != expected for t in tiles):
        raise ValueError('Expected all eight actual stage operands')
    pipeline = {'id':'rule/ch4/volcano_fixed_damage','kind':'rule','contract':'damage.pipeline',
                'implementation':{'type':'graph','nodes':[{'id':'settle',
                'expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],
                'output':'nodes.settle'}}
    profile = {'type':'periodic_effect_field','expected_blackboard':expected,
        'origin':{'native_prefab':'tile_volcano','native_component':cast_id,'source_sha256':SOURCE_PIN},
        'trigger':{'rule':'rule/ch4/volcano_clock','stream':'field/volcano','sample_count':1,
                   'parameters':{},'initial':{'mode':'sampled'}},
        'membership':{'rule':'rule/ch4/volcano_members','parameters':{}},
        'effects':[{'op':'no_source_damage','fixed_amount':expected[node['_damageKey']],
                    'damage_type':'true','attack_type':node['_attackType'],
                    'damage_without_modify':node['_damageWithoutModify'],'ignore_for_sp':node['_ignoreForSp'],
                    'node_is_env_damage':node['_isEnvDamage'],
                    'env_blackboard_injected':bool(cr['_injectEnvDmgFlagToBlackboard']),
                    'environmental':True,'origin':{'native_node':node['$type']},
                    'rules':{'damage.pipeline':pipeline['id']}}]}
    return {'schemaVersion':2, 'manifest':{'id':'package/chapter04/volcano_reference',
        'requires':['preset/ark_standard'],'metadata':{'source_locks':{str(SOURCE.relative_to(ROOT)):SOURCE_PIN},
            'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'tile_profiles':{'tile_volcano':profile}, 'source_trigger':{'path_id':trigger_id,**deepcopy(tr)},
            'source_cast':{'path_id':cast_id,**deepcopy(cr)},'source_action':deepcopy(node),
            'source_geometry':deepcopy(prefab['geometry_sources']),
            'model_policies':{'first_trigger':'preDelay -1 projected to a sampled first interval',
                'stream':'separate named stream field/volcano; native stream/call order pending comparison',
                'membership':'half-up cell projection: own cell plus four orthogonal neighbouring cells for enemies in blocked or attacking state',
                'visibility':'explicit reference exclusion9/17; native extra targetOptions contain no such flag bits',
                'availability':'explicit no-source default side2; raw CastTile sourceSide0 preserved separately',
                'environmental':'reference environment classification; distinct from native node _isEnvDamage False'},
            'pending_source_semantics':['Native Collider2D overlap and target radius versus cell projection',
                'Exact meaning of onlyCombatEnemyInExtraRange', 'Native initial random stream and quantization order'],
            'scope':'Eight source-bound field operands; no enemy spawn or complete-stage approval',
            'whole_stage_executed':False,'actual_client_verified':False}},
        'rules':[pipeline,
            {'id':'rule/ch4/volcano_clock','kind':'rule','contract':'field.trigger',
             'parameters':{'minimum_key':'cd_min','maximum_key':'cd_max'},
             'implementation':{'type':'provider','provider':'model.field.uniform_trigger'}},
            {'id':'rule/ch4/volcano_members','kind':'rule','contract':'field.members',
             'parameters':{'side_mask':target['targetSide'],'motion_mask':target['targetMotion'],
                'category_mask':target['targetCategory'],'extra_offsets':[[-1,0],[0,-1],[0,1],[1,0]],
                'combat_policy':'blocked_or_attacking','exclude_flags':[9,17], 'respect_target_free':True},
             'implementation':{'type':'provider','provider':'model.field.cell_combat_members'}}]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    raw = (json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes() != raw:
            raise ValueError('Volcano source module bytes changed')
    else:
        OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'source_fields':8,'whole_stage':False}))
