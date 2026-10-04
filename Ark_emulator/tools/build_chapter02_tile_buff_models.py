"""Source-backed tile Buff operands, without claiming native tile occupancy."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter02_tiles/source.reference.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    source=json.loads(SOURCE.read_bytes())
    for name,pin in source['source_locks'].items():
        if sha(ROOT/name)!=pin:raise ValueError('Tile source drift: '+name)
    roots={r['tile_key']:r['raw'] for r in source['root_components']}
    assert roots['tile_healing']['_clearBuffsWhenLeft']==roots['tile_gazebo']['_clearBuffsWhenLeft']==1
    assert roots['tile_healing']['_buffs'][0]['attributes']['attributeModifiers'][0]['attributeType']==19
    assert roots['tile_gazebo']['_buffs'][0]['attributes']['attributeModifiers'][0]['attributeType']==7
    def board(stage,key):
        rows=[r['raw_tile']['blackboard'] for r in source['stages'][stage]['selected_special_cells'] if r['raw_tile']['tileKey']==key]
        if not rows or any(r!=rows[0] for r in rows):raise ValueError('Multiple source tile board variants require distinct definitions')
        return {r['key']:r['value'] for r in rows[0]}
    healing=board('02-10','tile_healing');gazebo=board('02-09','tile_gazebo')
    assert healing=={'HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO':.03}
    assert gazebo=={'atk_scale':1.7,'attack_speed':-20.0}
    template=source['templates']['templates']['airforce_enhance']['parsed']['eventToActions']['ON_CALCULATE_DAMAGE']
    assert template[0]['_motionMask']=='FLY_ONLY' and template[1]['_atkScaleKey']=='atk_scale'
    return {'schemaVersion':2,'manifest':{'id':'package/chapter02_tile_buff_dependencies','requires':['preset/ark_standard'],
        'metadata':{'source_sha256':sha(SOURCE),'builder_sha256':sha(__file__),'source_target_options':{k:deepcopy(v.get('_targetOptions')) for k,v in roots.items()},
            'scope':'Only actual source Buff numerical operands; occupancy/enter/leave callback adapter not implemented',
            'native_game_verified':False,'require_complete_rejected':True,'pending':['native BuffTile target filtering/selected membership and callbacks',
                'source-side/abnormal permission and class category getter','maxHP ratio recovery precision/timing, cannot assert heal/free policy',
                'native HoleTile entry/flight/motionchange lethality','gazebo damagehook insertion/rounding order']}},
        'buffs':[{'id':'buff/ch2/healing_tile_member','kind':'buff','stacking':{'mode':'refresh'},
                  'modifiers':[{'attribute':'hp_ratio_recovery','layer':'flat','value':healing['HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO']}],
                  'metadata':{'native_buff':deepcopy(roots['tile_healing']['_buffs'][0]),'requires_target_hp_resource_driver':True}},
                 {'id':'buff/ch2/gazebo_member','kind':'buff','stacking':{'mode':'refresh'},
                  'modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':gazebo['attack_speed']/100}],
                  'damage_hooks':[{'phase':'before','rule':'rule/ch2/gazebo_flying_scale','condition':"'flying' in inputs.target.tags"}],
                  'metadata':{'native_buff':deepcopy(roots['tile_gazebo']['_buffs'][0]),'attack_speed_encoding':'explicit model percent points /100',
                              'native_hook_order_verified':False,'target_motion_adapter':'explicit flying tag, not recovered getter'}}],
        'rules':[{'id':'rule/ch2/tile_hp_ratio_recovery','kind':'rule','contract':'resource.recovery','implementation':{
                    'type':'expression','expression':'inputs.current + inputs.delta_seconds * inputs.attributes.max_hp * inputs.attributes.hp_ratio_recovery'}},
                 {'id':'rule/ch2/gazebo_flying_scale','kind':'rule','contract':'damage.request','parameters':{'atk_scale':gazebo['atk_scale']},
                    'implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'effect':{'op':'damage','damage_type':inputs.effect.damage_type,'attack':inputs.effect.attack,'defense':inputs.effect.defense,'resistance':inputs.effect.resistance,'scale':inputs.effect.scale*params.atk_scale,'additions':inputs.effect.additions},'effects':[]}"}],'output':'nodes.result'}}]}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();p=build()
    out=ROOT/'packages/campaign/chapter02_tiles/buffs.partial.json';raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if out.read_bytes()!=raw:raise ValueError('Tile Buff model output drift')
    else:out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)
    print(json.dumps({'output_sha256':sha(out),'native_game_verified':False,'tile_occupancy_implemented':False}))
