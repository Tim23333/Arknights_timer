"""Bind source BuffTile numerical modules to generic per-cell field owners."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'packages/campaign/chapter02_tiles/source.reference.json'
OPERANDS = ROOT / 'packages/campaign/chapter02_tiles/buffs.motion_state.partial.json'
OUT = ROOT / 'packages/campaign/chapter02_tiles/fields.reference_model.json'
PINS = {SOURCE: 'fc5ea7050014f56b5725be44805c9c81d17e157615a7eeb7c5d64401059610af',
        OPERANDS: '25d8b684b3ed96f4274feeaab65a455db07550ab5f06575cdf7b972f19b62c10'}


def state():
    return {'side':0, 'motion':1, 'category':1, 'profession':0, 'unit_type':4,
            'target_free':False, 'ally_target_free':False, 'heal_free':False,
            'camouflage':False, 'can_select_camouflage':False, 'abnormal_flags':[],
            'abnormal_combos':[], 'target_free_flags':[], 'target_free_combos':[]}


def build():
    for path, pin in PINS.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError('Tile field source drift: '+str(path))
    source = json.loads(SOURCE.read_bytes()); operands = json.loads(OPERANDS.read_bytes())
    roots = {row['tile_key']: row['raw'] for row in source['root_components']}
    package = {'schemaVersion':2, 'manifest': {'id':'package/chapter02_tile_field_reference_model',
        'requires':['preset/ark_standard'], 'metadata':{
            'source_locks':{str(path.relative_to(ROOT)).replace('\\','/'):pin for path,pin in PINS.items()},
            'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'declared_policy':'BuffTile ALLY uses explicit virtual side0 owner; advanced options disabled; typed source qualification',
            'feedback_pending':['native target-category getters and tile permission semantics',
                                'native world-to-cell boundary precision and hook rounding order'],
            'actual_client_verified':False}}, 'entities':[], 'selectors':[], 'buffs':[], 'rules':[
            {'id':'rule/ch2/tile_qualification','kind':'rule','contract':'targeting.eligibility',
             'implementation':{'type':'provider','provider':'model.targeting.eligibility'}}]}
    for key, member in [('tile_healing','buff/ch2/healing_tile_member'), ('tile_gazebo','buff/ch2/gazebo_member')]:
        raw = roots[key]; options = raw['_targetOptions']
        if raw['_sourceSide'] != 1 or options['enableAdvancedOptions'] != 0:
            raise ValueError('This explicit BuffTile adapter only supports sourceSide ALLY1 and disabled advanced options')
        if (options['targetSide'],options['targetMotion'],options['targetCategory']) != (1,3,1):
            raise ValueError('BuffTile source target mask changed')
        configuration = {'_'+name:value for name,value in options.items()}
        configuration.update(_needProfessionMask=0, _forceIgnoreCamouflage=0)
        if options['ignoreTargetSide'] or options['containSomeAbnormalFlags']:
            raise ValueError('Unsupported active target-option switch')
        adapted=deepcopy(next(row for row in operands['buffs'] if row['id']==member))
        adapted['id']=member+'/field_owned';adapted['stacking']={'mode':'independent'}
        adapted['metadata'].update(parent_operand_definition=member,
            declared_stacking_adapter='One owned child per occupied tile; ordinary actor occupies one projected cell. Native maxStack callbacks remain user feedback.')
        package['buffs'].append(adapted);member=adapted['id']
        selector='selector/ch2/field/'+key; parent='buff/ch2/field/'+key; unit='unit/ch2/field/'+key
        package['selectors'].append({'id':selector,'kind':'selector',
            'region':{'type':'grid_offsets','offsets':[[0,0]],'rotate_with_facing':False},
            'filters':[{'state':'alive'}],
            'eligibility':{'rule':'rule/ch2/tile_qualification','parameters':{
                'source_configuration':configuration,'side_policy':'relative_ally_enemy',
                'neutral_policy':'reject','defaults':state()}},
            'metadata':{'native_target_options':deepcopy(options),'advanced_disabled':True}})
        package['buffs'].append({'id':parent,'kind':'buff',
            'aura':{'selector':selector,'buff':member},
            'metadata':{'source_tile':key,'source_clear_when_left':raw['_clearBuffsWhenLeft'],
                        'lifetime':'explicit infinite parent; member owned by each tile source'}})
        package['entities'].append({'id':unit,'kind':'entity','tags':['tile_field_owner'],
            'components':{'spatial':{},'selection_state':state(),'buffs':{'initial':[parent]}},
            'metadata':{'native_tile_key':key,'virtual_field_owner':True}})
    return package


def profiles(native_map):
    """Profiles bind the entire actual numeric tile blackboard, without a hole stub."""
    from ark_sim.domains.tile_fields import board, same_data
    result={}
    for tile in native_map['tiles']:
        key=tile.get('tileKey')
        if key not in ('tile_healing','tile_gazebo'):continue
        actual=board(tile)
        expected=({'HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO':.03} if key=='tile_healing'
                  else {'atk_scale':1.7,'attack_speed':-20.0})
        if not same_data(actual,expected):raise ValueError('Source field operand mismatch: '+key)
        result[key]={'type':'occupancy_buff_field','definition':'unit/ch2/field/'+key,
                     'expected_blackboard':deepcopy(actual)}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    package=build();raw=(json.dumps(package,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Tile field package changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'field_types':2,'hole_implemented_here':False}))
